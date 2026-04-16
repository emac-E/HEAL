#!/usr/bin/env bash
# Full JIRA Ticket Extraction with Multi-Agent Quality Loop
#
# This script extracts all RSPEED cla-incorrect-answer tickets using:
# - Scope check FIRST (filters meta-tickets, jailbreaks, non-RHEL)
# - Linux Expert Agent (forms hypotheses with RHEL expertise)
# - Solr Expert Agent (verifies against actual documentation)
# - Review Agent (autonomous quality loop with iterative refinement)
#
# Features:
# - Skips OUT_OF_SCOPE tickets automatically (no expensive processing)
# - Incremental saving (won't lose progress if crashes)
# - Quality-verified answers only (Review Agent validation)
#
# Usage:
#   ./runners/extract.sh                    # Full extraction (force rebuild)
#   ./runners/extract.sh --append           # Append mode (skip existing)
#   ./runners/extract.sh --max-tickets 10   # Quick test (10 tickets)

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
MODE="--force-rebuild"
MAX_TICKETS=""
JQL="project = RSPEED AND component = command-line-assistant AND resolution = Unresolved AND labels = cla-incorrect-answer ORDER BY created DESC"
OUTPUT="config/extracted_tickets.yaml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --append)
            MODE=""
            shift
            ;;
        --max-tickets)
            MAX_TICKETS="--max-tickets $2"
            shift 2
            ;;
        --jql)
            JQL="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --append              Append mode (skip existing tickets)"
            echo "  --max-tickets N       Limit to N tickets (for testing)"
            echo "  --jql 'QUERY'         Custom JQL query"
            echo "  --output PATH         Output file path (default: config/extracted_tickets.yaml)"
            echo "  --help                Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                           # Full extraction (force rebuild)"
            echo "  $0 --append                  # Append new tickets only"
            echo "  $0 --max-tickets 10          # Test with 10 tickets"
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
echo -e "${BOLD}   HEAL - Multi-Agent JIRA Ticket Extraction${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Mode:${NC} $([ -z "$MODE" ] && echo "Append (skip existing)" || echo "Force rebuild (start fresh)")"
[ -n "$MAX_TICKETS" ] && echo -e "${BLUE}Limit:${NC} ${MAX_TICKETS##--max-tickets }" || echo -e "${BLUE}Limit:${NC} All tickets"
echo -e "${BLUE}Output:${NC} $OUTPUT"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Backup existing file if force rebuild
if [[ -n "$MODE" ]] && [[ -f "$OUTPUT" ]]; then
    BACKUP="${OUTPUT%.yaml}_backup_$(date +%Y%m%d_%H%M%S).yaml"
    echo -e "${YELLOW}⚠️  Force rebuild mode: backing up existing file${NC}"
    cp "$OUTPUT" "$BACKUP"
    echo -e "${GREEN}✓ Backup created: $BACKUP${NC}"
    echo ""
fi

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    uv sync --group dev
fi

# Run extraction
echo -e "${BOLD}${GREEN}Starting extraction...${NC}"
echo ""
echo "Pipeline:"
echo "  1. Fetch tickets from JIRA"
echo "  2. Scope check (filter meta-tickets, jailbreaks)"
echo "  3. For RHEL tickets:"
echo "     → Linux Expert forms hypothesis"
echo "     → Solr Expert verifies against docs"
echo "     → Linux Expert synthesizes answer"
echo "     → Review Agent validates quality"
echo "     → Refine iteratively until passing (≤3 iterations)"
echo "  4. Save incrementally (won't lose progress)"
echo ""

# Build command
CMD="uv run python src/heal/bootstrap/extract_jira_tickets.py"
CMD="$CMD --jql \"$JQL\""
CMD="$CMD --output \"$OUTPUT\""
[ -n "$MODE" ] && CMD="$CMD $MODE"
[ -n "$MAX_TICKETS" ] && CMD="$CMD $MAX_TICKETS"

# Execute
eval "$CMD"

# Summary
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}   Extraction Complete${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Show results
if [ -f "$OUTPUT" ]; then
    TOTAL=$(grep -c "conversation_group_id:" "$OUTPUT" || echo "0")
    OUT_OF_SCOPE=$(python3 << EOF
import yaml
with open("$OUTPUT") as f:
    data = yaml.safe_load(f)
    out_of_scope = [t for t in data['tickets'] if t.get('description', '').startswith('OUT_OF_SCOPE')]
    print(len(out_of_scope))
EOF
)
    RHEL_TICKETS=$((TOTAL - OUT_OF_SCOPE))

    echo -e "${BOLD}Results:${NC}"
    echo "  Total tickets: $TOTAL"
    echo "  ✅ RHEL tickets (extracted): $RHEL_TICKETS"
    echo "  🚫 OUT_OF_SCOPE (filtered): $OUT_OF_SCOPE"
    echo ""
    echo -e "${BOLD}Output:${NC} $OUTPUT"
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Review extracted tickets: cat $OUTPUT | less"
    echo "  2. Run pattern discovery: ./runners/discover_patterns.sh"
fi
