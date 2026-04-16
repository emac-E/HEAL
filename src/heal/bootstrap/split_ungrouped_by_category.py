#!/usr/bin/env python3
"""Split ungrouped tickets into category-based mini-groups for fixing.

Takes UNGROUPED.yaml (tickets with no pattern) and creates category-based
mini-groups using existing classifications (problem_type, components).

This enables:
- Bug tracking by category (EOL, INCORRECT_PROCEDURE, etc.)
- Component analysis (containers, networking, etc.)
- Efficient fixing of pairs/triplets vs pure singletons

No LLM calls - just uses existing classification data.

Usage:
    python src/heal/bootstrap/split_ungrouped_by_category.py \
        --ungrouped config/patterns/UNGROUPED.yaml \
        --classifications config/tickets_with_patterns.yaml \
        --output-dir config/ungrouped/

Output:
    - EOL_UNSUPPORTED_containers_2tickets.yaml
    - INCORRECT_PROCEDURE_networking_1ticket.yaml
    - OTHER_selinux_1ticket.yaml
    etc.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_classifications(classifications_file: Path) -> dict:
    """Load ticket classifications from tickets_with_patterns.yaml.

    This file was created by pattern discovery and has the full ticket data
    plus classifications in the metadata.

    Args:
        classifications_file: Path to tickets_with_patterns.yaml

    Returns:
        Dict mapping conversation_group_id → classification dict
    """
    logger.info(f"Loading classifications from {classifications_file}")

    with open(classifications_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    tickets = data.get("tickets", [])

    # Check if we have classifications checkpoint (more reliable)
    checkpoint_file = Path(".checkpoints/pattern_discovery/classifications.json")
    if checkpoint_file.exists():
        logger.info(f"  Found classifications checkpoint: {checkpoint_file}")
        with open(checkpoint_file) as f:
            classifications_list = json.load(f)

        classifications = {
            c["ticket_key"]: {
                "problem_type": c["problem_type"],
                "components": c["components"],
                "rhel_versions": c.get("rhel_versions", []),
                "keywords": c.get("keywords", []),
            }
            for c in classifications_list
        }

        logger.info(f"  Loaded {len(classifications)} classifications from checkpoint")
        return classifications

    # Fallback: extract from tickets (if checkpoint doesn't exist)
    logger.warning("  No checkpoint found, using fallback (less reliable)")
    classifications = {}

    for ticket in tickets:
        ticket_id = ticket.get("conversation_group_id")
        # Try to extract from metadata if available
        metadata = ticket.get("metadata", {})
        if "classification" in metadata:
            classifications[ticket_id] = metadata["classification"]

    logger.info(f"  Loaded {len(classifications)} classifications from YAML")
    return classifications


def load_ungrouped_tickets(ungrouped_file: Path) -> list:
    """Load ungrouped tickets from UNGROUPED.yaml.

    Args:
        ungrouped_file: Path to UNGROUPED.yaml

    Returns:
        List of ticket dicts
    """
    logger.info(f"Loading ungrouped tickets from {ungrouped_file}")

    with open(ungrouped_file, encoding="utf-8") as f:
        tickets = yaml.safe_load(f)

    logger.info(f"  Loaded {len(tickets)} ungrouped tickets")
    return tickets


def group_by_category(tickets: list, classifications: dict) -> dict:
    """Group ungrouped tickets by problem_type + main component.

    Args:
        tickets: List of ungrouped ticket dicts
        classifications: Dict mapping ticket_id → classification

    Returns:
        Dict mapping category_key → List[ticket]
    """
    logger.info("Grouping tickets by category...")

    grouped = defaultdict(list)

    for ticket in tickets:
        ticket_id = ticket.get("conversation_group_id")

        # Get classification
        classification = classifications.get(ticket_id)
        if not classification:
            logger.warning(f"  No classification for {ticket_id}, using OTHER")
            problem_type = "OTHER"
            component = "uncategorized"
        else:
            problem_type = classification.get("problem_type", "OTHER")
            components = classification.get("components", [])
            # Use first component as primary
            component = components[0] if components else "general"

        # Create category key: PROBLEM_TYPE_component
        category_key = f"{problem_type}_{component}"
        grouped[category_key].append(ticket)

    # Sort by size (largest groups first)
    grouped = dict(sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True))

    logger.info(f"  Created {len(grouped)} category groups")
    for category, category_tickets in list(grouped.items())[:10]:
        logger.info(f"    {category}: {len(category_tickets)} tickets")
    if len(grouped) > 10:
        logger.info(f"    ... and {len(grouped) - 10} more categories")

    return grouped


def write_category_yaml(
    category_key: str,
    tickets: list,
    output_dir: Path,
    classifications: dict,
):
    """Write category-based mini-group YAML.

    Args:
        category_key: Category identifier (e.g., EOL_UNSUPPORTED_containers)
        tickets: List of tickets in this category
        output_dir: Output directory
        classifications: Classification data for metadata
    """
    ticket_count = len(tickets)
    problem_type, component = category_key.rsplit("_", 1)

    # Filename: CATEGORY_component_Ntickets.yaml
    filename = f"{category_key}_{ticket_count}ticket{'s' if ticket_count > 1 else ''}.yaml"
    output_file = output_dir / filename

    # Build header
    header = (
        f"# Category: {problem_type}\n" f"# Component: {component}\n" f"# Tickets: {ticket_count}\n"
    )

    if ticket_count == 1:
        header += "# Type: Singleton - unique ticket with no similar tickets\n"
    else:
        header += (
            f"# Type: Mini-pattern - {ticket_count} similar tickets (below min pattern size)\n"
        )

    # Add ticket IDs for reference
    ticket_ids = [t.get("conversation_group_id") for t in tickets]
    header += f"# Ticket IDs: {', '.join(ticket_ids)}\n"

    # Write YAML
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n")
        yaml.dump(tickets, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"  ✅ {filename}")


def main():
    """Main split workflow."""
    parser = argparse.ArgumentParser(
        description="Split ungrouped tickets into category-based mini-groups"
    )

    parser.add_argument(
        "--ungrouped",
        type=Path,
        default=Path("config/patterns/UNGROUPED.yaml"),
        help="Path to UNGROUPED.yaml (default: config/patterns/UNGROUPED.yaml)",
    )
    parser.add_argument(
        "--classifications",
        type=Path,
        default=Path("config/tickets_with_patterns.yaml"),
        help="Path to tickets_with_patterns.yaml (default: config/tickets_with_patterns.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("config/ungrouped"),
        help="Output directory for category YAMLs (default: config/ungrouped)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.ungrouped.exists():
        logger.error(f"UNGROUPED.yaml not found: {args.ungrouped}")
        sys.exit(1)

    if not args.classifications.exists():
        logger.error(f"Classifications file not found: {args.classifications}")
        sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    classifications = load_classifications(args.classifications)
    ungrouped_tickets = load_ungrouped_tickets(args.ungrouped)

    # Group by category
    grouped = group_by_category(ungrouped_tickets, classifications)

    # Write category YAMLs
    logger.info(f"Writing category YAMLs to {args.output_dir}...")
    for category_key, category_tickets in grouped.items():
        write_category_yaml(category_key, category_tickets, args.output_dir, classifications)

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SPLIT COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Total category groups: {len(grouped)}")
    logger.info("")

    # Category breakdown
    singletons = sum(1 for tickets in grouped.values() if len(tickets) == 1)
    pairs = sum(1 for tickets in grouped.values() if len(tickets) == 2)
    triplets = sum(1 for tickets in grouped.values() if len(tickets) == 3)

    logger.info("Category breakdown:")
    logger.info(f"  Singletons (1 ticket): {singletons}")
    logger.info(f"  Pairs (2 tickets): {pairs}")
    logger.info(f"  Triplets (3 tickets): {triplets}")
    logger.info("")

    # Problem type summary
    problem_types = defaultdict(int)
    for category_key, category_tickets in grouped.items():
        problem_type = category_key.rsplit("_", 1)[0]
        problem_types[problem_type] += len(category_tickets)

    logger.info("Tickets by problem type:")
    for problem_type, count in sorted(problem_types.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {problem_type}: {count} tickets")
    logger.info("")

    logger.info("Next steps:")
    logger.info("  1. Review category groups:")
    logger.info(f"       ls -lh {args.output_dir}/")
    logger.info("  2. Fix a mini-pattern:")
    logger.info(f"       cd {args.output_dir.parent.parent}")
    logger.info("       ./runners/fix.sh <category-name>")
    logger.info("  3. Or batch fix all ungrouped (see runners/split_ungrouped.sh output)")
    logger.info("")


if __name__ == "__main__":
    main()
