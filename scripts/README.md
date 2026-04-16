# HEAL Scripts

Batch processing and utility scripts for HEAL pattern fix workflows.

## API Health Check

### test_api_health.sh

Quick test to verify the lightspeed API is responding correctly.

**Quick Start:**

```bash
cd /path/to/HEAL

# Run API health check
./scripts/test_api_health.sh
```

**What it does:**

1. Checks if okp-mcp container is running on localhost:8001
2. Creates a minimal test config with one simple question
3. Clears API cache to ensure fresh request
4. Runs a single evaluation with the question "What is RHEL?"
5. Reports success or failure with specific error details

**When to use:**
- ✅ Before running pattern fixes (verify API is healthy)
- ✅ When getting 500 errors (diagnose infrastructure issues)
- ✅ After restarting okp-mcp container (verify it's working)

**Example output:**
```
✅ API Health Check: PASSED
The lightspeed API is responding correctly!
```

or

```
❌ API Health Check: FAILED
⚠️  Detected HTTP 500 errors - API is experiencing issues
   This is an infrastructure problem, not a code issue
```

---

## Pattern Fix Batch Processing

### run_pattern_fix.sh

Simple wrapper script for running pattern fix POC with sensible defaults.

**Quick Start:**

```bash
cd /path/to/HEAL

# Full-pattern mode (default)
./scripts/run_pattern_fix.sh CONTAINER_UNSUPPORTED_CONFIG

# Single-ticket mode (for individual ticket testing)
./scripts/run_pattern_fix.sh RHEL10_DEPRECATED_FEATURES single
```

**What it does:**

Runs the pattern fix POC workflow with pre-configured defaults:
- Max iterations: 10
- Stability runs: 5
- Answer threshold: 0.90
- Mode: full (or specify `single` as second argument for individual ticket testing)

**When to use:**
- ✅ Quick testing on a single pattern
- ✅ Development/iteration on pattern fixes
- ✅ When you want sensible defaults without remembering flags

**Edit defaults:** Modify variables at top of `scripts/run_pattern_fix.sh` to customize:
```bash
MAX_ITERATIONS=10
STABILITY_RUNS=5
ANSWER_THRESHOLD=0.90
```

---

### run_all_pattern_fixes.sh

Run the pattern fix workflow for all patterns with full optimization cycles.

**Quick Start:**

```bash
cd /path/to/HEAL

# Full production run (10 iterations, 5 stability runs, full-pattern mode)
./scripts/run_all_pattern_fixes.sh --max-iterations 10 --stability-runs 5

# Quick test run (2 iterations, 2 stability runs, single-ticket mode for speed)
./scripts/run_all_pattern_fixes.sh --max-iterations 2 --stability-runs 2 --mode single
```

**What it does:**

1. Finds all pattern files in `config/patterns/`
2. **Skips excluded patterns** (UNGROUPED, CONTAINER_UNSUPPORTED_CONFIG)
3. Runs pattern fix workflow for each pattern sequentially
4. Logs output for each pattern to `.diagnostics/batch_TIMESTAMP/PATTERN_ID.log`
5. Generates summary report with success/failure counts
6. Creates review reports in `.diagnostics/PATTERN_ID/REVIEW_REPORT.md`
7. **Leaves fixes in branches** - does NOT auto-merge to main

**Auto-skipped patterns:**
- Patterns ending in `_SME_REVIEW` (contain only tickets needing SME answers)
- Patterns in `SKIP_PATTERNS` array:
  - `UNGROUPED` - Too many diverse tickets
  - `CONTAINER_UNSUPPORTED_CONFIG` - Product bugs, not RAG issues

**To skip additional patterns:**
Edit `scripts/run_all_pattern_fixes.sh` and add to `SKIP_PATTERNS` array:
```bash
SKIP_PATTERNS=(
  "UNGROUPED"
  "CONTAINER_UNSUPPORTED_CONFIG"
  "YOUR_PATTERN_NAME"  # Add patterns not suitable for automated fixing
)
```

**Note:** Patterns with `_SME_REVIEW` suffix are automatically created when patterns
have tickets with empty `expected_response`. These are auto-skipped.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--max-iterations` | 10 | Max optimization iterations per pattern |
| `--stability-runs` | 5 | Number of runs for stability validation |

**Output:**

```
.diagnostics/
├── batch_20260413_235900/
│   ├── BATCH_SUMMARY.md              # Summary of all patterns
│   ├── EOL_RHEL_VERSION_SUPPORT.log  # Full log for each pattern
│   ├── CONTAINER_UNSUPPORTED_CONFIG.log
│   └── ...
├── EOL_RHEL_VERSION_SUPPORT/
│   └── REVIEW_REPORT.md              # Review report for pattern
├── CONTAINER_UNSUPPORTED_CONFIG/
│   └── REVIEW_REPORT.md
└── ...
```

**Expected Runtime:**

- **Per pattern:** ~5-15 minutes (depends on iterations and answer quality)
- **Full batch (11 patterns after exclusions, 10 iterations, 5 stability runs):** ~1-3 hours
- **Note:** With answer-first exit criteria, patterns with correct answers skip optimization entirely

**Parallel Execution (Advanced):**

To run multiple patterns in parallel (use with caution - may overwhelm resources):

```bash
# Patterns to skip
SKIP_PATTERNS=("UNGROUPED" "CONTAINER_UNSUPPORTED_CONFIG")

# Create a simple parallel wrapper
for pattern in config/patterns/*.yaml; do
  pattern_id=$(basename "$pattern" .yaml)
  
  # Check if pattern should be skipped
  skip=false
  for skip_pattern in "${SKIP_PATTERNS[@]}"; do
    [[ "$pattern_id" == "$skip_pattern" ]] && skip=true && break
  done
  
  if [[ "$skip" == "false" ]]; then
    (
      uv run python src/heal/runners/run_pattern_fix_poc.py "$pattern_id" \
        --max-iterations 10 \
        --stability-runs 5 \
        > ".diagnostics/batch_parallel/${pattern_id}.log" 2>&1
    ) &
  fi
done

# Wait for all background jobs
wait
```

**Monitoring Progress:**

```bash
# Watch logs in real-time
tail -f .diagnostics/batch_*/BATCH_SUMMARY.md

# Check individual pattern progress
tail -f .diagnostics/batch_*/EOL_RHEL_VERSION_SUPPORT.log

# Count completed patterns
ls .diagnostics/*/REVIEW_REPORT.md | wc -l
```

## Next Steps After Batch Run

### 1. Review Summary

```bash
# Read batch summary
cat .diagnostics/batch_TIMESTAMP/BATCH_SUMMARY.md

# List successful patterns
grep "✅" .diagnostics/batch_TIMESTAMP/BATCH_SUMMARY.md
```

### 2. Review Individual Patterns

```bash
# Check review report for each pattern
cat .diagnostics/EOL_RHEL_VERSION_SUPPORT/REVIEW_REPORT.md
cat .diagnostics/CONTAINER_UNSUPPORTED_CONFIG/REVIEW_REPORT.md
```

### 3. Merge Successful Fixes

```bash
cd /path/to/okp-mcp

# Review branches created by workflow
git branch | grep 'fix/pattern-'

# Check changes for each successful pattern
git checkout fix/pattern-eol-rhel-version-support
git log --oneline
git diff main

# If satisfied, merge all successful patterns
git checkout main

# Option A: Merge each pattern individually
git merge --squash fix/pattern-eol-rhel-version-support
git commit -m "fix: EOL RHEL version support pattern"

git merge --squash fix/pattern-container-unsupported-config
git commit -m "fix: Container unsupported config pattern"

# Option B: Merge all patterns at once
git merge --squash fix/pattern-eol-rhel-version-support fix/pattern-container-unsupported-config ...
git commit -m "fix: Apply automated pattern-based fixes (12 patterns)"
```

### 4. Investigate Failures

For failed patterns, check:

```bash
# Read review report
cat .diagnostics/FAILED_PATTERN/REVIEW_REPORT.md

# Check full log
cat .diagnostics/batch_TIMESTAMP/FAILED_PATTERN.log

# Common failure reasons:
# - Faithfulness too low (LLM hallucinating)
# - High variance (unstable answers)
# - Retrieval optimization limit reached
# - Expected response too vague
```

## Tips and Best Practices

### Start Small

Before running full batch:

```bash
# Test on one pattern first
uv run python src/heal/runners/run_pattern_fix_poc.py EOL_RHEL_VERSION_SUPPORT \
    --max-iterations 2 \
    --stability-runs 2

# If successful, try quick batch
./scripts/run_all_pattern_fixes.sh --max-iterations 2 --stability-runs 2

# Then run full production batch
./scripts/run_all_pattern_fixes.sh --max-iterations 10 --stability-runs 5
```

### Resource Management

**CPU/Memory:**
- Each pattern runs sequentially (no parallel execution by default)
- Lightspeed-evaluation uses embeddings (CPU-intensive)
- Judge LLM calls (API calls, not local compute)

**Disk Space:**
- Each pattern generates ~10-50MB of logs/results
- Full batch: ~500MB-1GB total

**API Usage:**
- Judge LLM: ~20K-50K tokens per pattern
- Full batch (12 patterns): ~240K-600K tokens
- Cost: ~$1-3 for full batch (Gemini 2.5 Pro pricing)

### Scheduling Overnight Runs

```bash
# Run batch overnight
nohup ./scripts/run_all_pattern_fixes.sh \
    --max-iterations 10 \
    --stability-runs 5 \
    > batch_run.log 2>&1 &

# Check progress in the morning
cat batch_run.log | tail -100
```

### CI/CD Integration

```bash
# In CI pipeline (GitHub Actions, GitLab CI, etc.)
- name: Run Pattern Fix Batch
  run: |
    cd HEAL
    ./scripts/run_all_pattern_fixes.sh --max-iterations 5 --stability-runs 3

- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: pattern-fix-results
    path: .diagnostics/batch_*/
```

## Troubleshooting

### Script Fails Immediately

```bash
# Check config file exists
cat config/pattern_fix_config.yaml

# Verify paths are correct
ls ../../../okp-mcp
ls ../../../lightspeed-core/lightspeed-evaluation

# Test single pattern first
uv run python src/heal/runners/run_pattern_fix_poc.py EOL_RHEL_VERSION_SUPPORT \
    --max-iterations 1 --stability-runs 1
```

### Pattern Hangs/Takes Too Long

```bash
# Check if okp-mcp is running
curl http://localhost:8443/api/lightspeed/health

# Check lightspeed-evaluation is working
cd /path/to/lightspeed-evaluation
uv run lightspeed-eval --help

# Kill stuck pattern and skip it
pkill -f run_pattern_fix_poc
```

### All Patterns Failing

```bash
# Check recent changes to okp-mcp
cd /path/to/okp-mcp
git log --oneline -5

# Verify test suite still works
cd /path/to/lightspeed-evaluation
uv run lightspeed-eval run config/system_okp_mcp_agent.yaml
```
