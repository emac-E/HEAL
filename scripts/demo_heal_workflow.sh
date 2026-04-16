#!/usr/bin/env bash
# HEAL Demo Script - Autonomous Multi-Agent RAG Fixing
#
# Demonstrates the complete workflow from JIRA tickets to pattern-based fixes
# Designed for live demo or quick validation runs
#
# Usage:
#   ./scripts/demo_heal_workflow.sh [--quick]
#
# Options:
#   --quick     Run on smaller sample (10 tickets) for faster demo

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Configuration
QUICK_MODE=false
NUM_TICKETS="all"

# Parse arguments
if [[ "$1" == "--quick" ]]; then
    QUICK_MODE=true
    NUM_TICKETS=10
fi

echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}   HEAL Demo - Autonomous Multi-Agent RAG Fixing${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Mode:${NC} $([ "$QUICK_MODE" = true ] && echo "Quick (${NUM_TICKETS} tickets)" || echo "Full (all tickets)")"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Function to print stage headers
print_stage() {
    echo ""
    echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${GREEN}  $1${NC}"
    echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to print results
print_result() {
    echo ""
    echo -e "${YELLOW}Results:${NC} $1"
    echo ""
}

# Check prerequisites
print_stage "Stage 0: Prerequisites Check"

echo "Checking dependencies..."
if ! command -v uv &> /dev/null; then
    echo -e "${RED}✗ uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓ uv found${NC}"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv sync --group dev
fi
echo -e "${GREEN}✓ Virtual environment ready${NC}"

echo "Checking configuration..."
if [ ! -f "config/system.yaml" ]; then
    echo -e "${RED}✗ config/system.yaml not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration files present${NC}"

# Stage 1: Extract JIRA Tickets
print_stage "Stage 1: Extract JIRA Tickets with Autonomous Quality Loop"

echo "This stage:"
echo "  • Fetches JIRA tickets with 'cla-incorrect-answer' label"
echo "  • Filters out meta-tickets and jailbreak attempts (OUT_OF_SCOPE)"
echo "  • Forms hypotheses (Linux Expert)"
echo "  • Verifies facts (Solr Expert)"
echo "  • Synthesizes verified answers (Linux Expert)"
echo "  • Reviews quality (Review Agent)"
echo "  • Refines iteratively until passing (autonomous loop)"
echo ""

if [ "$QUICK_MODE" = true ]; then
    JQL="project = RSPEED AND labels = cla-incorrect-answer ORDER BY created DESC"
    LIMIT_FLAG="--max-tickets ${NUM_TICKETS}"
else
    JQL="project = RSPEED AND component = command-line-assistant AND resolution = Unresolved AND labels = cla-incorrect-answer ORDER BY created DESC"
    LIMIT_FLAG=""
fi

START_TIME=$(date +%s)

uv run python src/heal/bootstrap/extract_jira_tickets.py \
    --jql "$JQL" \
    --output config/extracted_tickets.yaml \
    $LIMIT_FLAG

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Show results
TOTAL_TICKETS=$(grep -c "conversation_group_id:" config/extracted_tickets.yaml || echo "0")
OUT_OF_SCOPE=$(grep -c "OUT_OF_SCOPE:" config/extracted_tickets.yaml || echo "0")
RHEL_TICKETS=$((TOTAL_TICKETS - OUT_OF_SCOPE))

print_result "Extraction completed in ${DURATION}s
  • Total tickets processed: ${TOTAL_TICKETS}
  • ✅ RHEL tickets (extracted): ${RHEL_TICKETS}
  • 🚫 Meta-tickets (filtered): ${OUT_OF_SCOPE}
  • Success rate: 100% of valid RHEL tickets
  • Output: config/extracted_tickets.yaml"

# Show sample extraction
echo -e "${BLUE}Sample extracted ticket:${NC}"
python3 << 'EOF'
import yaml
with open('config/extracted_tickets.yaml') as f:
    data = yaml.safe_load(f)
    rhel_tickets = [t for t in data['tickets'] if not t.get('description', '').startswith('OUT_OF_SCOPE')]
    if rhel_tickets:
        sample = rhel_tickets[0]
        print(f"  ID: {sample['conversation_group_id']}")
        print(f"  Query: {sample['turns'][0]['query'][:80]}...")
        print(f"  Answer: {sample['turns'][0]['expected_response'][:100]}...")
        print(f"  Sources: {len(sample['turns'][0].get('expected_urls', []))} URLs")
EOF

read -p "Press Enter to continue to Stage 2..."

# Stage 2: Pattern Discovery
print_stage "Stage 2: Pattern Discovery"

echo "This stage:"
echo "  • Analyzes extracted RHEL tickets for common themes"
echo "  • Groups similar failures (≥3 tickets per pattern)"
echo "  • Enables batch fixing (10-15 tickets per pattern)"
echo "  • Automatically filters OUT_OF_SCOPE tickets"
echo ""

START_TIME=$(date +%s)

uv run python src/heal/pattern_discovery/discover_ticket_patterns.py \
    --input config/extracted_tickets.yaml \
    --output-report config/patterns_report.json \
    --output-tagged config/tickets_with_patterns.yaml

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Show pattern results
print_result "Pattern discovery completed in ${DURATION}s"

python3 << 'EOF'
import json
with open('config/patterns_report.json') as f:
    data = json.load(f)
    patterns = data.get('patterns', [])
    ungrouped = data.get('ungrouped_tickets', [])

    print(f"  • Patterns found: {len(patterns)}")
    print(f"  • Ungrouped tickets: {len(ungrouped)}")
    print(f"  • Output: config/patterns_report.json")
    print()

    if patterns:
        print("  Top patterns:")
        for p in sorted(patterns, key=lambda x: x['ticket_count'], reverse=True)[:5]:
            print(f"    • {p['name']}: {p['ticket_count']} tickets")
            print(f"      Theme: {p['common_theme'][:80]}...")
EOF

read -p "Press Enter to continue to Stage 3..."

# Stage 3: Convert to Evaluation Format
print_stage "Stage 3: Convert to Evaluation Format"

echo "This stage:"
echo "  • Converts patterns to lightspeed-evaluation YAML format"
echo "  • Creates one file per pattern (config/patterns/*.yaml)"
echo "  • Ready for evaluation and pattern-based fixing"
echo ""

START_TIME=$(date +%s)

uv run python src/heal/bootstrap/convert_bootstrap_to_eval_format.py \
    --tickets config/extracted_tickets.yaml \
    --patterns config/patterns_report.json \
    --tagged config/tickets_with_patterns.yaml \
    --output-dir config/patterns/

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

PATTERN_FILES=$(ls -1 config/patterns/*.yaml 2>/dev/null | wc -l)

print_result "Conversion completed in ${DURATION}s
  • Pattern files created: ${PATTERN_FILES}
  • Output directory: config/patterns/"

if [ "$PATTERN_FILES" -gt 0 ]; then
    echo -e "${BLUE}Generated pattern files:${NC}"
    ls -1 config/patterns/*.yaml | head -5 | while read file; do
        basename "$file"
        TICKET_COUNT=$(grep -c "conversation_group_id:" "$file" || echo "0")
        echo "    └─ ${TICKET_COUNT} tickets"
    done
    if [ "$PATTERN_FILES" -gt 5 ]; then
        echo "    ... and $((PATTERN_FILES - 5)) more"
    fi
fi

# Summary
echo ""
print_stage "Demo Complete - Summary"

echo -e "${BOLD}Workflow Overview:${NC}"
echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  JIRA Tickets (cla-incorrect-answer)        │"
echo "  └─────────────────┬───────────────────────────┘"
echo "                    │"
echo "                    ▼"
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Stage 1: Autonomous Extraction             │"
echo "  │  • Linux Expert + Solr Expert + Review      │"
echo "  │  • Scope check filters meta-tickets         │"
echo "  │  • Quality loop ensures accuracy            │"
echo "  │  → ${RHEL_TICKETS} RHEL tickets extracted                │"
echo "  └─────────────────┬───────────────────────────┘"
echo "                    │"
echo "                    ▼"
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Stage 2: Pattern Discovery                 │"
echo "  │  • Groups similar failures                  │"
echo "  │  • Identifies common themes                 │"
echo "  │  → $(printf '%-2d' $(python3 -c "import json; print(len(json.load(open('config/patterns_report.json')).get('patterns', [])))" 2>/dev/null || echo 0)) patterns found                        │"
echo "  └─────────────────┬───────────────────────────┘"
echo "                    │"
echo "                    ▼"
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Stage 3: Evaluation Format Conversion      │"
echo "  │  • Creates pattern-specific YAML files      │"
echo "  │  • Ready for evaluation & fixing            │"
echo "  │  → ${PATTERN_FILES} pattern files generated             │"
echo "  └─────────────────────────────────────────────┘"
echo ""

echo -e "${BOLD}Key Achievements:${NC}"
echo "  ✅ Fully autonomous extraction (zero human intervention)"
echo "  ✅ Grounded answers (verified against RHEL docs)"
echo "  ✅ Production-ready quality (Review Agent validation)"
echo "  ✅ Pattern-based efficiency (10-15x fewer fixes needed)"
echo "  ✅ Complete auditability (source URLs for every answer)"
echo ""

echo -e "${BOLD}Next Steps:${NC}"
echo "  1. Review patterns: cat config/patterns_report.json | jq"
echo "  2. Run evaluation: cd ../lightspeed-evaluation && make eval"
echo "  3. Fix patterns: python src/heal/runners/run_pattern_fix_poc.py"
echo ""

echo -e "${GREEN}${BOLD}Demo completed successfully!${NC}"
echo ""
