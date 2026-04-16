# HEAL Pattern Fix Loop

Automated fix loop for pattern-based JIRA ticket resolution with smart optimization routing.

## Quick Start

### 1. Configure paths

Edit `config/pattern_fix_config.yaml` with your repository locations:

```yaml
# Typical setup with sibling repos
eval_root: ../../lightspeed-core/lightspeed-evaluation
okp_mcp_root: ../../okp-mcp
lscore_deploy_root: ../../lscore-deploy
```

Or use environment variables:
```bash
export LIGHTSPEED_EVAL_ROOT=/path/to/lightspeed-evaluation
export OKP_MCP_ROOT=/path/to/okp-mcp
export LSCORE_DEPLOY_ROOT=/path/to/lscore-deploy
```

### 2. Run the workflow

```bash
cd /path/to/HEAL
python -m heal.runners.run_pattern_fix_poc EOL_UNSUPPORTED_LEGACY_RHEL
```

## Usage

### Basic Usage

```bash
# Run with default config
python -m heal.runners.run_pattern_fix_poc PATTERN_ID

# Or run the script directly
python src/heal/runners/run_pattern_fix_poc.py PATTERN_ID
```

### Custom Parameters

```bash
# Override config values
python -m heal.runners.run_pattern_fix_poc PATTERN_ID \
    --max-iterations 5 \
    --answer-threshold 0.80 \
    --stability-runs 5
```

### Custom Config File

```bash
# Use a different config
python -m heal.runners.run_pattern_fix_poc PATTERN_ID \
    --config /path/to/custom_config.yaml
```

## Workflow Phases

### Phase 1: Initial Baseline
- Runs full evaluation with all metrics
- Determines problem type (retrieval vs answer quality)
- Early exit if already passing

### Phase 2: Smart Optimization
Routes to appropriate optimization:

**Route A: Retrieval Optimization** (fast, ~15-20 sec/iteration)
- When: Retrieval metrics are low
- Tests: Solr config changes (qf, pf, mm)
- Mode: Retrieval-only (no response generation)

**Route B: Prompt Optimization** (slower, ~30-60 sec/iteration)
- When: Answer quality is low but retrieval is good
- Tests: System prompt changes
- Mode: Full evaluation (with response generation)

### Phase 3: Answer Validation
- Validates answer_correctness ≥ threshold
- Must also pass faithfulness ≥ 0.8

### Phase 4: Stability Check
- Runs N times to verify consistency
- Checks variance < 0.05
- All runs must pass threshold

## Output

### Git Branch
```
fix/pattern-<pattern-id>
```
Created in the okp-mcp repository.

### Diagnostics
```
.diagnostics/<PATTERN_ID>/
├── REVIEW_REPORT.md       # Human review report
└── (other diagnostic files)
```

### Review Report
Automatically generated with:
- Overall status (✅ SUCCESS / ❌ FAILED)
- Phase-by-phase breakdown
- Next steps (merge or investigate)

## Configuration

### Required Paths

| Config Key | Description |
|-----------|-------------|
| `eval_root` | lightspeed-evaluation repository |
| `okp_mcp_root` | okp-mcp repository |
| `lscore_deploy_root` | lscore-deploy repository |
| `patterns_dir` | Pattern YAML directory (relative to HEAL root) |

### Optimization Parameters

| Config Key | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | 10 | Max iterations per optimization phase |
| `answer_threshold` | 0.90 | Minimum answer_correctness to pass |
| `stability_runs` | 3 | Number of runs for stability check |

## Examples

### Quick Test (2 iterations)
```bash
python -m heal.runners.run_pattern_fix_poc EOL_UNSUPPORTED_LEGACY_RHEL \
    --max-iterations 2 \
    --stability-runs 2
```

### High Confidence (15 iterations, 5 stability runs)
```bash
python -m heal.runners.run_pattern_fix_poc BOOTLOADER_UEFI_FIRMWARE \
    --max-iterations 15 \
    --answer-threshold 0.80 \
    --stability-runs 5
```

## Troubleshooting

### "Config file not found"
```bash
# Copy example config
cp config/pattern_fix_config.yaml.example config/pattern_fix_config.yaml

# Edit paths
vim config/pattern_fix_config.yaml
```

### "Environment variable not set"
```bash
# Set required environment variables
export OKP_MCP_ROOT=/path/to/okp-mcp
export LSCORE_DEPLOY_ROOT=/path/to/lscore-deploy
export LIGHTSPEED_EVAL_ROOT=/path/to/lightspeed-evaluation
```

### "Required path does not exist"
Verify paths in config file point to existing directories:
```bash
ls -ld $(grep 'okp_mcp_root:' config/pattern_fix_config.yaml | awk '{print $2}')
```

### "Pattern file not found"
List available patterns:
```bash
ls config/patterns/*.yaml
```

## See Also

- [Pattern Discovery](../../docs/PATTERN_DISCOVERY.md) - How patterns are discovered
- [Configuration Guide](../../docs/CONFIGURATION.md) - Detailed config options
