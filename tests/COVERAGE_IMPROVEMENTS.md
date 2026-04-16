# Coverage Improvement Plan

Current overall coverage: **81%**

This document outlines specific, high-quality tests to increase coverage without "cheating" (i.e., without writing trivial tests just to execute lines).

---

## Pattern Discovery: 80% → 90%+

### Missing: Lines 145, 150-154 (Field Normalization)
**What:** Handles Claude returning `ticket_id` instead of `ticket_key`, and missing `query` field

**Why untested:** Current mocks always return perfect data with correct field names

**How to test (HIGH VALUE):**
```python
async def test_classify_handles_ticket_id_instead_of_ticket_key(self, mocker):
    """Verify agent normalizes ticket_id → ticket_key.
    
    Claude may return 'ticket_id' instead of 'ticket_key'. The agent
    should normalize this automatically.
    """
    agent = PatternDiscoveryAgent()
    
    ticket = {"key": "RSPEED-100", "fields": {"summary": "Test", "description": "Test"}}
    
    # Mock Claude returning ticket_id (not ticket_key)
    mock_response = [{
        "ticket_id": "RSPEED-100",  # Wrong field name
        "query": "Test",
        "problem_type": "OTHER",
        "components": [],
        "rhel_versions": [],
        "keywords": []
    }]
    
    async def mock_gen():
        mock_msg = mocker.MagicMock()
        mock_msg.content = [mocker.MagicMock(text=f"```json\n{json.dumps(mock_response)}\n```")]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', return_value=mock_gen())
    
    results = await agent.classify_tickets([ticket])
    
    assert len(results) == 1
    assert results[0].ticket_key == "RSPEED-100"  # Normalized correctly
```

```python
async def test_classify_handles_missing_query_field(self, mocker):
    """Verify agent fills in query from ticket summary when missing.
    
    If Claude doesn't return 'query' field, agent should use ticket summary.
    """
    agent = PatternDiscoveryAgent()
    
    ticket = {"key": "RSPEED-100", "fields": {"summary": "RHEL 6 EOL", "description": "When?"}}
    
    # Mock Claude NOT returning query field
    mock_response = [{
        "ticket_key": "RSPEED-100",
        # "query" is missing!
        "problem_type": "EOL_UNSUPPORTED",
        "components": ["lifecycle"],
        "rhel_versions": ["6"],
        "keywords": ["EOL"]
    }]
    
    async def mock_gen():
        mock_msg = mocker.MagicMock()
        mock_msg.content = [mocker.MagicMock(text=f"```json\n{json.dumps(mock_response)}\n```")]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', return_value=mock_gen())
    
    results = await agent.classify_tickets([ticket])
    
    assert len(results) == 1
    assert results[0].query == "RHEL 6 EOL"  # Filled from summary
```

**Value:** Tests real error recovery logic (Claude doesn't always return perfect JSON)

---

### Missing: Lines 241-256 (Retry Logic)
**What:** Exponential backoff retry when Claude SDK query fails

**Why untested:** Current tests never fail

**How to test (HIGH VALUE):**
```python
@pytest.mark.asyncio
async def test_discover_patterns_retries_on_claude_failure(self, mocker):
    """Verify agent retries with exponential backoff when Claude fails.
    
    When Claude SDK raises an exception, the agent should:
    1. Log the error
    2. Wait (exponential backoff: 1s, 2s)
    3. Retry up to max_retries times
    4. Return empty list if all retries exhausted
    """
    agent = PatternDiscoveryAgent()
    
    classifications = [
        TicketClassification(
            ticket_key="RSPEED-1",
            query="test",
            problem_type="OTHER",
            components=[],
            rhel_versions=[],
            keywords=[]
        )
    ]
    
    call_count = [0]
    
    async def mock_failing_gen():
        call_count[0] += 1
        if call_count[0] < 3:  # Fail first 2 attempts
            raise Exception("Claude SDK timeout")
        # Third attempt succeeds
        mock_msg = mocker.MagicMock()
        mock_msg.content = [mocker.MagicMock(text=f"```json\n{json.dumps({'patterns': []})}\n```")]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', side_effect=lambda **kwargs: mock_failing_gen())
    
    # Mock asyncio.sleep to avoid waiting
    mock_sleep = mocker.patch('asyncio.sleep')
    
    patterns = await agent.discover_patterns(classifications)
    
    assert call_count[0] == 3  # Failed twice, succeeded on 3rd
    assert mock_sleep.call_count == 2  # Slept twice (1s, 2s)
    assert patterns == []
```

```python
@pytest.mark.asyncio
async def test_discover_patterns_max_retries_exhausted(self, mocker):
    """Verify agent returns empty patterns after max retries exhausted.
    
    If all retries fail, should return [] instead of crashing.
    """
    agent = PatternDiscoveryAgent()
    
    classifications = [
        TicketClassification(
            ticket_key="RSPEED-1",
            query="test",
            problem_type="OTHER",
            components=[],
            rhel_versions=[],
            keywords=[]
        )
    ]
    
    async def mock_always_fail():
        raise Exception("Persistent Claude failure")
    
    mocker.patch('claude_agent_sdk.query', side_effect=mock_always_fail)
    mock_sleep = mocker.patch('asyncio.sleep')
    
    patterns = await agent.discover_patterns(classifications)
    
    assert patterns == []
    assert mock_sleep.call_count == 2  # Retried max_retries (2) times
```

**Value:** Tests critical error handling - Claude API can fail, agent must be resilient

---

### Missing: Lines 271-275 (Missing 'patterns' key)
**What:** Handles when Claude returns valid JSON but missing 'patterns' key

**Why untested:** Current mocks always return correct structure

**How to test (MEDIUM VALUE):**
```python
@pytest.mark.asyncio
async def test_discover_patterns_handles_missing_patterns_key(self, mocker):
    """Verify agent handles Claude returning JSON without 'patterns' key.
    
    Claude might return valid JSON but wrong structure:
    {"error": "could not find patterns"} instead of {"patterns": [...]}
    
    Agent should log error and return empty list.
    """
    agent = PatternDiscoveryAgent()
    
    classifications = [
        TicketClassification(
            ticket_key="RSPEED-1",
            query="test",
            problem_type="OTHER",
            components=[],
            rhel_versions=[],
            keywords=[]
        )
    ]
    
    async def mock_wrong_structure():
        mock_msg = mocker.MagicMock()
        # Wrong structure - has 'error' not 'patterns'
        mock_msg.content = [mocker.MagicMock(text='```json\n{"error": "no patterns found"}\n```')]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', return_value=mock_wrong_structure())
    
    patterns = await agent.discover_patterns(classifications)
    
    assert patterns == []
```

**Value:** Tests schema validation - prevents crashes when Claude returns unexpected structure

---

### Missing: Lines 288-293 (PatternGroup construction failure)
**What:** Handles when JSON has 'patterns' but items can't construct PatternGroup objects

**Why untested:** Current mocks always return valid PatternGroup dicts

**How to test (MEDIUM VALUE):**
```python
@pytest.mark.asyncio
async def test_discover_patterns_handles_invalid_pattern_schema(self, mocker):
    """Verify agent handles patterns with missing required fields.
    
    If Claude returns patterns but they're missing required fields
    (e.g., pattern_id, matched_tickets), PatternGroup construction will fail.
    
    Agent should catch this and return empty list.
    """
    agent = PatternDiscoveryAgent()
    
    classifications = [
        TicketClassification(
            ticket_key="RSPEED-1",
            query="test",
            problem_type="OTHER",
            components=[],
            rhel_versions=[],
            keywords=[]
        )
    ]
    
    async def mock_invalid_patterns():
        mock_msg = mocker.MagicMock()
        # Patterns missing required fields
        invalid = {"patterns": [{"pattern_id": "TEST"}]}  # Missing many required fields
        mock_msg.content = [mocker.MagicMock(text=f"```json\n{json.dumps(invalid)}\n```")]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', return_value=mock_invalid_patterns())
    
    patterns = await agent.discover_patterns(classifications)
    
    assert patterns == []
```

**Value:** Tests Pydantic validation error handling

---

### Missing: Lines 343-348 (Large batch splitting)
**What:** When a problem_type group has >30 tickets, splits into sub-batches

**Why untested:** Current tests only use small ticket counts

**How to test (HIGH VALUE):**
```python
@pytest.mark.asyncio
async def test_discover_patterns_splits_large_groups_into_batches(self, mocker):
    """Verify agent splits large problem_type groups into batches of 30.
    
    If EOL_UNSUPPORTED has 65 tickets, should process as:
    - Batch 1: tickets 0-29 (30 tickets)
    - Batch 2: tickets 30-59 (30 tickets)
    - Batch 3: tickets 60-64 (5 tickets)
    
    This prevents Claude from being overwhelmed with huge prompts.
    """
    agent = PatternDiscoveryAgent()
    
    # Create 65 tickets, all EOL_UNSUPPORTED
    classifications = [
        TicketClassification(
            ticket_key=f"RSPEED-{i}",
            query=f"Query {i}",
            problem_type="EOL_UNSUPPORTED",
            components=["lifecycle"],
            rhel_versions=["6"],
            keywords=["EOL"]
        )
        for i in range(65)
    ]
    
    call_count = [0]
    
    async def mock_batch_response():
        call_count[0] += 1
        mock_msg = mocker.MagicMock()
        mock_msg.content = [mocker.MagicMock(text='```json\n{"patterns": []}\n```')]
        yield mock_msg
    
    mocker.patch('claude_agent_sdk.query', side_effect=lambda **kwargs: mock_batch_response())
    
    patterns = await agent.discover_patterns(classifications, batch_size=30)
    
    # Should have called Claude 3 times (65 tickets / 30 per batch = 3 batches)
    assert call_count[0] == 3
```

**Value:** Tests batch processing logic critical for handling large ticket volumes

---

## Search Intelligence: 97% → 99%+

### Missing: Lines 267-269 (JSON load error handling)
**What:** Exception handler for corrupted JSON files

**Why untested:** Tests always use valid JSON or missing files

**How to test (HIGH VALUE):**
```python
def test_load_json_handles_corrupted_file(self):
    """Verify manager handles corrupted JSON files gracefully.
    
    If a JSON file exists but is corrupted (invalid JSON), should:
    1. Log warning
    2. Return default value
    3. Not crash
    """
    with TemporaryDirectory() as tmpdir:
        manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")
        
        # Write corrupted JSON
        corrupted_file = Path(tmpdir) / "corrupted.json"
        with open(corrupted_file, "w") as f:
            f.write("{invalid json: [")
        
        # Should return default, not crash
        result = manager._load_json(corrupted_file, default={"empty": True})
        
        assert result == {"empty": True}
```

**Value:** Tests file corruption resilience - important for production systems

---

## Solr Expert: 66% → 80%+

### Missing: Lines 66, 79-81 (Initialization error handling)
**What:** Handles SOLR_URL env var and SearchIntelligenceManager init failure

**Why untested:** Current tests don't exercise initialization edge cases

**How to test (MEDIUM VALUE):**
```python
def test_solr_expert_uses_env_solr_url(self, monkeypatch):
    """Verify SolrExpertAgent uses SOLR_URL environment variable.
    
    If SOLR_URL is set, should override default.
    """
    monkeypatch.setenv("SOLR_URL", "http://custom-solr:9999/solr/custom")
    
    agent = SolrExpertAgent()
    
    assert agent.solr_url == "http://custom-solr:9999/solr/custom"
```

```python
def test_solr_expert_handles_search_intelligence_init_failure(self, mocker):
    """Verify agent continues if SearchIntelligenceManager fails to initialize.
    
    If search intelligence can't be initialized (permission denied, etc.),
    agent should log warning and continue with search_intelligence_mgr=None.
    """
    # Mock the import to raise exception
    mocker.patch(
        'heal.core.solr_expert.SearchIntelligenceManager',
        side_effect=Exception("Permission denied")
    )
    
    agent = SolrExpertAgent()
    
    # Should still work, just without search intelligence
    assert agent.search_intelligence_mgr is None
```

**Value:** Tests optional feature degradation - search intelligence is nice-to-have, not required

---

### Missing: Lines 199-201, 253-256 (Search intelligence logging)
**What:** Logs successful searches to SearchIntelligenceManager

**Why untested:** Current tests don't verify search intelligence integration

**How to test (HIGH VALUE):**
```python
@pytest.mark.asyncio
async def test_search_for_verification_logs_to_search_intelligence(self, mocker):
    """Verify successful searches are logged to SearchIntelligenceManager.
    
    When verification finds documents with HIGH confidence, should:
    1. Log search to search intelligence
    2. Record query, topic, docs, confidence
    """
    from tempfile import TemporaryDirectory
    
    with TemporaryDirectory() as tmpdir:
        # Create agent with real SearchIntelligenceManager
        search_mgr = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")
        agent = SolrExpertAgent(search_intelligence_mgr=search_mgr)
        
        # Mock Solr query
        async def mock_query_solr(client, query, num_results):
            return [
                {"title": "RHEL 6 EOL", "url": "http://example.com/eol", "score": 0.95}
            ]
        
        mocker.patch.object(agent, '_query_solr', side_effect=mock_query_solr)
        
        queries = [
            VerificationQuery(
                query="RHEL 6 EOL date",
                context="Verify EOL",
                expected_doc_type="documentation"
            )
        ]
        
        result = await agent.search_for_verification(queries, ticket_key="RSPEED-100")
        
        # Verify search was logged
        stats = search_mgr.get_stats()
        assert stats["total_searches"] == 1
        assert stats["successful_queries"] >= 1
```

**Value:** Tests integration with SearchIntelligenceManager - critical for feedback loop

---

### Missing: Lines 269-289 (Error handling in _query_solr)
**What:** Handles HTTP errors, timeouts, malformed responses from Solr

**Why untested:** Current tests use successful Solr responses

**How to test (HIGH VALUE):**
```python
@pytest.mark.asyncio
async def test_query_solr_handles_connection_timeout(self, mocker):
    """Verify _query_solr handles Solr connection timeouts gracefully.
    
    If Solr doesn't respond within timeout, should:
    1. Log error
    2. Return empty list
    3. Not crash
    """
    agent = SolrExpertAgent()
    
    # Mock httpx client to timeout
    mock_client = mocker.MagicMock()
    mock_client.get.side_effect = httpx.TimeoutException("Solr timeout")
    
    docs = await agent._query_solr(mock_client, "test query", num_results=5)
    
    assert docs == []
```

```python
@pytest.mark.asyncio
async def test_query_solr_handles_http_500_error(self, mocker):
    """Verify _query_solr handles Solr 500 errors gracefully.
    
    If Solr returns 500 Internal Server Error, should return empty list.
    """
    agent = SolrExpertAgent()
    
    # Mock httpx response with 500 error
    mock_response = mocker.MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 error", request=mocker.MagicMock(), response=mock_response
    )
    
    mock_client = mocker.MagicMock()
    mock_client.get.return_value = mock_response
    
    docs = await agent._query_solr(mock_client, "test query", num_results=5)
    
    assert docs == []
```

```python
@pytest.mark.asyncio
async def test_query_solr_handles_malformed_json(self, mocker):
    """Verify _query_solr handles malformed JSON from Solr.
    
    If Solr returns invalid JSON, should log error and return empty list.
    """
    agent = SolrExpertAgent()
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("bad json", "", 0)
    
    mock_client = mocker.MagicMock()
    mock_client.get.return_value = mock_response
    
    docs = await agent._query_solr(mock_client, "test query", num_results=5)
    
    assert docs == []
```

**Value:** Tests critical error handling for external service failures

---

## Linux Expert: 86% → 90%+

### Missing: Lines 335-349 (Error handling in extract_with_verification)
**What:** Handles failures in hypothesis formation or synthesis

**Why untested:** Current tests always succeed

**How to test (HIGH VALUE):**
```python
@pytest.mark.asyncio
async def test_extract_with_verification_handles_hypothesis_failure(self, mocker):
    """Verify extract_with_verification handles _form_hypothesis failures.
    
    If hypothesis formation fails (Claude timeout, invalid JSON), should:
    1. Log error
    2. Return TicketQueryExtraction with inferred=True and low confidence
    """
    from heal.core.linux_expert import LinuxExpertAgent
    from heal.core.solr_expert import SolrExpertAgent
    
    ticket = {
        "key": "TEST-001",
        "fields": {
            "summary": "Test ticket",
            "description": "Test description"
        }
    }
    
    solr_expert = mocker.MagicMock(spec=SolrExpertAgent)
    linux_expert = LinuxExpertAgent()
    
    # Mock _form_hypothesis to fail
    mocker.patch.object(
        linux_expert,
        '_form_hypothesis',
        side_effect=Exception("Claude timeout")
    )
    
    result = await linux_expert.extract_with_verification(ticket, solr_expert)
    
    # Should still return a result, but with low confidence
    assert result.ticket_key == "TEST-001"
    assert result.inferred is True
    assert result.confidence == "LOW"
```

**Value:** Tests graceful degradation when LLM calls fail

---

## Summary: Prioritized Test Additions

### Priority 1 (HIGH VALUE - Add These First)
1. ✅ Pattern Discovery: Field normalization tests (lines 145, 150-154)
2. ✅ Pattern Discovery: Retry logic tests (lines 241-256)
3. ✅ Pattern Discovery: Large batch splitting (lines 343-348)
4. ✅ Search Intelligence: Corrupted JSON handling (lines 267-269)
5. ✅ Solr Expert: Error handling (_query_solr timeouts, 500s, malformed JSON)
6. ✅ Solr Expert: Search intelligence integration (lines 199-201, 253-256)
7. ✅ Linux Expert: Hypothesis failure handling (lines 335-349)

**Expected coverage increase: 81% → 88%**

### Priority 2 (MEDIUM VALUE - Add If Time Permits)
1. Pattern Discovery: Missing 'patterns' key handling (lines 271-275)
2. Pattern Discovery: PatternGroup construction errors (lines 288-293)
3. Solr Expert: Initialization edge cases (lines 66, 79-81)

**Expected coverage increase: 88% → 92%**

### Priority 3 (LOW VALUE - Skip These)
- Don't add trivial tests just to hit 100% coverage
- Integration tests (TP-001 through TP-008) provide more value than mocking everything
- Some code (logger calls, debug output) doesn't need explicit testing

---

## Test Quality Checklist

Before adding a test, ask:

1. ✅ Does this test validate real error handling logic?
2. ✅ Would this scenario actually occur in production?
3. ✅ Does the test use realistic inputs (not trivial examples)?
4. ✅ Does the test verify correct behavior (not just "doesn't crash")?
5. ❌ Am I just executing code to increase coverage %?

If you answer NO to #5 and YES to 1-4, the test is worth adding.
