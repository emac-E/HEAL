#!/usr/bin/env python3
"""Refine existing extracted tickets in-place using stored sources.

Attempts to fix failing tickets by re-synthesizing answers using:
- The stored expected_urls (fetches content again)
- Review feedback from quality checks
- Iterative refinement loop

Tickets that still fail after max iterations are marked for re-extraction.

Usage:
    # Refine all failing tickets
    python src/heal/bootstrap/refine_extracted_tickets.py \
        --input config/extracted_tickets.yaml \
        --output config/extracted_tickets_refined.yaml \
        --failed-tickets failed_tickets.txt

    # More aggressive refinement
    python src/heal/bootstrap/refine_extracted_tickets.py \
        --input config/extracted_tickets.yaml \
        --max-iterations 5
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

# Add src/ to sys.path for imports
SRC_ROOT = Path(__file__).parent.parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from heal.core import AnswerReviewAgent, LinuxExpertAgent, SolrExpertAgent  # noqa: E402
from heal.core.solr_expert import VerificationQuery  # noqa: E402

# HEAL repository root for file paths
REPO_ROOT = SRC_ROOT.parent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def fetch_docs_from_solr(sources: list[str], solr_expert: SolrExpertAgent):
    """Fetch documents from Solr using stored URLs.

    Args:
        sources: List of OKP URLs
        solr_expert: Solr Expert Agent

    Returns:
        VerificationResult with found_docs
    """
    # Create verification queries for each URL
    verification_queries = [
        VerificationQuery(
            query=url, context=f"Fetch documentation from {url}", expected_doc_type="documentation"
        )
        for url in sources
    ]

    # Use Solr Expert's existing search method
    return await solr_expert.search_for_verification(verification_queries)


async def refine_ticket(
    ticket: dict[str, Any],
    linux_expert: LinuxExpertAgent,
    solr_expert: SolrExpertAgent,
    reviewer: AnswerReviewAgent,
    max_iterations: int = 3,
) -> tuple[dict[str, Any], bool]:
    """Refine a ticket's answer using stored sources.

    Args:
        ticket: Ticket data (conversation dict)
        linux_expert: Linux Expert for synthesis
        solr_expert: Solr Expert for document retrieval
        reviewer: Review Agent for quality checks
        max_iterations: Maximum refinement iterations

    Returns:
        (updated_ticket, needs_reextraction)
    """
    conv_id = ticket.get("conversation_group_id", "UNKNOWN")

    if not ticket.get("turns") or len(ticket["turns"]) == 0:
        logger.warning(f"{conv_id}: No turns, skipping")
        return ticket, False

    turn = ticket["turns"][0]
    query = turn.get("query", "")
    current_answer = turn.get("expected_response", "")
    sources = turn.get("expected_urls", [])

    # Initial review
    review = await reviewer.review_answer(query, current_answer, sources)

    if review.passes:
        logger.info(f"{conv_id}: Already passes (score: {review.score:.2f}), skipping")
        return ticket, False

    logger.info(f"{conv_id}: Failed review (score: {review.score:.2f}), refining...")
    for issue in review.issues:
        logger.info(f"  - {issue}")

    # Fetch docs from Solr using stored URLs
    logger.info(f"{conv_id}: Fetching {len(sources)} source documents from Solr...")
    verification = await fetch_docs_from_solr(sources, solr_expert)

    if not verification.found_docs:
        logger.warning(f"{conv_id}: No docs fetched from Solr, needs re-extraction")
        return ticket, True

    logger.info(f"  Found: {len(verification.found_docs)} documents")
    logger.info(f"  Confidence: {verification.confidence}")

    # Build minimal hypothesis for synthesis (we don't have the original)
    hypothesis = {
        "query": query,
        "hypothesis": "Answer needs refinement based on quality review",
        "verification_queries": [],
    }

    # Iterative refinement
    best_answer = current_answer
    best_score = review.score

    for iteration in range(max_iterations):
        logger.info(f"{conv_id}: Refinement iteration {iteration + 1}/{max_iterations}")

        # Check if reviewer provided a suggested fix
        if review.suggested_fix and len(review.suggested_fix.strip()) > 0:
            logger.info("  Using reviewer's suggested fix")
            improved = review.suggested_fix
        else:
            # Fall back to re-synthesis with feedback
            logger.info(f"  Re-synthesizing with feedback: {len(review.issues)} issues")
            synthesis_result = await linux_expert._synthesize_verified_answer(
                key=conv_id,
                summary=ticket.get("description", ""),
                description="",
                hypothesis=hypothesis,
                verification=verification,
                feedback=review.issues if iteration > 0 else None,
            )

            improved = synthesis_result["expected_response"]

            # DEBUG: Check if synthesis returned empty
            if not improved or len(improved.strip()) == 0:
                logger.warning("  ⚠️  Synthesis returned empty response!")
                logger.warning(f"  Synthesis result keys: {synthesis_result.keys()}")
                logger.warning(f"  Confidence: {synthesis_result.get('confidence')}")
                logger.warning(f"  Reasoning: {synthesis_result.get('reasoning', '')[:200]}")

        # Review improved answer
        review = await reviewer.review_answer(query, improved, sources)
        logger.info(f"  Score: {review.score:.2f}, Passes: {review.passes}")

        if review.score > best_score:
            best_answer = improved
            best_score = review.score

        if review.passes:
            logger.info(f"{conv_id}: ✅ Passed after {iteration + 1} iterations")
            turn["expected_response"] = best_answer
            return ticket, False

        # review object is updated for next iteration (used at top of loop)

    # Max iterations reached
    if best_score >= 0.6:
        # Improved but not passing - keep it
        logger.info(
            f"{conv_id}: ⚠️  Improved to {best_score:.2f} but not passing, keeping best attempt"
        )
        turn["expected_response"] = best_answer
        return ticket, False
    else:
        # Still terrible - needs re-extraction
        logger.warning(f"{conv_id}: ❌ Still failing ({best_score:.2f}), needs re-extraction")
        return ticket, True


async def main():
    """Main refinement workflow."""
    parser = argparse.ArgumentParser(description="Refine existing extracted tickets in-place")
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "config" / "extracted_tickets.yaml",
        help="Input extracted tickets YAML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output refined tickets YAML (default: overwrites input)",
    )
    parser.add_argument(
        "--failed-tickets",
        type=Path,
        default=REPO_ROOT / "config" / "failed_tickets.txt",
        help="Output file for tickets needing re-extraction",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum refinement iterations per ticket (default: 3)",
    )
    parser.add_argument(
        "--tickets",
        type=str,
        help="Comma-separated ticket keys to refine (default: all failing)",
    )

    args = parser.parse_args()

    if not args.output:
        args.output = args.input

    # Load tickets
    logger.info(f"Loading tickets from {args.input}")
    with open(args.input, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "tickets" not in data:
        logger.error("Invalid YAML: missing 'tickets' key")
        return

    tickets = data["tickets"]
    logger.info(f"Loaded {len(tickets)} tickets")

    # Filter to specific tickets if requested
    if args.tickets:
        ticket_keys = [k.strip() for k in args.tickets.split(",")]
        tickets = [t for t in tickets if t.get("conversation_group_id") in ticket_keys]
        logger.info(f"Filtered to {len(tickets)} tickets: {ticket_keys}")

    # Initialize agents
    logger.info("Initializing agents...")
    solr_expert = SolrExpertAgent()
    linux_expert = LinuxExpertAgent()
    reviewer = AnswerReviewAgent()

    # Refine tickets
    logger.info(f"\n{'='*80}")
    logger.info(f"Refining {len(tickets)} tickets")
    logger.info(f"{'='*80}\n")

    refined_count = 0
    needs_reextraction = []

    import time

    start_time_ms = int(time.perf_counter() * 1000)

    for i, ticket in enumerate(tickets, 1):
        conv_id = ticket.get("conversation_group_id", f"ticket_{i}")
        logger.info(f"\n[{i}/{len(tickets)}] Refining {conv_id}")

        try:
            updated_ticket, needs_reextract = await refine_ticket(
                ticket, linux_expert, solr_expert, reviewer, max_iterations=args.max_iterations
            )

            # Update in place
            idx = data["tickets"].index(ticket)
            data["tickets"][idx] = updated_ticket

            if needs_reextract:
                needs_reextraction.append(conv_id)
            else:
                refined_count += 1

            # Save incrementally after each ticket (prevent loss on crash/Ctrl+C)
            logger.info(f"  💾 Saving progress to {args.output}")
            with open(args.output, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Progress reporting
            elapsed_ms = int(time.perf_counter() * 1000) - start_time_ms
            avg_ms_per_ticket = elapsed_ms / i
            remaining_tickets = len(tickets) - i
            eta_ms = int(avg_ms_per_ticket * remaining_tickets)
            eta_min = eta_ms / 60000

            percent_complete = (i / len(tickets)) * 100
            logger.info(
                f"  📊 Progress: {i}/{len(tickets)} ({percent_complete:.1f}%) | ETA: {eta_min:.1f} min | Avg: {avg_ms_per_ticket/1000:.1f}s per ticket"
            )

        except Exception as e:
            logger.error(f"  Failed to refine {conv_id}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            needs_reextraction.append(conv_id)

    # Final summary save (data already saved incrementally above)
    logger.info(f"\nFinal save to {args.output}")
    with open(args.output, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    # Save failed tickets list
    if needs_reextraction:
        logger.info(f"Saving {len(needs_reextraction)} failed tickets to {args.failed_tickets}")
        with open(args.failed_tickets, "w", encoding="utf-8") as f:
            f.write(",".join(needs_reextraction))

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("REFINEMENT COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total tickets: {len(tickets)}")
    logger.info(f"✅ Refined successfully: {refined_count}")
    logger.info(f"❌ Need re-extraction: {len(needs_reextraction)}")

    if needs_reextraction:
        logger.info("\nTo re-extract failed tickets:")
        logger.info("  uv run python src/heal/bootstrap/extract_jira_tickets.py \\")
        logger.info(
            f"    --tickets {','.join(needs_reextraction[:5])}{',...' if len(needs_reextraction) > 5 else ''} \\"
        )
        logger.info("    --force-reextract")


if __name__ == "__main__":
    import os

    exit_code = 0
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        exit_code = 1
    finally:
        os._exit(exit_code)
