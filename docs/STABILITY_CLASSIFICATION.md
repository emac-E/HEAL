# Statistical Stability Classification

## Problem

When testing multiple tickets in a pattern with multiple evaluation runs, **averaging scores can mask individual ticket failures**:

```python
# Bad: Averaging masks Ticket B's failure
Ticket A: [0.95, 0.95, 0.95]  → avg = 0.95 ✅
Ticket B: [0.50, 0.55, 0.52]  → avg = 0.52 ❌
Ticket C: [0.92, 0.93, 0.91]  → avg = 0.92 ✅

Pattern avg = 0.80  # Looks "borderline" but hides that Ticket B is failing badly
```

Even worse, averaging across runs can mask intermittent failures:

```python
# Really Bad: Intermittent failure masked by averaging
Ticket runs: [0.95, 0.50, 0.95, 0.92]  → avg = 0.83

# Looks borderline, but reality: 1 catastrophic failure (0.50)
# This is a critical intermittent issue that needs investigation!
```

## Solution

**Statistical classification with skip tags** - analyze each ticket individually:

```python
from heal.core.stability_classifier import classify_stability

runs = [0.95, 0.50, 0.95, 0.92]
classification = classify_stability(runs, threshold=0.90)

# Result:
# status: INTERMITTENT_FAILURE
# reason: "1/4 runs failed, min=0.50 (catastrophic)"
# skip: False  # Must fix!
# needs_review: True  # Investigate why it fails sometimes
# priority: HIGH
```

## Classification System

### StabilityStatus

1. **STABLE_PASSING** - All runs passed with low variance
   - `skip = True` - Don't waste iterations on this ticket
   - `needs_review = False`
   - Example: [0.92, 0.91, 0.93, 0.91]

2. **UNSTABLE_PASSING** - All runs passed but high variance
   - `skip = True` - May not be fixable (measurement noise)
   - `needs_review = True` - Investigate why variance is high
   - Example: [0.90, 1.0, 0.90, 1.0] (CV > 0.15)

3. **BORDERLINE** - Some runs barely fail, some pass
   - `skip = False` - Needs fixing
   - `needs_review = False`
   - Example: [0.88, 0.91, 0.87, 0.90]

4. **INTERMITTENT_FAILURE** - Some catastrophic failures hidden by averaging
   - `skip = False` - Critical issue
   - `needs_review = True` - Must investigate root cause
   - Example: [0.95, 0.50, 0.95, 0.92]

5. **CONSISTENTLY_FAILING** - All runs failed
   - `skip = False` - Definitely needs fixing
   - `needs_review = False`
   - Example: [0.65, 0.68, 0.62, 0.70]

### Metrics

- **Failure Rate**: Percent of runs that failed
- **Coefficient of Variation (CV)**: std_dev / mean (normalized variance)
  - CV < 0.05: Low variance (stable)
  - CV > 0.15: High variance (unstable)
- **Min/Max/Mean**: Range of scores across runs
- **Catastrophic Threshold**: Below 0.70 = catastrophic failure

## Workflow Integration

### Phase 1: Baseline Assessment

```python
# Run all tickets, analyze each individually
for ticket in pattern_tickets:
    ticket_runs = [run.answer_correctness for run in runs]
    
    classification = classify_stability(ticket_runs, threshold=0.90)
    
    if classification.status == StabilityStatus.STABLE_PASSING:
        ticket.skip = True  # Don't iterate on this
    elif classification.status == StabilityStatus.INTERMITTENT_FAILURE:
        ticket.skip = False
        ticket.priority = "HIGH"
        ticket.needs_investigation = True
    else:
        ticket.skip = False
        ticket.priority = classification.priority
```

### Phase 2-3: Optimization

```python
# Only evaluate non-skipped tickets
failing_tickets = [t for t in pattern_tickets if not t.skip]

for iteration in range(max_iterations):
    # Evaluation framework honors skip flag
    run_eval(pattern_tickets)  # Skipped tickets return cached results
    
    # Re-classify after each iteration (progressive skipping)
    for ticket in failing_tickets:
        if ticket.answer_correctness >= 0.90:
            classification = classify_stability([...])
            if classification.status == StabilityStatus.STABLE_PASSING:
                ticket.skip = True  # Fixed! Skip in next iteration
```

### Phase 4: Final Validation

```python
# Remove ALL skip tags - validate everything
for ticket in pattern_tickets:
    ticket.skip = False

# Full evaluation to catch regressions
final_results = run_eval(pattern_tickets)

# Verify no previously-passing tickets broke
for ticket in pattern_tickets:
    if ticket.was_stable_passing_at_baseline:
        assert ticket.still_passing, "Regression detected!"
```

## Benefits

✅ **Detects masked failures** - Individual ticket failures don't hide in averages  
✅ **Identifies intermittent issues** - Catastrophic failures detected even if rare  
✅ **Reduces wasted iterations** - Skip stable tickets, focus on failing ones  
✅ **Progressive optimization** - More tickets get skipped as they get fixed  
✅ **Better diagnostics** - Know exactly which tickets need work and why  
✅ **Prevents regressions** - Final validation tests everything

## Example Output

```
================================================================================
PHASE 1: BASELINE ASSESSMENT
================================================================================

Running 5 stability runs on 3 tickets...

📊 Per-Ticket Classification:

✅ RSPEED-2218: STABLE_PASSING
   All 5 runs passed (mean=0.92, CV=0.02)
   → Will SKIP in optimization phase

❌ RSPEED-2219: INTERMITTENT_FAILURE
   1/5 runs failed catastrophically (min=0.45, max=0.95)
   → Priority: HIGH, needs investigation

❌ RSPEED-2220: BORDERLINE
   2/5 runs failed (min=0.88, max=0.92)
   → Priority: MEDIUM, needs optimization

Summary:
- Stable passing: 1/3 (will skip)
- Needs fixing: 2/3
- High priority: 1/3
```

## Testing

See `tests/test_stability_classifier.py` for comprehensive test coverage:

```bash
uv run pytest tests/test_stability_classifier.py -v
```

Tests cover:
- All 5 classification statuses
- Masked failure detection
- Measurement noise vs intermittent failure
- Coefficient of variation calculation
- Custom thresholds
- Edge cases (single run, empty runs)
