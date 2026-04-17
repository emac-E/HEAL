#!/usr/bin/env bash
# Debug Fix Runner - Test multi-agent optimization with fixtures (FAST)
#
# This script provides CHECKPOINT-based debugging:
# 1. SKIP slow baseline evaluation (20+ minutes)
# 2. LOAD fixture data from previous run (instant)
# 3. JUMP directly to multi-agent optimization phase
# 4. ITERATE on Solr Expert + Code Expert + Synthesizer logic
#
# Usage:
#   ./runners/debug.sh PATTERN_ID [FIXTURE_FILE]
#
# Examples:
#   ./runners/debug.sh BOOTLOADER_GRUB_ISSUES
#   ./runners/debug.sh BOOTLOADER_GRUB_ISSUES baseline_FIXED.json
#   ./runners/debug.sh BOOTLOADER_GRUB_ISSUES tests/fixtures/custom/data.json
#
# Benefits:
#   - Test in SECONDS instead of 30+ minutes
#   - Perfect for iterating on multi-agent prompts
#   - No need to re-run slow evaluations

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

# Parse arguments
if [ $# -lt 1 ]; then
    echo -e "${YELLOW}Usage: $0 PATTERN_ID [FIXTURE_FILE]${NC}"
    echo ""
    echo "Arguments:"
    echo "  PATTERN_ID      Pattern to debug (e.g., BOOTLOADER_GRUB_ISSUES)"
    echo "  FIXTURE_FILE    Optional: Fixture file name or path (default: baseline_FIXED.json)"
    echo ""
    echo "Examples:"
    echo "  $0 BOOTLOADER_GRUB_ISSUES"
    echo "  $0 BOOTLOADER_GRUB_ISSUES run_001_results.json"
    echo "  $0 BOOTLOADER_GRUB_ISSUES tests/fixtures/custom/data.json"
    echo ""
    echo "Available patterns with fixtures:"
    if [ -d "tests/fixtures" ]; then
        find tests/fixtures -name "*.json" -type f | sed 's|tests/fixtures/||' | sed 's|/.*||' | sort -u | sed 's/^/  - /'
    fi
    exit 1
fi

PATTERN_ID="$1"
FIXTURE_ARG="${2:-baseline_FIXED.json}"

# Print banner
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}   HEAL - Debug Fix Runner (Fixture-Based)${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Resolve fixture path
FIXTURE_PATH=""

# Try multiple directory naming patterns
PATTERN_LOWER="${PATTERN_ID,,}"
PATTERN_UNDER="$(echo $PATTERN_ID | tr '[:upper:]' '[:lower:]' | tr '-' '_')"

# Case 1: Full path provided
if [ -f "$FIXTURE_ARG" ]; then
    FIXTURE_PATH="$FIXTURE_ARG"
# Case 2: Look in pattern's fixture directory (lowercase with dashes)
elif [ -f "tests/fixtures/${PATTERN_LOWER}_pattern/$FIXTURE_ARG" ]; then
    FIXTURE_PATH="tests/fixtures/${PATTERN_LOWER}_pattern/$FIXTURE_ARG"
# Case 3: Look in pattern's fixture directory (lowercase with underscores)
elif [ -f "tests/fixtures/${PATTERN_UNDER}_pattern/$FIXTURE_ARG" ]; then
    FIXTURE_PATH="tests/fixtures/${PATTERN_UNDER}_pattern/$FIXTURE_ARG"
# Case 4: Search all pattern directories for the fixture file
else
    # Find any matching pattern directory
    for dir in tests/fixtures/*_pattern; do
        if [ -f "$dir/$FIXTURE_ARG" ]; then
            # Check if directory name contains pattern ID tokens
            DIR_NAME=$(basename "$dir")
            # Simple heuristic: if most of the pattern ID words appear in dir name, use it
            if [[ "$DIR_NAME" == *"bootloader"* && "$PATTERN_ID" == *"BOOTLOADER"* ]]; then
                FIXTURE_PATH="$dir/$FIXTURE_ARG"
                break
            fi
        fi
    done
fi

if [ -z "$FIXTURE_PATH" ]; then
    echo -e "${YELLOW}⚠️  Fixture file not found!${NC}"
    echo ""
    echo "Searched:"
    echo "  - $FIXTURE_ARG (absolute path)"
    echo "  - tests/fixtures/${PATTERN_LOWER}_pattern/$FIXTURE_ARG"
    echo "  - tests/fixtures/${PATTERN_UNDER}_pattern/$FIXTURE_ARG"
    echo "  - All *_pattern directories"
    echo ""
    echo "Available fixture directories:"
    ls -d tests/fixtures/*_pattern 2>/dev/null | sed 's/^/  - /' || echo "  (none found)"
    echo ""
    echo "Available fixtures in each directory:"
    for dir in tests/fixtures/*_pattern; do
        if [ -d "$dir" ]; then
            echo "  $(basename $dir):"
            ls "$dir"/*.json 2>/dev/null | xargs -n1 basename | sed 's/^/    - /' || echo "    (no JSON files)"
        fi
    done
    exit 1
fi

# Show configuration
echo -e "${BLUE}Pattern:${NC} $PATTERN_ID"
echo -e "${BLUE}Fixture:${NC} $FIXTURE_PATH"
echo -e "${BLUE}Mode:${NC} DEBUG (skip baseline, load from fixture)"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    uv sync --group dev
fi

# Detect okp-mcp root (check common locations)
OKP_MCP_ROOT=""
if [ -d "../okp-mcp" ]; then
    OKP_MCP_ROOT="../okp-mcp"
elif [ -d "../../okp-mcp" ]; then
    OKP_MCP_ROOT="../../okp-mcp"
elif [ -d "/home/emackey/Work/okp-mcp" ]; then
    OKP_MCP_ROOT="/home/emackey/Work/okp-mcp"
fi

if [ -z "$OKP_MCP_ROOT" ]; then
    echo -e "${YELLOW}⚠️  okp-mcp directory not found in common locations${NC}"
    echo "Searched: ../okp-mcp, ../../okp-mcp, /home/emackey/Work/okp-mcp"
    echo ""
    echo -e "${YELLOW}Multi-agent Code Expert will be disabled.${NC}"
    echo "To enable, ensure okp-mcp is cloned in a parent directory."
    echo ""
fi

# Build command
CMD="uv run python src/heal/runners/fix_agent_debugger.py --fixture $FIXTURE_PATH"

if [ -n "$OKP_MCP_ROOT" ]; then
    CMD="$CMD --okp-mcp-root $OKP_MCP_ROOT"
    echo -e "${BLUE}OKP-MCP Root:${NC} $OKP_MCP_ROOT"
fi

# Detect eval root (lightspeed-evaluation)
if [ -d "../lightspeed-evaluation" ]; then
    CMD="$CMD --eval-root ../lightspeed-evaluation"
elif [ -d "../../lightspeed-evaluation" ]; then
    CMD="$CMD --eval-root ../../lightspeed-evaluation"
fi

echo ""
echo -e "${BOLD}${GREEN}🚀 Starting debug session...${NC}"
echo -e "${BLUE}This will test multi-agent optimization WITHOUT slow baseline eval${NC}"
echo ""

# Run debugger
PYTHONUNBUFFERED=1 $CMD

echo ""
echo -e "${BOLD}${GREEN}✅ Debug session complete!${NC}"
echo ""
echo -e "${BOLD}💡 Next steps:${NC}"
echo ""
echo "  Option A - Auto-apply and test the fix:"
echo -e "     ${BLUE}./runners/eval_fix.sh $PATTERN_ID --apply${NC}"
echo ""
echo "  Option B - Manually apply and test:"
echo "     1. Edit okp-mcp code based on suggestion above"
echo -e "     2. ${BLUE}./runners/eval_fix.sh $PATTERN_ID${NC}"
echo ""
echo "  Option C - Iterate on multi-agent prompts:"
echo "     1. Edit Solr Expert / Code Expert / Synthesizer prompts"
echo "     2. Re-run: ./runners/debug.sh $PATTERN_ID"
echo ""
echo "  When fix is validated, run full loop:"
echo -e "     ${BLUE}./runners/fix.sh $PATTERN_ID${NC}"
echo ""
