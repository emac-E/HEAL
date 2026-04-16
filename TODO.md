# HEAL Pattern Fix Workflow - TODO

## High Priority

### Bootstrap Workflow Validation

- [ ] **Test Full Agentic Workflow End-to-End from Scratch** - Critical, High Impact
  - [ ] Run complete autonomous pipeline on fresh checkout:
    1. Extract JIRA tickets with multi-agent verification
    2. Review and refine extracted answers autonomously
    3. Re-extract failures flagged by review agent
    4. Discover patterns from quality Q&A
    5. Convert to lightspeed-evaluation format
    6. Run full evaluation
  - [ ] Validate autonomous quality loop works (Review Agent → Linux Expert refinement)
  - [ ] Measure success rate: % tickets passing review without human intervention
  - [ ] Document any manual interventions needed (should be zero for agentic POC)
  - [ ] Files involved:
    - `src/heal/bootstrap/extract_jira_tickets.py`
    - `src/heal/bootstrap/refine_extracted_tickets.py`
    - `scripts/discover_patterns.py`
    - `scripts/convert_to_eval_format.py`
  - **Impact:** Validates fully autonomous multi-agent workflow works end-to-end
  - **Why:** Current testing done mid-process with pre-existing data; need clean-slate validation
  - **Priority:** CRITICAL - proves POC concept before scaling
  - **Status:** Pending - refinement improvements not yet tested fresh

### Improve Progress Visibility and Timing

- [ ] **Add Historical Timing Data for Better Estimates** - High Impact, Low Effort
  - [ ] Store historical timing data in `.diagnostics/timing_history.json`
    - Track completion time (ms) per pattern and evaluation type
    - Store: pattern_id, eval_type (full/retrieval), num_runs, duration_ms, timestamp
  - [ ] Calculate estimates from historical averages
    - Use moving average of last N runs for same pattern/config
    - Fall back to default estimate if no historical data
    - Format: `historical_avg_ms if historical_avg_ms else runs * 2 * 60000`
  - [ ] Update progress messages to use milliseconds instead of seconds
    - Capture: `start_ms = int(time.perf_counter() * 1000)`
    - Report: `print(f"Completed in {elapsed_ms}ms ({elapsed_ms/60000:.1f} min)")`
  - [ ] Files to modify:
    - `src/heal/agents/okp_mcp_agent.py`:
      - `diagnose_full()` - add timing persistence
      - `diagnose_retrieval_only()` - add timing persistence
    - `src/heal/runners/run_pattern_fix_poc.py`:
      - Add timing history loader/saver
      - Update estimate calculations
  - **Impact:** Users get accurate time estimates based on actual historical performance
  - **Why:** Current estimates (`runs * 2 minutes`) are hardcoded and often inaccurate
  - **Priority:** High - improves user experience during long-running batch operations

## Medium Priority

### Pattern Fix Loop Enhancements

- [ ] **Add Event System for Real-Time Progress** - Medium Impact, Medium Effort
  - [ ] Implement event bus using `queue.Queue` + `dataclasses` (see `docs/EVENT_DESIGN.md`)
  - [ ] Define event types:
    - `PhaseStartEvent`, `PhaseCompleteEvent`, `IterationEvent`, `EvaluationProgressEvent`
  - [ ] Emit events from pattern fix workflow
  - [ ] Add event consumer for real-time monitoring
  - **Impact:** Better real-time visibility into workflow progress
  - **Reference:** `docs/EVENT_DESIGN.md`

- [ ] **Implement Library API** - High Impact, High Effort
  - [ ] Refactor scripts into importable modules (see `docs/LIBRARY_API_DESIGN.md`)
  - [ ] Create `heal/core/` with events, models, config
  - [ ] Extract `DiagnosticEngine`, `PatternFixer`, `BatchRunner` classes
  - [ ] Maintain backward compatibility with CLI scripts
  - **Impact:** Makes HEAL reusable across projects, not just standalone scripts
  - **Reference:** `docs/LIBRARY_API_DESIGN.md`
  - **Timeline:** 5 weeks phased implementation
  - **Status:** Design document complete, awaiting review

### Performance and Quality

- [ ] **Analyze Review Score vs Judge Score Stability** - High Impact, Medium Effort
  - [ ] **Hypothesis:** Lower review_score (extraction quality) → higher variance in judge scores across eval runs
  - [ ] **Data sources:**
    - Review scores: Saved in `config/extracted_tickets.yaml` at `turns[0].review_score` (0.0-1.0)
    - Judge scores: After eval, in lightspeed-evaluation output `run_*/evaluation_*_summary.json`
  - [ ] **Analysis steps:**
    1. Run evaluation 3 times on same tickets (to get variance)
    2. Extract review_score from YAML: `ticket['turns'][0]['review_score']`
    3. Extract judge_scores from eval runs: load 3 runs of same ticket
    4. Calculate variance: `np.var([score_run1, score_run2, score_run3])`
    5. Test correlation: `scipy.stats.pearsonr(review_scores, judge_variances)`
    6. Or linear regression: `scipy.stats.linregress(review_scores, judge_variances)`
  - [ ] **Expected result:** Negative correlation (low review_score → high variance)
  - [ ] **Additional factors to test:**
    - Number of refinement iterations (not currently saved - could add)
    - Source document count: `len(ticket['turns'][0]['expected_urls'])`
    - Answer length: `len(ticket['turns'][0]['expected_response'])`
    - Problem type: from pattern discovery classification
  - [ ] **ML approach (simple scipy):**
    ```python
    # Correlation test
    correlation, p_value = scipy.stats.pearsonr(review_scores, judge_variances)
    # If correlation < 0 and p < 0.05: hypothesis confirmed
    
    # Or multi-factor regression
    from sklearn.linear_model import LinearRegression
    X = np.column_stack([review_scores, num_sources, answer_lengths])
    y = judge_variances
    model.fit(X, y)  # Which factors predict instability?
    ```
  - [ ] **Impact:** Proves ground truth quality affects eval stability; enables filtering low-quality tickets
  - [ ] **Use case:** Filter evaluation data to only high-confidence tickets (review_score >= 0.85)
  - **Priority:** High - could explain eval instability issues
  - **Status:** review_score field added, ready for analysis after extraction completes

- [ ] **Add Performance Metrics to Evaluations** - Medium Impact, Medium Effort
  - [ ] Implement performance metrics (latency, throughput, resource usage, baseline comparison)
  - [ ] Integrate with lightspeed-evaluation framework
  - [ ] Add to pattern fix diagnostics for visibility
  - **Impact:** Enables perf/scale testing required for release qualification
  - **Reference:** `docs/PERFORMANCE_METRICS_DESIGN.md`
  - **Status:** Design document complete

## Future Enhancements

### Jailbreak Protection Investigation (Separate from HEAL)

- [ ] **Investigate Guardrail Configuration for CLA Jailbreak Protection** - Medium Impact, Medium Effort
  - [ ] **Context:** Open JIRA tickets (e.g., RSPEED-2219) document jailbreak vulnerabilities
  - [ ] **Current status:** Jailbreaks likely work (no Llama Guard deployed locally)
  - [ ] **Investigation steps:**
    1. Find where guardrails are configured:
       - CLA: Check for input validation, safety filters
       - lightspeed-stack: Check middleware, request handlers
       - llamastack: Check inference safety settings
    2. Search for existing protections:
       ```bash
       # Configuration files
       find . -name "*config*.yaml" -o -name "*safety*.yaml"
       
       # Code patterns
       grep -r "safety\|guard\|filter\|sanitize" --include="*.py"
       grep -r "jailbreak\|prompt.injection" --include="*.py"
       ```
    3. Understand current state:
       - What protections exist (if any)?
       - Where do they live (CLA/lightspeed-stack/llamastack)?
       - Why aren't they blocking jailbreaks?
  - [ ] **Potential fixes (after investigation):**
    - Deploy Llama Guard (if available in llamastack)
    - Add pattern-based input filters (regex for common jailbreaks)
    - Strengthen system prompts (though this alone is weak)
    - Add response validation (detect prompt leakage)
  - [ ] **Scope for HEAL:**
    - Jailbreak tickets marked OUT_OF_SCOPE (correctly)
    - Not RHEL technical questions - security tests
    - Separate concern from fixing incorrect RHEL answers
  - **Impact:** Addresses security vulnerabilities documented in open tickets
  - **Priority:** Medium - separate from core HEAL workflow
  - **Status:** Requires investigation before implementation
  - **Note:** Different problem domain than HEAL (security vs correctness)

### Product-Based Intent System (Separate Interface)

- [ ] **Agentic Product Coverage and Intent Discovery** - High Impact, High Effort
  - [ ] **Concept:** Test-driven intent system that ensures CLA coverage of all Red Hat products
  - [ ] **Workflow:**
    1. **Product Enumeration Agent** - LLM discovers all Red Hat products
       - RHEL (versions 6-10), Satellite, OpenShift, Ansible Automation, etc.
       - Query Solr/OKP for product list or use RH product catalog
    2. **Test Discovery/Generation** - For each product:
       - Find existing tickets: `find_tickets(product="Satellite")`
       - If gaps exist: Generate synthetic tests for untested areas
    3. **Failure Detection** - Test CLA knowledge:
       - If tests pass: Note in comments "CLA has good {product} coverage"
       - If tests fail: Identify knowledge gaps
    4. **Intent Rule Builder** - Test-driven rule creation:
       - Iterate on intent rules until tests pass
       - Rules guide how to answer product-specific questions
  - [ ] **Integration with HEAL:**
    - Intent rules feed into Pattern Discovery (product-aware grouping)
    - Proactive (ensure coverage) complements reactive (fix bugs)
    - Could use same agents: Linux Expert, Solr Expert, Review Agent
  - [ ] **Example:**
    ```python
    # Discover products
    products = ["RHEL", "Satellite", "OpenShift", ...]
    
    # Find/create tests
    satellite_tests = find_or_create_tests(product="Satellite")
    
    # Test CLA
    results = test_cla(satellite_tests)  # 2/3 fail on uninstall
    
    # Build intent rules (test-driven)
    while not all_tests_pass():
        intent_rules["satellite_uninstall"] = refine_rule()
    ```
  - [ ] **Architecture:**
    - Separate interface from current HEAL workflow
    - Orthogonal: HEAL fixes existing bugs, Intent System prevents future gaps
    - Complementary: Intent rules improve pattern discovery accuracy
  - **Impact:** Systematic product coverage, prevents blind spots, broadens agentic scope
  - **Credit:** Proposed by user's friend
  - **Priority:** Future - after core HEAL workflow validated
  - **Status:** Design idea captured, pending HEAL core completion

## Low Priority

### Code Quality and Maintenance

- [ ] **Make JIRA Token Retrieval Cross-Platform** - Low Impact, Low Effort
  - [ ] Currently hardcoded to use `secret-tool` (Linux/GNOME keyring only)
  - [ ] Add fallback to `JIRA_API_TOKEN` environment variable (cross-platform)
  - [ ] Or use `keyring` Python library (supports macOS Keychain, Windows Credential Manager, Linux keyrings)
  - [ ] Files to modify:
    - `src/heal/bootstrap/extract_jira_tickets.py` - `get_jira_token()` function
  - **Impact:** Makes bootstrap workflow work on macOS and Windows
  - **Current workaround:** Set `JIRA_API_TOKEN` env var manually
  - **Priority:** Low - currently works for Linux users

- [ ] **Improve Test Coverage**
  - [ ] Add more tests for `okp_mcp_agent.py` methods
  - [ ] Add integration tests for pattern fix workflow
  - [ ] Add end-to-end tests for batch processing

- [ ] **Documentation Updates**
  - [ ] Update README with latest features
  - [ ] Add user guide for batch processing
  - [ ] Document timing history format

- [ ] **Error Handling**
  - [ ] Better error messages for common failures
  - [ ] Graceful degradation when services unavailable
  - [ ] Retry logic for transient failures

## Completed ✅

- [x] Fix Python output buffering issues (line buffering + PYTHONUNBUFFERED=1)
- [x] Add progress monitoring for evaluation runs (poll for completion files)
- [x] Fix file pattern for progress monitoring (evaluation_*_summary.json)
- [x] Add signal handling for cleanup on Ctrl+C (SIGINT/SIGTERM + atexit)
- [x] Fix authentication conflicts (switch to Claude Agent SDK throughout)
- [x] Add timestamps to evaluation progress (start/end times)
- [x] Fix format string errors in review report (handle non-float metrics)
- [x] Add phase completion summaries for better visibility
- [x] Enhance branch creation to start clean from main
- [x] Create EVENT_DESIGN.md for event system architecture
- [x] Create LIBRARY_API_DESIGN.md for refactoring roadmap
- [x] Create PERFORMANCE_METRICS_DESIGN.md for release testing
- [x] Add proper pytest tests for check_answer_in_retrieved_docs()

## Notes

### Recent Improvements (2026-04-15)

**Problem:** Batch pattern fix workflow sat silently with no progress output, making it impossible to tell if running or stuck.

**Root Causes:**
1. Python stdout buffering when output piped through `tee`
2. Progress monitoring watching wrong files (`results.csv` instead of `evaluation_*_summary.json`)
3. Auth conflicts between Anthropic SDK and Claude Agent SDK (ADC issues)
4. No cleanup on Ctrl+C - left on pattern branches instead of returning to main

**Solutions Applied:**
1. Added `sys.stdout.reconfigure(line_buffering=True)` + `PYTHONUNBUFFERED=1`
2. Fixed file pattern to `run_*/evaluation_*_summary.json`
3. Switched all LLM calls to use Claude Agent SDK's `query()` function
4. Added signal handlers (SIGINT/SIGTERM) + atexit cleanup
5. Added start/end timestamps and progress updates with explicit `flush()`
6. Enhanced output to show phase summaries instead of raw evaluation logs

**User Preference:** Milliseconds for all timing (not seconds), coming from nanosecond-level systems programming background

### Next Steps

Waiting on user review for:
- Library API design (`docs/LIBRARY_API_DESIGN.md`)
- Performance metrics design (`docs/PERFORMANCE_METRICS_DESIGN.md`)

Once approved, can proceed with implementation.
