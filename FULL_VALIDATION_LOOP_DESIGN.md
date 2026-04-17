# Full Validation Loop Design

## Problem
Current fix loop does:
1. Baseline (20 min)
2. Loop: optimize → quick Solr test (30 sec) → repeat 10x
3. Final validation (20 min)

**Issue**: We don't know if answer_correctness improved until the very end!

## Desired Behavior (User Request)

```
1. Baseline (once) → get answer_correctness baseline

2. Loop (max_iterations):
   a. Optimize/get suggestion
   b. Apply fix
   c. **FULL validate** (answer_correctness, faithfulness)
   d. Check if passing threshold (e.g., > 0.85)
   e. If PASSING → ✅ SUCCESS, exit early!
   f. If IMPROVED but not passing → continue
   g. If NOT IMPROVED for 3 iterations → stop
   
3. Pattern database tracks:
   - What fixes were tried
   - Which ones improved metrics
   - Which ones reached passing threshold
```

## Implementation Options

### Option A: Validate Every Iteration (Slow but Accurate)
```python
def optimize_with_full_validation(
    max_iterations=10,
    passing_threshold=0.85,  # answer_correctness threshold
    max_no_improvement=3,     # stop if no improvement for N iterations
):
    # Baseline
    baseline = full_evaluation()  # 20 min
    best_answer = baseline.answer_correctness
    
    for iteration in range(1, max_iterations + 1):
        # Optimize
        suggestion = multi_agent.suggest_fix()
        apply_fix(suggestion)
        
        # FULL validate
        current = full_evaluation()  # 20 min each!
        
        # Check if passing
        if current.answer_correctness >= passing_threshold:
            print(f"✅ PASSING! ({current.answer_correctness:.2f} >= {passing_threshold})")
            break  # SUCCESS
        
        # Check if improved
        if current.answer_correctness > best_answer:
            print(f"✅ Improved: {best_answer:.2f} → {current.answer_correctness:.2f}")
            best_answer = current.answer_correctness
            no_improvement_count = 0
            commit_fix()  # Keep this fix
        else:
            print(f"❌ No improvement: {current.answer_correctness:.2f} <= {best_answer:.2f}")
            no_improvement_count += 1
            revert_fix()  # Don't keep this fix
        
        # Early stop if stuck
        if no_improvement_count >= max_no_improvement:
            print(f"⏹️  Stopping: no improvement for {max_no_improvement} iterations")
            break
    
    # Final report
    return best_answer >= passing_threshold
```

**Pros:**
- Accurate feedback every iteration
- Stop as soon as passing threshold reached
- Pattern database tracks real improvement

**Cons:**
- SLOW: 20 min × 10 iterations = 3+ hours
- But user wants this ("it seemed to get us to success frequently")

### Option B: Hybrid (Validate Every N Iterations)
```python
def optimize_hybrid(
    max_iterations=15,
    validate_frequency=3,  # Full validate every 3 iterations
):
    baseline = full_evaluation()
    
    for i in range(1, max_iterations + 1):
        suggestion = multi_agent.suggest_fix()
        apply_fix(suggestion)
        
        # Quick test every iteration
        quick_result = quick_solr_test()  # 30 sec
        
        # Full validate every Nth iteration
        if i % validate_frequency == 0:
            full_result = full_evaluation()  # 20 min
            if full_result.answer_correctness >= threshold:
                break  # PASSING!
```

**Pros:**
- Faster than Option A
- Still gets full validation feedback

**Cons:**
- Might waste iterations between validation checks

### Option C: Adaptive (Validate When Promising)
```python
def optimize_adaptive(max_iterations=15):
    baseline = full_evaluation()
    
    for i in range(1, max_iterations + 1):
        suggestion = multi_agent.suggest_fix()
        apply_fix(suggestion)
        
        # Quick test first
        quick_result = quick_solr_test()
        
        # If quick metrics look good → full validate
        if quick_result.url_f1 > baseline.url_f1 + 0.10:
            print("📊 Promising improvement, running full validation...")
            full_result = full_evaluation()
            if full_result.answer_correctness >= threshold:
                break  # PASSING!
```

## Recommendation

**Go with Option A (Full Validation Every Iteration)** because:

1. User said: "it seemed to get us to success frequently" - referring to the earlier version that did this
2. Overnight runs are fine being slow (3-5 hours) if they find the right fix
3. Pattern database will have accurate data on what actually improves answer quality
4. Early exit when passing saves time on successful patterns

## Implementation Plan

1. Add `--full-validation-loop` flag to `fix.sh`
2. Modify `run_retrieval_optimization()` to:
   - Run full `diagnose()` instead of quick Solr test after each fix
   - Check `answer_correctness >= threshold`
   - Exit early when passing
   - Revert fixes that don't improve
3. Track all attempts in pattern database:
   ```python
   pattern_db.record_attempt(
       iteration=i,
       suggestion=suggestion,
       baseline_answer=baseline_answer,
       new_answer=current_answer,
       improved=current_answer > baseline_answer,
       passed=current_answer >= threshold,
   )
   ```

## Usage

```bash
# Fast mode (current behavior): quick Solr tests
./runners/fix.sh PATTERN_ID

# Full validation mode: answer_correctness feedback each iteration
./runners/fix.sh PATTERN_ID --full-validation-loop

# Customize thresholds
./runners/fix.sh PATTERN_ID \\
    --full-validation-loop \\
    --passing-threshold 0.85 \\
    --max-iterations 10
```

## Time Estimates

**Fast mode (current)**:
- Baseline: 20 min
- Iterations: 10 × 30 sec = 5 min
- Final validation: 20 min
- **Total: ~45 min**

**Full validation mode**:
- Baseline: 20 min
- Iterations: 10 × 20 min = 200 min (but stops early if passing!)
- Average case (3-4 iterations to pass): ~1.5 hours
- Worst case (10 iterations): ~3.5 hours
- **Total: 1.5-3.5 hours**

Still reasonable for overnight runs!
