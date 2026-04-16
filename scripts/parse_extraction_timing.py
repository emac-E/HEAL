#!/usr/bin/env python3
"""Parse extraction logs to extract timing data per ticket.

Parses logs from extract_jira_tickets.py to calculate:
- Time per ticket (ms)
- Average time
- Statistics for estimation

Usage:
    # From log file
    python scripts/parse_extraction_timing.py extraction.log

    # From stdin
    tail -f extraction.log | python scripts/parse_extraction_timing.py -

    # Output JSON for programmatic use
    python scripts/parse_extraction_timing.py extraction.log --json timing_data.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def parse_timestamp(line: str) -> Optional[datetime]:
    """Extract timestamp from log line.

    Args:
        line: Log line with format "YYYY-MM-DD HH:MM:SS,mmm - ..."

    Returns:
        datetime object or None
    """
    # Match format: "2026-04-15 02:19:35,123 - ..."
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
    if match:
        timestamp_str = match.group(1)
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
    return None


def parse_ticket_id(line: str) -> Optional[str]:
    """Extract ticket ID from processing line.

    Args:
        line: Log line

    Returns:
        Ticket ID (e.g., "RSPEED-2833") or None
    """
    # Match: "[1/50] Processing RSPEED-2833"
    match = re.search(r"Processing (RSPEED-\d+)", line)
    if match:
        return match.group(1)
    return None


def parse_extraction_log(log_file: Path) -> Dict[str, int]:
    """Parse extraction log to get timing per ticket.

    Args:
        log_file: Path to log file (or '-' for stdin)

    Returns:
        Dict mapping ticket_id → duration_ms
    """
    if str(log_file) == "-":
        lines = sys.stdin.readlines()
    else:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()

    timings = {}
    ticket_starts = {}

    for line in lines:
        timestamp = parse_timestamp(line)
        if not timestamp:
            continue

        # Check for start marker
        ticket_id = parse_ticket_id(line)
        if ticket_id:
            ticket_starts[ticket_id] = timestamp
            continue

        # Check for end marker: "💾 Saved to"
        if "💾 Saved to" in line:
            # Find most recent ticket ID
            for tid, start_time in reversed(list(ticket_starts.items())):
                if tid not in timings:
                    duration_ms = int((timestamp - start_time).total_seconds() * 1000)
                    timings[tid] = duration_ms
                    break

    return timings


def calculate_statistics(timings: Dict[str, int]) -> Dict[str, float]:
    """Calculate timing statistics.

    Args:
        timings: Dict mapping ticket_id → duration_ms

    Returns:
        Statistics dict
    """
    if not timings:
        return {}

    durations = list(timings.values())
    durations.sort()

    n = len(durations)
    total_ms = sum(durations)
    avg_ms = total_ms / n

    # Percentiles
    p50_ms = durations[n // 2]
    p90_ms = durations[int(n * 0.9)]
    p95_ms = durations[int(n * 0.95)]

    return {
        "total_tickets": n,
        "total_time_ms": total_ms,
        "total_time_min": total_ms / 60000,
        "avg_ms": avg_ms,
        "avg_min": avg_ms / 60000,
        "min_ms": durations[0],
        "max_ms": durations[-1],
        "p50_ms": p50_ms,
        "p90_ms": p90_ms,
        "p95_ms": p95_ms,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse extraction logs to extract timing data"
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to log file (or '-' for stdin)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Output JSON file with timing data",
    )
    parser.add_argument(
        "--show-tickets",
        action="store_true",
        help="Show per-ticket timings",
    )

    args = parser.parse_args()

    # Parse log
    print(f"Parsing log: {args.log_file}", file=sys.stderr)
    timings = parse_extraction_log(args.log_file)

    if not timings:
        print("No timing data found in log!", file=sys.stderr)
        return

    # Calculate statistics
    stats = calculate_statistics(timings)

    # Display results
    print("\n" + "="*80)
    print("EXTRACTION TIMING ANALYSIS")
    print("="*80)
    print(f"Total tickets: {stats['total_tickets']}")
    print(f"Total time: {stats['total_time_min']:.1f} minutes")
    print(f"\nPer-ticket timing:")
    print(f"  Average: {stats['avg_ms']:.0f}ms ({stats['avg_min']:.2f} min)")
    print(f"  Median (P50): {stats['p50_ms']:.0f}ms")
    print(f"  P90: {stats['p90_ms']:.0f}ms")
    print(f"  P95: {stats['p95_ms']:.0f}ms")
    print(f"  Min: {stats['min_ms']:.0f}ms")
    print(f"  Max: {stats['max_ms']:.0f}ms")

    # Show per-ticket if requested
    if args.show_tickets:
        print("\nPer-ticket timings:")
        for ticket_id, duration_ms in sorted(timings.items()):
            print(f"  {ticket_id}: {duration_ms}ms ({duration_ms/60000:.2f} min)")

    # Save JSON if requested
    if args.json:
        output = {
            "stats": stats,
            "timings": {
                ticket_id: duration_ms
                for ticket_id, duration_ms in sorted(timings.items())
            },
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved timing data to: {args.json}")


if __name__ == "__main__":
    main()
