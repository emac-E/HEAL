#!/usr/bin/env bash
# Split Ungrouped - Organize ungrouped tickets by category into mini-groups
#
# Takes UNGROUPED.yaml (tickets with no pattern) and creates category-based
# mini-groups (1-3 tickets each) for easier fixing and bug tracking.
#
# Uses existing classifications (problem_type, components) to group similar
# tickets together, even if they didn't meet the min pattern size threshold.
#
# Output:
#   - Mini-pattern YAMLs: CATEGORY_component_Ntickets.yaml (2-3 tickets)
#   - Singleton YAMLs: CATEGORY_component_1ticket.yaml (1 ticket)
#
# Benefits:
#   - Category tracking for bug analysis
#   - Pairs can be fixed together (more efficient than singletons)
#   - Easy to see which categories/components have most issues
#
# Usage:
#   ./runners/split_ungrouped.sh                    # Default paths
#   ./runners/split_ungrouped.sh --output-dir out/  # Custom output

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
UNGROUPED_YAML="config/patterns/UNGROUPED.yaml"
CLASSIFICATIONS="config/tickets_with_patterns.yaml"
OUTPUT_DIR="config/ungrouped"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ungrouped)
            UNGROUPED_YAML="$2"
            shift 2
            ;;
        --classifications)
            CLASSIFICATIONS="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ungrouped PATH         Input UNGROUPED.yaml (default: config/patterns/UNGROUPED.yaml)"
            echo "  --classifications PATH   Classifications YAML (default: config/tickets_with_patterns.yaml)"
            echo "  --output-dir PATH        Output directory (default: config/ungrouped)"
            echo "  --help                   Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                              # Default paths"
            echo "  $0 --output-dir out/ungrouped/  # Custom output directory"
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
echo -e "${BOLD}   HEAL - Split Ungrouped by Category${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Input UNGROUPED:${NC} $UNGROUPED_YAML"
echo -e "${BLUE}Classifications:${NC} $CLASSIFICATIONS"
echo -e "${BLUE}Output dir:${NC} $OUTPUT_DIR"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check input files exist
if [ ! -f "$UNGROUPED_YAML" ]; then
    echo -e "${YELLOW}⚠️  UNGROUPED.yaml not found: $UNGROUPED_YAML${NC}"
    echo ""
    echo "Run pattern discovery and split first:"
    echo "  ./runners/pattern.sh"
    echo "  ./runners/split.sh"
    exit 1
fi

if [ ! -f "$CLASSIFICATIONS" ]; then
    echo -e "${YELLOW}⚠️  Classifications file not found: $CLASSIFICATIONS${NC}"
    echo ""
    echo "Run pattern discovery first:"
    echo "  ./runners/pattern.sh"
    exit 1
fi

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    uv sync --group dev
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run Python script
echo -e "${BOLD}${GREEN}Splitting ungrouped tickets by category...${NC}"
echo ""

uv run python src/heal/bootstrap/split_ungrouped_by_category.py \
    --ungrouped "$UNGROUPED_YAML" \
    --classifications "$CLASSIFICATIONS" \
    --output-dir "$OUTPUT_DIR"

# Summary
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}   Split Complete${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Category-based mini-groups created in:${NC} $OUTPUT_DIR"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Review category groups: ls -lh $OUTPUT_DIR/"
echo "  2. Fix mini-patterns: ./runners/fix.sh --pattern \$(basename \$OUTPUT_DIR/<file>.yaml .yaml)"
echo "  3. Or batch fix all ungrouped:"
echo "     for f in $OUTPUT_DIR/*.yaml; do"
echo "       pattern=\$(basename \$f .yaml)"
echo "       ./runners/fix.sh --pattern \$pattern"
echo "     done"
echo ""
