#!/usr/bin/env bash
# Quick Fix Evaluation - Test if a code change improves metrics
#
# This script provides FAST fix validation (5-10 min instead of 30+ min):
# 1. Load baseline metrics from fixture
# 2. Apply code change to okp-mcp (manual)
# 3. Restart lscore-deploy to pick up changes
# 4. Run QUICK evaluation (2 runs instead of 6)
# 5. Compare answer_correctness before/after
# 6. Report improvement
#
# Usage:
#   ./runners/eval_fix.sh PATTERN_ID [OPTIONS]
#
# Examples:
#   # Workflow: Get suggestion → Apply fix → Test
#   ./runners/debug.sh BOOTLOADER_GRUB_ISSUES
#   # (manually edit okp-mcp code based on suggestion)
#   ./runners/eval_fix.sh BOOTLOADER_GRUB_ISSUES
#
#   # Quick 2-run test (default)
#   ./runners/eval_fix.sh BOOTLOADER_GRUB_ISSUES
#
#   # More runs for confidence
#   ./runners/eval_fix.sh BOOTLOADER_GRUB_ISSUES --runs 4

set -e  # Exit on error

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
NUM_RUNS=2
FIXTURE_NAME="baseline_FIXED.json"
APPLY_FIX=false

# Parse arguments
if [ $# -lt 1 ]; then
    echo -e "${YELLOW}Usage: $0 PATTERN_ID [OPTIONS]${NC}"
    echo ""
    echo "Arguments:"
    echo "  PATTERN_ID      Pattern to test (e.g., BOOTLOADER_GRUB_ISSUES)"
    echo ""
    echo "Options:"
    echo "  --apply         Automatically apply the suggested code change"
    echo "  --runs N        Number of evaluation runs (default: 2 for speed)"
    echo "  --fixture FILE  Fixture file with baseline metrics (default: baseline_FIXED.json)"
    echo ""
    echo "Workflow:"
    echo "  1. ./runners/debug.sh PATTERN_ID           # Get multi-agent suggestion"
    echo "  2. ./runners/eval_fix.sh PATTERN_ID --apply  # Auto-apply fix and test"
    echo ""
    echo "Or manual workflow:"
    echo "  1. ./runners/debug.sh PATTERN_ID           # Get suggestion"
    echo "  2. Manually edit okp-mcp code"
    echo "  3. ./runners/eval_fix.sh PATTERN_ID        # Test manually applied fix"
    exit 1
fi

PATTERN_ID="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --apply)
            APPLY_FIX=true
            shift
            ;;
        --runs)
            NUM_RUNS="$2"
            shift 2
            ;;
        --fixture)
            FIXTURE_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Print banner
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}   HEAL - Quick Fix Evaluation${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Find fixture
FIXTURE_PATH=""
for dir in tests/fixtures/*_pattern; do
    if [ -f "$dir/$FIXTURE_NAME" ]; then
        DIR_NAME=$(basename "$dir")
        if [[ "$DIR_NAME" == *"bootloader"* && "$PATTERN_ID" == *"BOOTLOADER"* ]]; then
            FIXTURE_PATH="$dir/$FIXTURE_NAME"
            break
        fi
    fi
done

if [ -z "$FIXTURE_PATH" ]; then
    echo -e "${RED}❌ Fixture file not found: $FIXTURE_NAME${NC}"
    exit 1
fi

# Check virtual environment
if [ ! -d ".venv" ]; then
    uv sync --group dev
fi

# Apply fix if requested
if [ "$APPLY_FIX" = true ]; then
    echo -e "${BOLD}${GREEN}Step 1: Apply suggested code change${NC}"
    echo ""

    # Look for suggestion file
    SUGGESTION_FILE=".diagnostics/$PATTERN_ID/suggestion.json"

    if [ ! -f "$SUGGESTION_FILE" ]; then
        echo -e "${RED}❌ Suggestion file not found: $SUGGESTION_FILE${NC}"
        echo ""
        echo "Did you run debug.sh first?"
        echo -e "  ${BLUE}./runners/debug.sh $PATTERN_ID${NC}"
        echo ""
        exit 1
    fi

    # Detect okp-mcp root
    OKP_MCP_ROOT=""
    if [ -d "../okp-mcp" ]; then
        OKP_MCP_ROOT="$(cd ../okp-mcp && pwd)"
    elif [ -d "../../okp-mcp" ]; then
        OKP_MCP_ROOT="$(cd ../../okp-mcp && pwd)"
    elif [ -d "/home/emackey/Work/okp-mcp" ]; then
        OKP_MCP_ROOT="/home/emackey/Work/okp-mcp"
    fi

    if [ -z "$OKP_MCP_ROOT" ]; then
        echo -e "${RED}❌ okp-mcp directory not found${NC}"
        echo "Searched: ../okp-mcp, ../../okp-mcp, /home/emackey/Work/okp-mcp"
        exit 1
    fi

    echo "📝 Applying suggestion from: $SUGGESTION_FILE"
    echo "📁 Target repository: $OKP_MCP_ROOT"
    echo ""

    # Apply using Python script
    uv run python src/heal/runners/apply_suggestion.py \
        --suggestion "$SUGGESTION_FILE" \
        --okp-mcp-root "$OKP_MCP_ROOT"

    if [ $? -ne 0 ]; then
        echo ""
        echo -e "${RED}❌ Failed to apply suggestion${NC}"
        echo ""
        echo "You can try manually editing the code based on the suggestion:"
        echo -e "  ${BLUE}cat $SUGGESTION_FILE${NC}"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}✅ Code change applied successfully!${NC}"
    echo ""
    echo "Review the changes:"
    echo -e "  ${BLUE}cd $OKP_MCP_ROOT && git diff${NC}"
    echo ""

    # Give user a chance to review before continuing
    echo -e "${YELLOW}Press Enter to continue with evaluation, or Ctrl+C to abort${NC}"
    read -r
    echo ""
fi

# Run Python evaluation script
PYTHONUNBUFFERED=1 uv run python src/heal/runners/quick_eval_fix.py "$PATTERN_ID" \
    --baseline-fixture "$FIXTURE_PATH" \
    --runs "$NUM_RUNS"

echo ""
echo -e "${BOLD}💡 Next steps:${NC}"
echo ""
echo "  If improvement:"
echo -e "    ${BLUE}git add -A && git commit -m 'Apply fix for $PATTERN_ID'${NC}"
echo -e "    ${BLUE}./runners/fix.sh $PATTERN_ID${NC}  # Full validation (6 runs)"
echo ""
echo "  If regression or no change:"
echo -e "    ${BLUE}git restore .${NC}  # Revert changes"
echo "    Review multi-agent risks and try different approach"
echo ""
