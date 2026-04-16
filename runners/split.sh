#!/usr/bin/env bash
# Split Patterns - Create evaluation YAML files from pattern-tagged tickets
#
# This script takes the output from pattern discovery and splits tickets
# into separate YAML files (one per pattern) ready for lightspeed-evaluation.
#
# Input: tickets_with_patterns.yaml (from pattern discovery)
# Output: One YAML per pattern in config/patterns/
#
# No LLM calls - just reorganizes existing data by pattern_id.
#
# Usage:
#   ./runners/split.sh                     # Default paths
#   ./runners/split.sh --output-dir out/   # Custom output directory

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
INPUT="config/tickets_with_patterns.yaml"
PATTERNS="config/patterns_report.json"
OUTPUT_DIR="config/patterns"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            INPUT="$2"
            shift 2
            ;;
        --patterns)
            PATTERNS="$2"
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
            echo "  --input PATH         Input YAML with pattern tags (default: config/tickets_with_patterns.yaml)"
            echo "  --patterns PATH      Patterns report JSON (default: config/patterns_report.json)"
            echo "  --output-dir PATH    Output directory for pattern YAMLs (default: config/patterns)"
            echo "  --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                              # Default paths"
            echo "  $0 --output-dir out/patterns/   # Custom output directory"
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
echo -e "${BOLD}   HEAL - Split Patterns to Evaluation Files${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Input:${NC} $INPUT"
echo -e "${BLUE}Patterns:${NC} $PATTERNS"
echo -e "${BLUE}Output dir:${NC} $OUTPUT_DIR"
echo -e "${BLUE}Date:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check input files exist
if [ ! -f "$INPUT" ]; then
    echo -e "${YELLOW}⚠️  Input file not found: $INPUT${NC}"
    echo ""
    echo "Run pattern discovery first:"
    echo "  ./runners/pattern.sh"
    exit 1
fi

if [ ! -f "$PATTERNS" ]; then
    echo -e "${YELLOW}⚠️  Patterns file not found: $PATTERNS${NC}"
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

# Run split
echo -e "${BOLD}${GREEN}Splitting tickets by pattern...${NC}"
echo ""

uv run python src/heal/bootstrap/split_patterns_to_eval_files.py \
    --input "$INPUT" \
    --patterns "$PATTERNS" \
    --output-dir "$OUTPUT_DIR"

# Summary
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}   Split Complete${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Pattern files created in:${NC} $OUTPUT_DIR"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Review pattern YAMLs: ls -lh $OUTPUT_DIR/"
echo "  2. Test evaluation on a pattern:"
echo "     cd /home/emackey/Work/lightspeed-core/lightspeed-evaluation"
echo "     uv run python -m lightspeed_evaluation.runner \\"
echo "       --config config/system_okp_mcp_agent.yaml \\"
echo "       --data $(realpath $OUTPUT_DIR)/<PATTERN_ID>.yaml \\"
echo "       --metrics ragas:context_relevance,custom:answer_correctness"
echo ""
