#!/usr/bin/env python3
"""Discover patterns across extracted JIRA tickets.

Stage 2: Pattern Discovery
---------------------------
Analyzes extracted tickets (from Stage 1) to discover common patterns:
- Groups tickets by problem type, components, RHEL versions
- Clusters similar tickets (≥3 by default)
- Tags tickets with pattern_id
- Generates pattern reports for batch fixing

Features:
- Works on any extracted YAML (new or old)
- Re-runnable without re-extraction
- Configurable minimum pattern size
- Outputs tagged YAML + pattern report
- Automatically filters OUT_OF_SCOPE tickets (meta-tickets, non-RHEL)
- Incremental saving with checkpoints (resume on crash)

Usage:
    # Default: discover patterns in extracted_tickets.yaml
    python scripts/discover_ticket_patterns.py

    # Custom input/output
    python scripts/discover_ticket_patterns.py \
      --input config/extracted_tickets_20260407.yaml \
      --output-tagged config/tickets_with_patterns.yaml \
      --output-report patterns_report.json

    # Require at least 5 tickets per pattern
    python scripts/discover_ticket_patterns.py --min-pattern-size 5
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add src/ to sys.path for imports
SRC_ROOT = Path(__file__).parent.parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from heal.core.pattern_discovery import PatternDiscoveryAgent  # noqa: E402

# HEAL repository root for file paths
REPO_ROOT = SRC_ROOT.parent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_INPUT = REPO_ROOT / "config" / "extracted_tickets.yaml"
DEFAULT_OUTPUT_TAGGED = REPO_ROOT / "config" / "tickets_with_patterns.yaml"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "patterns_report.json"
DEFAULT_CHECKPOINT_DIR = REPO_ROOT / ".checkpoints" / "pattern_discovery"


def load_extracted_tickets(path: Path) -> list[dict]:
    """Load extracted tickets from YAML and filter out non-RHEL tickets.

    Args:
        path: Path to extracted tickets YAML

    Returns:
        List of ticket dictionaries (RHEL tickets only, OUT_OF_SCOPE filtered)
    """
    if not path.exists():
        logger.error(f"Input file not found: {path}")
        logger.error("Run extract_jira_tickets.py first to generate extracted tickets")
        sys.exit(1)

    logger.info(f"Loading tickets from {path}")
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "tickets" not in data:
        logger.error("YAML file has no 'tickets' key")
        sys.exit(1)

    all_tickets = data["tickets"]
    logger.info(f"Loaded {len(all_tickets)} tickets")

    # Filter out OUT_OF_SCOPE tickets (meta-tickets, jailbreaks, non-RHEL)
    rhel_tickets = [
        t for t in all_tickets if not t.get("description", "").startswith("OUT_OF_SCOPE")
    ]

    filtered_count = len(all_tickets) - len(rhel_tickets)
    if filtered_count > 0:
        logger.info(f"Filtered out {filtered_count} OUT_OF_SCOPE tickets (meta-tickets, non-RHEL)")
        logger.info(f"Pattern discovery will use {len(rhel_tickets)} RHEL tickets")

    if len(rhel_tickets) == 0:
        logger.error("No RHEL tickets found after filtering OUT_OF_SCOPE")
        logger.error("All tickets were meta-tickets or out of scope")
        sys.exit(1)

    return rhel_tickets


def format_tickets_for_classification(tickets: list[dict]) -> list[dict]:
    """Convert extracted ticket format to format needed by PatternDiscoveryAgent.

    Args:
        tickets: List of extracted tickets from YAML

    Returns:
        List of tickets in JIRA-like format for classification
    """
    formatted = []
    for ticket in tickets:
        # Extract first turn's data
        first_turn = ticket["turns"][0]
        formatted.append(
            {
                "key": ticket["conversation_group_id"],
                "fields": {
                    "summary": first_turn["query"],
                    "description": first_turn.get("expected_response", ""),
                },
            }
        )
    return formatted


def save_tagged_yaml(tickets: list[dict], patterns: list, path: Path, metadata: dict) -> None:
    """Save tickets with pattern tags to YAML.

    Args:
        tickets: Original extracted tickets
        patterns: Discovered patterns
        path: Output path
        metadata: Original metadata from input YAML
    """
    # Build pattern_id lookup
    ticket_to_pattern = {}
    for pattern in patterns:
        for ticket_key in pattern.matched_tickets:
            ticket_to_pattern[ticket_key] = pattern.pattern_id

    # Tag tickets
    tagged_tickets = []
    for ticket in tickets:
        tagged_ticket = ticket.copy()
        pattern_id = ticket_to_pattern.get(ticket["conversation_group_id"])
        if pattern_id:
            tagged_ticket["pattern_id"] = pattern_id
        else:
            tagged_ticket["pattern_id"] = None  # Ungrouped ticket

        tagged_tickets.append(tagged_ticket)

    # Output structure
    output = {
        "metadata": {
            **metadata,
            "pattern_discovery_at": datetime.utcnow().isoformat(),
            "patterns_found": len(patterns),
            "ungrouped_tickets": sum(1 for t in tagged_tickets if not t["pattern_id"]),
        },
        "tickets": tagged_tickets,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved tagged tickets to {path}")


def save_pattern_report(patterns: list, path: Path, summary: dict) -> None:
    """Save pattern discovery report to JSON.

    Args:
        patterns: Discovered patterns
        path: Output path
        summary: Summary statistics
    """
    # Convert patterns to dict format
    patterns_data = []
    for pattern in patterns:
        patterns_data.append(
            {
                "pattern_id": pattern.pattern_id,
                "description": pattern.description,
                "ticket_count": pattern.ticket_count,
                "representative_tickets": pattern.representative_tickets,
                "matched_tickets": pattern.matched_tickets,
                "common_problem_type": pattern.common_problem_type,
                "common_components": pattern.common_components,
                "version_pattern": pattern.version_pattern,
                "verification_queries": pattern.verification_queries,
            }
        )

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "patterns": patterns_data,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Saved pattern report to {path}")


def save_checkpoint(checkpoint_dir: Path, checkpoint_name: str, data: any) -> None:
    """Save checkpoint data incrementally.

    Args:
        checkpoint_dir: Directory for checkpoints
        checkpoint_name: Name of checkpoint file (e.g., "classifications.json")
        data: Data to save (will be JSON serialized)
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / checkpoint_name

    with open(checkpoint_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"  💾 Checkpoint saved: {checkpoint_path}")


def load_checkpoint(checkpoint_dir: Path, checkpoint_name: str) -> any:
    """Load checkpoint data if it exists.

    Args:
        checkpoint_dir: Directory for checkpoints
        checkpoint_name: Name of checkpoint file

    Returns:
        Loaded data or None if checkpoint doesn't exist
    """
    checkpoint_path = checkpoint_dir / checkpoint_name

    if not checkpoint_path.exists():
        return None

    with open(checkpoint_path) as f:
        data = json.load(f)

    logger.info(f"  ♻️  Checkpoint loaded: {checkpoint_path}")
    return data


def clear_checkpoints(checkpoint_dir: Path) -> None:
    """Clear all checkpoints after successful completion.

    Args:
        checkpoint_dir: Directory for checkpoints
    """
    if checkpoint_dir.exists():
        import shutil

        shutil.rmtree(checkpoint_dir)
        logger.info(f"  🧹 Cleared checkpoints: {checkpoint_dir}")


async def main():
    """Main pattern discovery workflow."""
    parser = argparse.ArgumentParser(description="Discover patterns across extracted JIRA tickets")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input YAML with extracted tickets (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output-tagged",
        type=Path,
        default=DEFAULT_OUTPUT_TAGGED,
        help=f"Output YAML with pattern tags (default: {DEFAULT_OUTPUT_TAGGED})",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=DEFAULT_OUTPUT_REPORT,
        help=f"Output JSON pattern report (default: {DEFAULT_OUTPUT_REPORT})",
    )
    parser.add_argument(
        "--min-pattern-size",
        type=int,
        default=3,
        help="Minimum tickets required to form a pattern (default: 3)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore checkpoints and start fresh (default: resume from checkpoints)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Max tickets per Claude SDK call for pattern discovery (default: 15)",
    )

    args = parser.parse_args()

    # Setup checkpoint directory
    checkpoint_dir = DEFAULT_CHECKPOINT_DIR

    # Clear checkpoints if --fresh flag is set
    if args.fresh:
        logger.info("--fresh flag set, clearing any existing checkpoints")
        clear_checkpoints(checkpoint_dir)

    # Load extracted tickets
    tickets = load_extracted_tickets(args.input)

    if len(tickets) < args.min_pattern_size:
        logger.warning(
            f"Only {len(tickets)} tickets - need at least {args.min_pattern_size} to form patterns"
        )
        logger.warning("Skipping pattern discovery")
        return

    # Convert to format for classification
    formatted_tickets = format_tickets_for_classification(tickets)

    # Initialize pattern discovery agent
    logger.info("Initializing pattern discovery agent...")
    agent = PatternDiscoveryAgent()

    # Stage 1: Classify tickets (with checkpoint resume)
    logger.info(f"\n{'='*80}")
    logger.info("STAGE 1: Classifying Tickets")
    logger.info(f"{'='*80}\n")

    # Try to load classification checkpoint
    classifications_data = load_checkpoint(checkpoint_dir, "classifications.json")

    if classifications_data:
        logger.info(f"Resuming from checkpoint: {len(classifications_data)} classifications loaded")
        # Reconstruct classification objects from JSON
        from heal.core.pattern_discovery import TicketClassification

        classifications = [TicketClassification(**c) for c in classifications_data]
    else:
        logger.info("No checkpoint found, starting fresh classification")
        classifications = await agent.classify_tickets(formatted_tickets)

        # Save checkpoint after classification completes
        classifications_dict = [
            {
                "ticket_key": c.ticket_key,
                "query": c.query,
                "problem_type": c.problem_type,
                "components": c.components,
                "rhel_versions": c.rhel_versions,
                "keywords": c.keywords,
            }
            for c in classifications
        ]
        save_checkpoint(checkpoint_dir, "classifications.json", classifications_dict)

    logger.info(f"Classified {len(classifications)} tickets")
    logger.info("\nProblem type breakdown:")
    problem_types = {}
    for c in classifications:
        problem_types[c.problem_type] = problem_types.get(c.problem_type, 0) + 1

    for ptype, count in sorted(problem_types.items(), key=lambda x: -x[1]):
        logger.info(f"  {ptype}: {count}")

    # Stage 2: Discover patterns (with checkpoint resume)
    logger.info(f"\n{'='*80}")
    logger.info("STAGE 2: Discovering Patterns")
    logger.info(f"{'='*80}\n")

    # Try to load pattern checkpoint
    patterns_data = load_checkpoint(checkpoint_dir, "patterns.json")

    if patterns_data:
        logger.info(f"Resuming from checkpoint: {len(patterns_data)} patterns loaded")
        # Reconstruct pattern objects from JSON
        from heal.core.pattern_discovery import PatternGroup

        patterns = [PatternGroup(**p) for p in patterns_data]
    else:
        logger.info("No pattern checkpoint found, discovering patterns")
        try:
            patterns = await agent.discover_patterns(classifications, batch_size=args.batch_size)

            # Save checkpoint after pattern discovery completes
            patterns_dict = [
                {
                    "pattern_id": p.pattern_id,
                    "description": p.description,
                    "ticket_count": p.ticket_count,
                    "representative_tickets": p.representative_tickets,
                    "matched_tickets": p.matched_tickets,
                    "common_problem_type": p.common_problem_type,
                    "common_components": p.common_components,
                    "version_pattern": p.version_pattern,
                    "verification_queries": p.verification_queries,
                }
                for p in patterns
            ]
            save_checkpoint(checkpoint_dir, "patterns.json", patterns_dict)

        except Exception as e:
            logger.error(f"Pattern discovery failed: {e}")
            logger.error("This may be due to:")
            logger.error("  - Claude SDK subprocess crash")
            logger.error("  - Malformed response from LLM")
            logger.error("  - Prompt too large or complex")
            logger.error(f"  - Number of tickets: {len(classifications)}")
            logger.error("\nCheckpoint saved - you can resume by re-running this script")
            logger.error(f"Checkpoint location: {checkpoint_dir}")
            raise

    if not patterns:
        logger.warning("No patterns found!")
        logger.warning(f"Try lowering --min-pattern-size (currently {args.min_pattern_size})")
        return

    logger.info(f"\nDiscovered {len(patterns)} patterns:")
    for pattern in patterns:
        logger.info(f"\n  Pattern: {pattern.pattern_id}")
        logger.info(f"    Description: {pattern.description}")
        logger.info(f"    Tickets: {pattern.ticket_count}")
        logger.info(f"    Problem Type: {pattern.common_problem_type}")
        logger.info(f"    Components: {', '.join(pattern.common_components)}")
        logger.info(f"    Representatives: {', '.join(pattern.representative_tickets)}")

    # Calculate summary stats
    total_grouped = sum(p.ticket_count for p in patterns)
    ungrouped = len(tickets) - total_grouped

    summary = {
        "total_tickets": len(tickets),
        "patterns_found": len(patterns),
        "tickets_grouped": total_grouped,
        "tickets_ungrouped": ungrouped,
        "grouping_rate": f"{(total_grouped / len(tickets) * 100):.1f}%",
        "min_pattern_size": args.min_pattern_size,
    }

    # Save outputs
    logger.info(f"\n{'='*80}")
    logger.info("Saving Outputs")
    logger.info(f"{'='*80}\n")

    # Preserve original metadata
    with open(args.input) as f:
        original_data = yaml.safe_load(f)
    original_metadata = original_data.get("metadata", {})

    save_tagged_yaml(tickets, patterns, args.output_tagged, original_metadata)
    save_pattern_report(patterns, args.output_report, summary)

    # Clear checkpoints after successful completion
    clear_checkpoints(checkpoint_dir)

    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("PATTERN DISCOVERY COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total tickets: {len(tickets)}")
    logger.info(f"Patterns found: {len(patterns)}")
    logger.info(f"Tickets grouped: {total_grouped} ({summary['grouping_rate']})")
    logger.info(f"Tickets ungrouped: {ungrouped}")
    logger.info("\nOutputs:")
    logger.info(f"  Tagged YAML: {args.output_tagged}")
    logger.info(f"  Pattern report: {args.output_report}")

    # Show what to do next
    logger.info(f"\n{'='*80}")
    logger.info("NEXT STEPS")
    logger.info(f"{'='*80}")
    logger.info("Review the pattern report to understand common issues:")
    logger.info(f"  cat {args.output_report} | jq '.patterns'")
    logger.info("\nUse patterns to guide batch fixes in okp-mcp:")
    logger.info("  - Fix one pattern → validates against all tickets in that pattern")
    logger.info("  - Reduces regression risk vs fixing tickets individually")


if __name__ == "__main__":
    import os
    import sys

    exit_code = 0
    interrupted = False

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        interrupted = True
        exit_code = 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        exit_code = 1
    finally:
        # Aggressive cleanup: Force kill any remaining Claude SDK subprocess tasks
        # This is necessary because Claude SDK spawns background tasks that don't
        # get properly cleaned up when the query finishes
        #
        # IMPORTANT: We use os._exit() instead of sys.exit() because sys.exit()
        # waits for background threads to finish, which causes hangs with Claude SDK
        if not interrupted:
            # On normal completion, try gentle cleanup first
            try:
                loop = asyncio.get_event_loop()
                if loop and not loop.is_closed():
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    if pending:
                        for task in pending:
                            task.cancel()
                        try:
                            loop.run_until_complete(asyncio.wait(pending, timeout=0.5))
                        except Exception:
                            pass
            except Exception:
                pass

        # Force exit to kill any lingering subprocess threads
        # This works for both normal completion AND Ctrl+C interruption
        os._exit(exit_code)
