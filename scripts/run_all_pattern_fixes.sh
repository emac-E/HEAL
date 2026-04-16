#!/bin/bash
# Run pattern fix workflow for all patterns
#
# Usage:
#   ./scripts/run_all_pattern_fixes.sh [--max-iterations N] [--stability-runs N] [--mode single|full]
#
# Examples:
#   # Full production run (10 iterations, 5 stability runs, full pattern mode - default)
#   ./scripts/run_all_pattern_fixes.sh --max-iterations 10 --stability-runs 5
#
#   # Quick test run (single-ticket mode for speed)
#   ./scripts/run_all_pattern_fixes.sh --max-iterations 2 --stability-runs 2 --mode single

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEAL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PATTERNS_DIR="$HEAL_ROOT/config/patterns"
LOGS_DIR="$HEAL_ROOT/.diagnostics/batch_$(date +%Y%m%d_%H%M%S)"

# Default parameters
MAX_ITERATIONS=10
STABILITY_RUNS=3
MODE="full"  # Default to full-pattern mode (test all tickets)

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --stability-runs)
      STABILITY_RUNS="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      if [[ "$MODE" != "single" && "$MODE" != "full" ]]; then
        echo "Error: --mode must be 'single' or 'full'"
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--max-iterations N] [--stability-runs N] [--mode single|full]"
      exit 1
      ;;
  esac
done

# Create logs directory
mkdir -p "$LOGS_DIR"

echo "🚀 Running Pattern Fix Workflow - Batch Mode"
echo "=============================================="
echo "Testing mode:    $MODE"
echo "Max iterations:  $MAX_ITERATIONS"
echo "Stability runs:  $STABILITY_RUNS"
echo "Patterns dir:    $PATTERNS_DIR"
echo "Logs dir:        $LOGS_DIR"
echo "=============================================="
echo ""

# Patterns to skip (not suitable for automated fixing)
SKIP_PATTERNS=(
  "UNGROUPED"                          # Too many diverse tickets
  "CONTAINER_UNSUPPORTED_CONFIG"       # Product bugs, not RAG issues
)

# Find all pattern files
PATTERNS=()
for pattern_file in "$PATTERNS_DIR"/*.yaml; do
  pattern_name=$(basename "$pattern_file" .yaml)

  # Auto-skip SME review patterns (all tickets have empty expected_response)
  if [[ "$pattern_name" == *_SME_REVIEW ]]; then
    echo "⏭️  Skipping $pattern_name (SME review only - no expected answers)"
    continue
  fi

  # Check if pattern should be skipped
  skip=false
  for skip_pattern in "${SKIP_PATTERNS[@]}"; do
    if [[ "$pattern_name" == "$skip_pattern" ]]; then
      echo "⏭️  Skipping $pattern_name (excluded from batch run)"
      skip=true
      break
    fi
  done

  if [[ "$skip" == "true" ]]; then
    continue
  fi

  PATTERNS+=("$pattern_name")
done

echo "📋 Found ${#PATTERNS[@]} patterns to process"
echo ""

# Track results
SUCCESSFUL=()
FAILED=()
SKIPPED=()

# Process each pattern
for i in "${!PATTERNS[@]}"; do
  pattern_id="${PATTERNS[$i]}"
  pattern_num=$((i + 1))
  total_patterns="${#PATTERNS[@]}"

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Pattern $pattern_num/$total_patterns: $pattern_id"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  log_file="$LOGS_DIR/${pattern_id}.log"

  # Run pattern fix workflow
  cd "$HEAL_ROOT"

  if PYTHONUNBUFFERED=1 uv run python src/heal/runners/run_pattern_fix_poc.py "$pattern_id" \
      --max-iterations "$MAX_ITERATIONS" \
      --stability-runs "$STABILITY_RUNS" \
      --mode "$MODE" \
      2>&1 | tee "$log_file"; then

    # Check if pattern actually succeeded (exit 0 doesn't mean success, check review report)
    if grep -q "Status: ✅ SUCCESS" ".diagnostics/$pattern_id/REVIEW_REPORT.md" 2>/dev/null; then
      echo "✅ $pattern_id: SUCCESS"
      SUCCESSFUL+=("$pattern_id")
    else
      echo "❌ $pattern_id: FAILED (see review report)"
      FAILED+=("$pattern_id")
    fi
  else
    echo "❌ $pattern_id: FAILED (workflow error)"
    FAILED+=("$pattern_id")
  fi

  echo "📝 Log saved to: $log_file"
done

# Generate summary report
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "BATCH RUN SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Total patterns:  ${#PATTERNS[@]}"
echo "✅ Successful:   ${#SUCCESSFUL[@]}"
echo "❌ Failed:       ${#FAILED[@]}"
echo ""

if [[ ${#SUCCESSFUL[@]} -gt 0 ]]; then
  echo "✅ Successful patterns:"
  for pattern in "${SUCCESSFUL[@]}"; do
    echo "   - $pattern"
  done
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "❌ Failed patterns:"
  for pattern in "${FAILED[@]}"; do
    echo "   - $pattern"
  done
  echo ""
fi

echo "📁 Diagnostics: .diagnostics/[PATTERN_ID]/REVIEW_REPORT.md"
echo "📁 Batch logs:  $LOGS_DIR/"
echo ""

# Create summary file
summary_file="$LOGS_DIR/BATCH_SUMMARY.md"
cat > "$summary_file" << EOF
# Batch Pattern Fix Summary

**Run Date:** $(date)

**Parameters:**
- Max Iterations: $MAX_ITERATIONS
- Stability Runs: $STABILITY_RUNS

## Results

Total Patterns: ${#PATTERNS[@]}
- ✅ Successful: ${#SUCCESSFUL[@]}
- ❌ Failed: ${#FAILED[@]}

## Successful Patterns

EOF

if [[ ${#SUCCESSFUL[@]} -gt 0 ]]; then
  for pattern in "${SUCCESSFUL[@]}"; do
    echo "- $pattern" >> "$summary_file"
  done
else
  echo "None" >> "$summary_file"
fi

cat >> "$summary_file" << EOF

## Failed Patterns

EOF

if [[ ${#FAILED[@]} -gt 0 ]]; then
  for pattern in "${FAILED[@]}"; do
    echo "- $pattern (see \`.diagnostics/$pattern/REVIEW_REPORT.md\`)" >> "$summary_file"
  done
else
  echo "None" >> "$summary_file"
fi

cat >> "$summary_file" << EOF

## Next Steps

### For Successful Patterns

Review and merge fixes:

\`\`\`bash
cd /path/to/okp-mcp

# Review each successful pattern branch
EOF

for pattern in "${SUCCESSFUL[@]}"; do
  branch_name=$(echo "$pattern" | tr '[:upper:]_' '[:lower:]-')
  echo "git checkout fix/pattern-$branch_name" >> "$summary_file"
  echo "git log --oneline" >> "$summary_file"
  echo "" >> "$summary_file"
done

cat >> "$summary_file" << EOF
# If satisfied, merge to main
git checkout main
EOF

for pattern in "${SUCCESSFUL[@]}"; do
  branch_name=$(echo "$pattern" | tr '[:upper:]_' '[:lower:]-')
  echo "git merge --squash fix/pattern-$branch_name" >> "$summary_file"
done

cat >> "$summary_file" << EOF
git commit -m "fix: Apply pattern-based fixes for ${#SUCCESSFUL[@]} patterns"
\`\`\`

### For Failed Patterns

Investigate failures:

\`\`\`bash
EOF

for pattern in "${FAILED[@]}"; do
  echo "# $pattern" >> "$summary_file"
  echo "cat .diagnostics/$pattern/REVIEW_REPORT.md" >> "$summary_file"
  echo "" >> "$summary_file"
done

echo "\`\`\`" >> "$summary_file"

echo "📄 Summary saved to: $summary_file"
cat "$summary_file"

# Exit with error if any failed
if [[ ${#FAILED[@]} -gt 0 ]]; then
  exit 1
else
  exit 0
fi
