#!/usr/bin/env python3
"""Review extracted tickets for answer quality.

Reviews expected_response fields against production quality guidelines.
Can be run independently on any extracted tickets YAML file.

Usage:
    # Review extracted tickets
    python src/heal/bootstrap/review_extracted_tickets.py \
        --input config/extracted_tickets.yaml \
        --output config/extracted_tickets_reviewed.yaml \
        --report review_report.json

    # Review specific tickets only
    python src/heal/bootstrap/review_extracted_tickets.py \
        --input config/extracted_tickets.yaml \
        --tickets RSPEED-2651,RSPEED-2652

    # Review and auto-fix issues
    python src/heal/bootstrap/review_extracted_tickets.py \
        --input config/extracted_tickets.yaml \
        --auto-fix
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Add src/ to sys.path for imports
SRC_ROOT = Path(__file__).parent.parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from heal.core.answer_review_agent import AnswerReviewAgent  # noqa: E402

# HEAL repository root for file paths
REPO_ROOT = SRC_ROOT.parent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_extracted_tickets(input_file: Path) -> dict[str, Any]:
    """Load extracted tickets YAML.

    Args:
        input_file: Path to extracted tickets YAML

    Returns:
        Dict with metadata and tickets list
    """
    logger.info(f"Loading extracted tickets from {input_file}")
    with open(input_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "tickets" not in data:
        raise ValueError(f"Invalid format: {input_file} missing 'tickets' key")

    logger.info(f"Loaded {len(data['tickets'])} tickets")
    return data


def save_reviewed_tickets(data: dict[str, Any], output_file: Path, review_stats: dict) -> None:
    """Save reviewed tickets to YAML.

    Args:
        data: Ticket data with review metadata
        output_file: Output path
        review_stats: Review statistics
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Add review metadata
    data["metadata"]["reviewed_at"] = datetime.utcnow().isoformat()
    data["metadata"]["review_stats"] = review_stats

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved reviewed tickets to {output_file}")


def save_review_report(report: dict[str, Any], report_file: Path) -> None:
    """Save review report to JSON.

    Args:
        report: Review report data
        report_file: Output path
    """
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Saved review report to {report_file}")


async def review_ticket(
    ticket: dict[str, Any],
    reviewer: AnswerReviewAgent,
    auto_fix: bool = False,
) -> dict[str, Any]:
    """Review a single ticket's answer quality.

    Args:
        ticket: Ticket data with conversation
        reviewer: Review agent
        auto_fix: Whether to apply suggested fixes

    Returns:
        Review result dict
    """
    # Extract from conversation structure
    conv_id = ticket["conversation_group_id"]
    if not ticket.get("turns") or len(ticket["turns"]) == 0:
        return {
            "ticket_key": conv_id,
            "passes": False,
            "score": 0.0,
            "issues": ["No turns in conversation"],
        }

    turn = ticket["turns"][0]
    query = turn.get("query", "")
    expected_response = turn.get("expected_response", "")
    sources = turn.get("expected_urls", [])

    # Review answer
    result = await reviewer.review_answer(query, expected_response, sources)

    # Build review result
    review = {
        "ticket_key": conv_id,
        "passes": result.passes,
        "score": result.score,
        "issues": result.issues,
    }

    if result.suggested_fix:
        review["suggested_fix"] = result.suggested_fix

    # Apply fix if requested
    if auto_fix and result.suggested_fix and not result.passes:
        logger.info(f"  Auto-fixing {conv_id}")
        turn["expected_response"] = result.suggested_fix
        turn["_review_applied_fix"] = True

    return review


async def main():
    """Main review workflow."""
    parser = argparse.ArgumentParser(description="Review extracted tickets for answer quality")
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "config" / "extracted_tickets.yaml",
        help="Input extracted tickets YAML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output reviewed tickets YAML (default: same as input)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "config" / "review_report.json",
        help="Review report JSON output",
    )
    parser.add_argument(
        "--tickets",
        type=str,
        help="Comma-separated ticket keys to review (e.g., RSPEED-2651,RSPEED-2652)",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically apply suggested fixes to failing answers",
    )

    args = parser.parse_args()

    # Default output to input file if not specified
    if not args.output:
        args.output = args.input

    # Load extracted tickets
    data = load_extracted_tickets(args.input)

    # Filter to specific tickets if requested
    tickets_to_review = data["tickets"]
    if args.tickets:
        ticket_keys = [k.strip() for k in args.tickets.split(",")]
        tickets_to_review = [
            t for t in data["tickets"] if t.get("conversation_group_id") in ticket_keys
        ]
        logger.info(f"Filtered to {len(tickets_to_review)} tickets: {ticket_keys}")

    if not tickets_to_review:
        logger.error("No tickets to review!")
        return

    # Initialize review agent
    logger.info("Initializing Answer Review Agent...")
    reviewer = AnswerReviewAgent()

    # Review tickets
    logger.info(f"\n{'='*80}")
    logger.info(f"Reviewing {len(tickets_to_review)} tickets")
    logger.info(f"{'='*80}\n")

    reviews = []
    for i, ticket in enumerate(tickets_to_review, 1):
        conv_id = ticket.get("conversation_group_id", f"ticket_{i}")
        logger.info(f"\n[{i}/{len(tickets_to_review)}] Reviewing {conv_id}")

        try:
            review = await review_ticket(ticket, reviewer, auto_fix=args.auto_fix)
            reviews.append(review)

            # Log result
            status = "✅ PASS" if review["passes"] else "❌ FAIL"
            logger.info(f"  {status} - Score: {review['score']:.2f}")
            if review["issues"]:
                for issue in review["issues"]:
                    logger.info(f"    - {issue}")

        except Exception as e:
            logger.error(f"  Failed to review {conv_id}: {e}")
            reviews.append(
                {
                    "ticket_key": conv_id,
                    "passes": False,
                    "score": 0.0,
                    "issues": [f"Review error: {str(e)}"],
                }
            )

    # Calculate statistics
    total = len(reviews)
    passed = sum(1 for r in reviews if r["passes"])
    failed = total - passed
    avg_score = sum(r["score"] for r in reviews) / total if total > 0 else 0.0

    stats = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": avg_score,
    }

    # Build report
    report = {
        "reviewed_at": datetime.utcnow().isoformat(),
        "input_file": str(args.input),
        "auto_fix_applied": args.auto_fix,
        "statistics": stats,
        "reviews": reviews,
    }

    # Save outputs
    save_review_report(report, args.report)

    if args.auto_fix:
        save_reviewed_tickets(data, args.output, stats)

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("REVIEW COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total tickets: {total}")
    logger.info(f"✅ Passed: {passed} ({stats['pass_rate']*100:.1f}%)")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Average score: {avg_score:.2f}")
    logger.info(f"\nReview report: {args.report}")
    if args.auto_fix:
        logger.info(f"Fixed tickets: {args.output}")


if __name__ == "__main__":
    import os

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
        # Aggressive cleanup for Claude SDK
        if not interrupted:
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

        os._exit(exit_code)
