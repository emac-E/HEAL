#!/usr/bin/env bash
# Pattern Discovery - Cluster similar JIRA tickets for batch fixing
#
# This script analyzes extracted tickets to discover common patterns that can
# be fixed together. Instead of fixing 68 tickets individually, patterns enable
# batch fixes (e.g., fix 1 pattern → validates against 15 similar tickets).
#
# How it works:
# 1. Classifies tickets by problem type, components, RHEL versions
# 2. Discovers patterns (≥3 similar tickets per pattern)
# 3. Tags tickets with pattern_id
# 4. Generates pattern report for batch fixing
#
# Features:
# - Automatic OUT_OF_SCOPE filtering (skips meta-tickets)
# - Incremental checkpointing (resume on crash)
# - Hierarchical batching (handles large ticket sets)
#
# Usage:
#   ./runners/pattern.sh                    # Default (min 3 tickets per pattern)
#   ./runners/pattern.sh --min-size 5       # Require 5+ tickets per pattern
#   ./runners/pattern.sh --fresh            # Ignore checkpoints, start fresh

set -e  # Exit on error

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
INPUT="config/extracted_tickets.yaml"
OUTPUT_TAGGED="config/tickets_with_patterns.yaml"
OUTPUT_REPORT="config/patterns_report.json"
MIN_PATTERN_SIZE=3
BATCH_SIZE=15
FRESH_FLAG=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            INPUT="$2"
            shift 2
            ;;
        --output-tagged)
            OUTPUT_TAGGED="$2"
            shift 2
            ;;
        --output-report)
            OUTPUT_REPORT="$2"
            shift 2
            ;;
        --min-size)
            MIN_PATTERN_SIZE="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --fresh)
            FRESH_FLAG="--fresh"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --input PATH          Input YAML with extracted tickets (default: config/extracted_tickets.yaml)"
            echo "  --output-tagged PATH  Output YAML with pattern tags (default: config/tickets_with_patterns.yaml)"
            echo "  --output-report PATH  Output JSON pattern report (default: config/patterns_report.json)"
            echo "  --min-size N          Minimum tickets per pattern (default: 3)"
            echo "  --batch-size N        Max tickets per Claude SDK call (default: 15)"
            echo "  --fresh               Ignore checkpoints, start fresh"
            echo "  --help                Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                           # Default (min 3 tickets per pattern)"
            echo "  $0 --min-size 5              # Require 5+ tickets per pattern"
            echo "  $0 --batch-size 15           # Reduce batch size if 30 fails"
            echo "  $0 --fresh                   # Start fresh (ignore checkpoints)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

# Print banner
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}   HEAL - Pattern Discovery for Batch Fixing${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Input:${NC} $INPUT"
echo -e "${BLUE}Min pattern size:${NC} $MIN_PATTERN_SIZE tickets"
echo -e "${BLUE}Batch size:${NC} $BATCH_SIZE tickets per Claude SDK call"
[ -n "$FRESH_FLAG" ] && echo -e "${BLUE}Mode:${NC} Fresh (ignore checkpoints)" || echo -e "${BLUE}Mode:${NC} Resume from checkpoints"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check input file exists
if [ ! -f "$INPUT" ]; then
    echo -e "${YELLOW}⚠️  Input file not found: $INPUT${NC}"
    echo ""
    echo "Run extraction first:"
    echo "  ./runners/extract.sh"
    exit 1
fi

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    uv sync --group dev
fi

# Run pattern discovery
echo -e "${BOLD}${GREEN}Starting pattern discovery...${NC}"
echo ""
echo "Pipeline:"
echo "  Stage 1: Classify tickets"
echo "    → Extract problem type, components, RHEL versions"
echo "    → Filter OUT_OF_SCOPE tickets automatically"
echo "    → Checkpoint saved after classification"
echo ""
echo "  Stage 2: Discover patterns"
echo "    → Group similar tickets (≥${MIN_PATTERN_SIZE} tickets per pattern)"
echo "    → Identify common themes and root causes"
echo "    → Generate verification queries"
echo "    → Checkpoint saved after discovery"
echo ""
echo "  Stage 3: Save outputs"
echo "    → Tagged YAML (tickets with pattern_id)"
echo "    → Pattern report (for batch fixing)"
echo ""

# Build command
CMD="uv run python src/heal/pattern_discovery/discover_ticket_patterns.py"
CMD="$CMD --input \"$INPUT\""
CMD="$CMD --output-tagged \"$OUTPUT_TAGGED\""
CMD="$CMD --output-report \"$OUTPUT_REPORT\""
CMD="$CMD --min-pattern-size $MIN_PATTERN_SIZE"
CMD="$CMD --batch-size $BATCH_SIZE"
[ -n "$FRESH_FLAG" ] && CMD="$CMD $FRESH_FLAG"

# Execute
eval "$CMD"

# Summary
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}   Pattern Discovery Complete${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Show results
if [ -f "$OUTPUT_REPORT" ]; then
    echo -e "${BOLD}Results:${NC}"
    python3 << EOF
import json
with open("$OUTPUT_REPORT") as f:
    data = json.load(f)
    summary = data.get("summary", {})
    patterns = data.get("patterns", [])

print(f"  Total tickets analyzed: {summary.get('total_tickets', 0)}")
print(f"  Patterns found: {summary.get('patterns_found', 0)}")
print(f"  Tickets grouped: {summary.get('tickets_grouped', 0)}")
print(f"  Tickets ungrouped: {summary.get('tickets_ungrouped', 0)}")
print(f"  Grouping rate: {summary.get('grouping_rate', '0%')}")

if patterns:
    print(f"\n  Top patterns:")
    for p in sorted(patterns, key=lambda x: x['ticket_count'], reverse=True)[:5]:
        print(f"    • {p['pattern_id']}: {p['ticket_count']} tickets")
        print(f"      {p['description'][:80]}...")
EOF

    echo ""
    echo -e "${BOLD}Outputs:${NC}"
    echo "  Pattern report: $OUTPUT_REPORT"
    echo "  Tagged tickets: $OUTPUT_TAGGED"
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Review patterns: cat $OUTPUT_REPORT | jq '.patterns'"
    echo "  2. Convert to evaluation format: ./runners/convert.sh"
    echo "  3. Fix patterns in okp-mcp (10-15 tickets per pattern)"
fi
