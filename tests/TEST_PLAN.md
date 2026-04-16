# HEAL Test Plan

## Objectives
1. Verify each agent component works independently
2. Test integration between agents
3. Ensure high code coverage of core modules
4. Validate data structures and edge cases

## Test Coverage Goals
- **Pattern Discovery**: 80%+ coverage
- **Search Intelligence**: 95%+ coverage  
- **Linux Expert**: 50%+ coverage (relies on Claude SDK)
- **Solr Expert**: 50%+ coverage (relies on external Solr)

---

## Core Agent Tests (test_multi_agent_system.py)

### TP-001: Claude Agent SDK Basic Connectivity
**Goal:** Verify Claude Agent SDK can make simple API calls with Vertex AI credentials

**Why:** Foundation test - if this fails, all Claude-dependent tests will fail. Tests ADC authentication and basic SDK functionality.

**What it tests:**
- Claude Agent SDK import and initialization
- Vertex AI authentication via ADC
- Basic message passing and response handling

**Steps:**
1. Import claude_agent_sdk
2. Create simple prompt (< 100 chars)
3. Call query() with minimal options
4. Verify we get a response back

**Expected:** AssistantMessage with text content
**Dependencies:** ANTHROPIC_VERTEX_PROJECT_ID env var, ADC configured

---

### TP-002: Claude Agent SDK with Long Prompts
**Goal:** Verify SDK can handle prompts > 100 characters (realistic use case)

**Why:** Real HEAL prompts include system instructions (RHEL expertise context) + ticket content, typically 1000+ characters. This ensures no truncation issues.

**What it tests:**
- Long system prompt handling
- Multi-paragraph prompt formatting
- Response completeness

**Steps:**
1. Create prompt with system instructions + user task (> 100 chars)
2. Call query() with max_turns=1
3. Extract text from response

**Expected:** Full response text without truncation
**Dependencies:** TP-001 passes

---

### TP-003: Claude Agent SDK JSON Output
**Goal:** Verify SDK can return structured JSON responses

**Why:** All HEAL agents (Linux Expert, Pattern Discovery) return structured JSON for machine-readable results. This validates JSON parsing works correctly.

**What it tests:**
- JSON formatting in prompts
- JSON extraction from markdown code blocks
- JSON parsing and validation

**Steps:**
1. Create prompt requesting JSON response
2. Parse JSON from response text (handles ```json blocks)
3. Validate JSON structure

**Expected:** Valid JSON object matching expected schema
**Dependencies:** TP-002 passes

---

### TP-004: Solr Expert - Direct Solr Connectivity
**Goal:** Verify SolrExpertAgent can query Solr directly via HTTP

**Why:** Validates Solr is accessible and returns expected document structure. Critical for verification workflow.

**What it tests:**
- Solr HTTP connection (httpx async client)
- Query parameter construction
- Document parsing from Solr response

**Steps:**
1. Create SolrExpertAgent instance
2. Call _query_solr() with simple query
3. Verify documents returned

**Expected:** List of document dicts with title, url, score
**Dependencies:** Solr running on localhost:8983 (skipped if SKIP_SOLR_TESTS=true)

---

### TP-005: Solr Expert - Verification Query
**Goal:** Verify search_for_verification() works end-to-end

**Why:** This is the main Solr Expert API used by Linux Expert to verify hypotheses. Tests full workflow including confidence calculation.

**What it tests:**
- VerificationQuery → Solr search → VerificationResult flow
- Confidence level calculation (HIGH/MEDIUM/LOW)
- Source URL extraction

**Steps:**
1. Create VerificationQuery for known fact (e.g., "RHEL 6 EOL date")
2. Call search_for_verification()
3. Verify VerificationResult has docs and confidence

**Expected:** VerificationResult with HIGH/MEDIUM confidence and source URLs
**Dependencies:** TP-004 passes

---

### TP-006: Linux Expert - Hypothesis Formation
**Goal:** Verify _form_hypothesis() can analyze JIRA ticket and return structured response

**Why:** This is step 1 of Linux Expert workflow: understand the user question and form an initial hypothesis. Tests Claude's ability to extract queries from JIRA tickets.

**What it tests:**
- JIRA ticket parsing (summary + description)
- Query extraction and reformulation
- Hypothesis generation from RHEL expertise
- Verification query generation

**Steps:**
1. Create test ticket dict (realistic JIRA structure)
2. Call _form_hypothesis()
3. Validate returned dict has: query, hypothesis, verification_queries

**Expected:** Dict with all required fields, verification_queries is non-empty list
**Dependencies:** TP-003 passes (needs JSON output)

---

### TP-007: Linux Expert - Answer Synthesis  
**Goal:** Verify _synthesize_verified_answer() creates final response from hypothesis + verification

**Why:** This is step 2 of Linux Expert workflow: combine hypothesis with Solr verification results to produce final answer. Tests answer quality and source attribution.

**What it tests:**
- Hypothesis + VerificationResult → final answer
- Confidence propagation
- Source URL tracking
- Inferred flag calculation

**Steps:**
1. Create mock hypothesis dict
2. Create mock VerificationResult
3. Call _synthesize_verified_answer()
4. Validate output format

**Expected:** Dict with query, expected_response, confidence, sources, inferred
**Dependencies:** TP-003 passes

---

### TP-008: Full Integration
**Goal:** Verify complete workflow: Linux Expert ↔ Solr Expert

**Why:** End-to-end integration test of the core JIRA extraction pipeline. This is the main use case: extract verified query/answer pairs from JIRA tickets.

**What it tests:**
- Full agent collaboration
- Async coordination between agents
- Data flow: JIRA → hypothesis → verification → extraction
- TicketQueryExtraction model construction

**Steps:**
1. Create real JIRA ticket dict
2. Initialize both agents (LinuxExpertAgent, SolrExpertAgent)
3. Call extract_with_verification()
4. Verify complete TicketQueryExtraction returned

**Expected:** Complete extraction with verified answer and sources
**Dependencies:** TP-005, TP-006, TP-007 pass

---

## Pattern Discovery Tests (test_pattern_discovery.py)

### Why Pattern Discovery Matters
Pattern Discovery enables **10-15x efficiency gain** by grouping similar JIRA tickets. Instead of extracting 15 similar tickets individually, we:
1. Classify tickets by problem type
2. Discover patterns (e.g., "all RHEL 6 EOL questions")
3. Generate one template answer for the entire pattern
4. Apply template to all matching tickets

### Test Coverage: 80%

#### Ticket Classification Tests
**What:** Tests classify_tickets() which categorizes tickets by problem type, components, RHEL versions

**Why:** Classification is the foundation of pattern discovery - poor classification = poor patterns

**Tests:**
- Single EOL ticket classification (validates problem_type, components, versions extraction)
- Multiple tickets with different types (validates batch processing)
- Empty ticket list (edge case)
- Tickets with missing fields (robustness)

**Coverage:** Lines 79-160 in pattern_discovery.py

#### Pattern Discovery Tests
**What:** Tests discover_patterns() which groups classified tickets into patterns

**Why:** This is the core value - identifying that 15 tickets are really asking the same question

**Tests:**
- EOL pattern identification (3+ tickets about RHEL 6 EOL → 1 pattern)
- No similarity detection (completely different tickets → 0 patterns)
- Single ticket handling (edge case - can't form pattern)

**Coverage:** Lines 162-296 in pattern_discovery.py

#### Pattern Merging Tests
**What:** Tests _merge_overlapping_patterns() which deduplicates patterns with >50% ticket overlap

**Why:** Prevents duplicate patterns when discovery finds the same group multiple times

**Tests:**
- Overlapping patterns (tickets [1,2,3] and [2,3,4] → deduplicate)
- No overlap (tickets [1,2,3] and [4,5,6] → keep separate)

**Coverage:** Lines 360-390 in pattern_discovery.py

---

## Search Intelligence Tests (test_search_intelligence.py)

### Why Search Intelligence Matters
Search Intelligence creates a **feedback loop** between extraction and fixing:
- During extraction: Record which Solr queries successfully found docs
- During fixing: Use that intelligence to diagnose why searches fail in production

**Example:** If extraction found `https://access.redhat.com/rhel6-eol` using query "RHEL 6 EOL date", but fixing can't find it, we know it's a search config issue (not a docs gap).

### Test Coverage: 97%

#### SearchResult Creation Tests
**What:** Tests SearchResult.from_verification() factory method

**Why:** Validates data capture from Solr queries - must record query, docs, scores, confidence

**Tests:**
- Creation with documents found (validates all fields populated)
- Creation with no documents (validates doc_count=0, top_doc_score=0.0)

**Coverage:** Lines 50-69 in search_intelligence.py

#### Search Logging Tests
**What:** Tests log_search() which persists searches to JSONL + indexes successful ones

**Why:** This is the write path - must correctly log to audit trail AND index for fast lookup

**Tests:**
- HIGH confidence search → written to 3 files (audit, successful_queries, topic_to_docs)
- LOW confidence search → only written to audit (not indexed)
- Multiple searches same topic → accumulate queries and docs

**Coverage:** Lines 94-165 in search_intelligence.py

#### Intelligence Retrieval Tests
**What:** Tests get_search_intelligence_for_ticket() which retrieves relevant search history

**Why:** This is the read path - fixing agent uses this to learn what searches previously worked

**Tests:**
- Retrieval with history (returns working queries and docs)
- Retrieval with no history (returns None)
- get_working_queries_for_topic (topic-specific query list)

**Coverage:** Lines 167-228 in search_intelligence.py

#### Statistics Tests
**What:** Tests get_stats() which provides analytics on search intelligence database

**Why:** Monitoring search success rate, topic coverage over time

**Tests:**
- Stats with searches logged
- Stats on empty manager

**Coverage:** Lines 229-258 in search_intelligence.py

#### File I/O Tests
**What:** Tests _save_json(), _load_json() persistence

**Why:** Validates data survives across manager restarts, handles missing files gracefully

**Tests:**
- Save/load roundtrip
- Load missing file uses default
- Persistence across manager instances

**Coverage:** Lines 260-280 in search_intelligence.py

#### Edge Cases
**What:** Stress tests with unusual inputs

**Why:** Robustness - must handle empty queries, long topic names, shared documents

**Tests:**
- Empty query string
- Very long topic name (500+ chars)
- Same document under multiple topics

**Coverage:** Various edge case handling

---

## Coverage Gaps and Improvement Opportunities

### Current Coverage
| Module | Coverage | Gap |
|--------|----------|-----|
| pattern_discovery.py | 80% | 20% (lines 124-135: claude_sdk_context removal cleanup, error handling) |
| search_intelligence.py | 97% | 3% (atomic rename edge case) |
| linux_expert.py | 19% | 81% (mostly Claude SDK integration, hard to mock) |
| solr_expert.py | 19% | 81% (mostly Solr HTTP queries, requires running Solr) |

### Why Low Coverage on Linux/Solr Expert is OK
- **Real LLM dependency**: Mocking Claude SDK responses is fragile and doesn't test real behavior
- **Real Solr dependency**: Mocking HTTP responses loses value of integration testing
- **TP-006, TP-007, TP-008 tests**: These ARE testing Linux/Solr Expert, but with REAL Claude SDK + Solr
- **Trade-off**: Lower coverage % but higher test quality (integration > unit)

### Opportunities to Increase Coverage (Without Cheating)

#### Pattern Discovery (80% → 90%+)
1. **Test batch processing logic** (lines 106-117)
   - Test tickets split into batches of 10
   - Test batch boundary conditions (9 tickets, 11 tickets, 31 tickets)

2. **Test error handling in _discover_patterns_batch** (lines 243-258)
   - Test retry logic when Claude SDK fails
   - Test max retries reached
   - Test exponential backoff timing

3. **Test hierarchical batching** (lines 322-350)
   - Test problem_type grouping
   - Test large groups split into sub-batches

#### Search Intelligence (97% → 99%+)
1. **Test atomic rename failure** (line 279)
   - Mock temp_path.replace() to raise exception
   - Verify graceful handling

2. **Test URL matching edge cases** (lines 190-192)
   - Test URLs with trailing slashes
   - Test partial URL matches

#### Linux Expert (19% → 40%+)
1. **Test error handling in _form_hypothesis**
   - Test when Claude returns invalid JSON
   - Test when Claude times out
   - Test when required fields missing

2. **Test error handling in _synthesize_verified_answer**
   - Same as above

3. **Test extract_with_verification error paths**
   - Test when hypothesis formation fails
   - Test when verification fails
   - Test when synthesis fails

#### Solr Expert (19% → 40%+)
1. **Test _query_solr error handling**
   - Test Solr connection timeout
   - Test Solr returns 500 error
   - Test malformed Solr response

2. **Test search_for_verification with multiple queries**
   - Test aggregation of results across queries
   - Test confidence calculation edge cases

---

## Debugging Strategy

If TP-001 fails → Check ANTHROPIC_VERTEX_PROJECT_ID, gcloud auth, ADC file
If TP-002 fails → Check prompt formatting, max_tokens
If TP-003 fails → Check JSON parsing logic, regex extraction
If TP-004 fails → Check SOLR_URL, Solr running, network connectivity
If TP-006/TP-007 fail → Check Claude Agent SDK error details, stderr output, model escalation
If TP-008 fails → Check integration logic, async/await patterns, data flow

If pattern discovery tests fail → Check mock response format (array vs dict), classification data structure
If search intelligence tests fail → Check data structure assumptions (dicts with "query" key, nested "best_docs")

---

## Test Quality Guidelines

### What We Do
- ✅ Test real implementations (LinuxExpertAgent, SolrExpertAgent, not test doubles)
- ✅ Use pytest-mock (mocker fixture) exclusively
- ✅ Test data structures match actual implementation
- ✅ Test edge cases (empty inputs, malformed data)
- ✅ Test error handling and retries
- ✅ Use descriptive docstrings explaining what each test validates

### What We Don't Do
- ❌ Test standalone/debug code that doesn't run in production
- ❌ Use unittest.mock (use pytest-mock instead)
- ❌ Mock everything to get 100% coverage (integration tests have value)
- ❌ Write tests that pass but don't validate real behavior
- ❌ Skip testing because "it's hard to mock"

### When to Write Integration vs Unit Tests
- **Unit tests**: Pure functions, data transformations, parsing logic
- **Integration tests**: Agent collaboration, Claude SDK calls, Solr queries
- **Balance**: Aim for mix - unit tests for speed, integration tests for confidence

---

## Running Tests

```bash
# All tests (excluding ones that need Solr)
uv run pytest tests/ -v

# Include Solr tests (requires Solr running)
SKIP_SOLR_TESTS=false uv run pytest tests/ -v

# Coverage report
uv run pytest tests/ --cov=src/heal/core --cov-report=term-missing

# Specific test file
uv run pytest tests/test_pattern_discovery.py -v

# Stop on first failure
uv run pytest tests/ -x
```
