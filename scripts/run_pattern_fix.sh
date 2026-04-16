#!/bin/bash
#
# Simple wrapper for pattern fix POC
# Usage: ./scripts/run_pattern_fix.sh PATTERN_ID [single|full]
#
# Examples:
#   ./scripts/run_pattern_fix.sh CONTAINER_UNSUPPORTED_CONFIG
#   ./scripts/run_pattern_fix.sh RHEL10_DEPRECATED_FEATURES full
#

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 PATTERN_ID [single|full]"
    echo ""
    echo "Examples:"
    echo "  $0 CONTAINER_UNSUPPORTED_CONFIG          # full-pattern mode (default)"
    echo "  $0 RHEL10_DEPRECATED_FEATURES single     # single-ticket mode"
    echo ""
    exit 1
fi

PATTERN_ID=$1
MODE=${2:-full}  # Default to full-pattern mode

# Default parameters (adjust these as needed)
MAX_ITERATIONS=10
STABILITY_RUNS=5
ANSWER_THRESHOLD=0.90

# Navigate to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "========================================"
echo "Pattern Fix POC"
echo "========================================"
echo "Pattern:           $PATTERN_ID"
echo "Mode:              $MODE"
echo "Max iterations:    $MAX_ITERATIONS"
echo "Stability runs:    $STABILITY_RUNS"
echo "Answer threshold:  $ANSWER_THRESHOLD"
echo "========================================"
echo ""

# Run the pattern fix POC
uv run python src/heal/runners/run_pattern_fix_poc.py \
    "$PATTERN_ID" \
    --mode "$MODE" \
    --max-iterations "$MAX_ITERATIONS" \
    --stability-runs "$STABILITY_RUNS" \
    --answer-threshold "$ANSWER_THRESHOLD"
