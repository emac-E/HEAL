#!/usr/bin/env python3
"""Comprehensive tests for Search Intelligence Manager.

The Search Intelligence Manager records successful search queries during JIRA
ticket extraction and makes this intelligence available during the fixing phase.
This creates a feedback loop: extraction learns what works, fixing uses that knowledge.

Test Coverage:
- Search result logging: Recording search attempts with outcomes
- Query indexing: Building indexes of successful queries by topic
- Topic-to-docs mapping: Tracking which documents answer which topics
- Intelligence retrieval: Getting relevant search history for ticket fixing
- Statistics and analytics: Monitoring search success rates over time
- File I/O: JSON persistence and loading
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from heal.core.search_intelligence import (
    SearchIntelligenceManager,
    SearchResult,
)


class TestSearchResultCreation:
    """Tests for SearchResult data class creation and validation.

    SearchResult captures the outcome of a single Solr search during
    JIRA extraction: what was searched, what was found, and how confident
    the verification was.
    """

    def test_create_search_result_from_verification_with_docs(self):
        """Verify SearchResult creation from successful Solr verification.

        When Solr finds relevant documents for a verification query,
        SearchResult should capture:
        - The query text
        - The topic being verified (e.g., "RHEL_6_EOL")
        - All found documents with scores
        - The verification confidence level
        - Timestamp for audit trail
        """
        found_docs = [
            {"title": "RHEL 6 EOL", "url": "https://example.com/rhel6-eol", "score": 0.95},
            {"title": "RHEL Lifecycle", "url": "https://example.com/lifecycle", "score": 0.82},
        ]

        result = SearchResult.from_verification(
            query="RHEL 6 end of life date",
            topic="RHEL_6_EOL",
            ticket_key="RSPEED-100",
            found_docs=found_docs,
            confidence="HIGH",
        )

        assert result.query == "RHEL 6 end of life date"
        assert result.topic == "RHEL_6_EOL"
        assert result.ticket_key == "RSPEED-100"
        assert result.doc_count == 2
        assert result.top_doc_score == 0.95
        assert result.verification_confidence == "HIGH"
        assert result.found_docs == found_docs
        assert result.timestamp  # Should be set to current time

    def test_create_search_result_from_verification_no_docs(self):
        """Verify SearchResult handles searches that find no documents.

        When Solr finds nothing for a query, SearchResult should still
        capture the attempt with doc_count=0 and top_doc_score=0.0.
        This is valuable for tracking what doesn't work.
        """
        result = SearchResult.from_verification(
            query="nonexistent fake query",
            topic="FAKE_TOPIC",
            ticket_key="RSPEED-999",
            found_docs=[],
            confidence="LOW",
        )

        assert result.doc_count == 0
        assert result.top_doc_score == 0.0
        assert result.verification_confidence == "LOW"
        assert result.found_docs == []


class TestSearchLogging:
    """Tests for logging search attempts to persistent storage.

    Each search is logged to search_results.jsonl (append-only audit trail)
    and also indexed for fast lookup by topic or query.
    """

    def test_log_search_successful_high_confidence(self):
        """Verify logging a successful search with HIGH confidence.

        High-confidence searches should be:
        - Written to search_results.jsonl
        - Indexed in successful_queries.json (topic → queries)
        - Indexed in topic_to_docs.json (topic → documents)
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            result = SearchResult.from_verification(
                query="RHEL 6 EOL date",
                topic="RHEL_6_EOL",
                ticket_key="RSPEED-100",
                found_docs=[
                    {"title": "RHEL 6 EOL", "url": "https://example.com/rhel6", "score": 0.95}
                ],
                confidence="HIGH",
            )

            manager.log_search(result)

            # Verify written to audit trail
            audit_file = Path(tmpdir) / "search_intelligence" / "search_results.jsonl"
            assert audit_file.exists()

            with open(audit_file) as f:
                logged = json.loads(f.read())
                assert logged["query"] == "RHEL 6 EOL date"
                assert logged["topic"] == "RHEL_6_EOL"

            # Verify indexed in successful queries
            queries_file = Path(tmpdir) / "search_intelligence" / "successful_queries.json"
            with open(queries_file) as f:
                queries = json.load(f)
                assert "RHEL_6_EOL" in queries
                # successful_queries stores list of dicts with "query" key
                assert any(q["query"] == "RHEL 6 EOL date" for q in queries["RHEL_6_EOL"])

            # Verify indexed in topic_to_docs
            docs_file = Path(tmpdir) / "search_intelligence" / "topic_to_docs.json"
            with open(docs_file) as f:
                topics = json.load(f)
                assert "RHEL_6_EOL" in topics
                # topic_to_docs has structure: {topic: {best_docs: [...], working_queries: [...], last_verified: ...}}
                assert len(topics["RHEL_6_EOL"]["best_docs"]) == 1
                assert topics["RHEL_6_EOL"]["best_docs"][0]["title"] == "RHEL 6 EOL"

    def test_log_search_low_confidence_not_indexed(self):
        """Verify LOW confidence searches are logged but not indexed as successful.

        Searches that find documents but with LOW confidence should:
        - Still be written to audit trail (for analysis)
        - NOT be indexed in successful_queries.json
        - NOT be indexed in topic_to_docs.json

        This prevents bad queries from polluting the success index.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            result = SearchResult.from_verification(
                query="vague unclear query",
                topic="SOME_TOPIC",
                ticket_key="RSPEED-200",
                found_docs=[{"title": "Random doc", "url": "http://example.com", "score": 0.3}],
                confidence="LOW",
            )

            manager.log_search(result)

            # Should be in audit trail
            audit_file = Path(tmpdir) / "search_intelligence" / "search_results.jsonl"
            assert audit_file.exists()

            # Should NOT be in successful queries
            queries_file = Path(tmpdir) / "search_intelligence" / "successful_queries.json"
            # File may not exist if no successful queries logged yet (which is the case here)
            if queries_file.exists():
                with open(queries_file) as f:
                    queries = json.load(f)
                    assert "SOME_TOPIC" not in queries
            # If file doesn't exist, that's correct - no successful queries were logged

    def test_log_multiple_searches_same_topic(self):
        """Verify multiple searches for the same topic accumulate correctly.

        When multiple queries target the same topic, the manager should:
        - Add all successful queries to the topic's query list
        - Merge documents from all searches (avoiding duplicates)
        - Maintain chronological order in audit trail
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            # First search
            result1 = SearchResult.from_verification(
                query="RHEL 6 EOL date",
                topic="RHEL_6_EOL",
                ticket_key="RSPEED-100",
                found_docs=[{"title": "RHEL 6 EOL", "url": "http://ex.com/1", "score": 0.9}],
                confidence="HIGH",
            )
            manager.log_search(result1)

            # Second search, same topic
            result2 = SearchResult.from_verification(
                query="RHEL 6 support end",
                topic="RHEL_6_EOL",
                ticket_key="RSPEED-101",
                found_docs=[{"title": "RHEL Lifecycle", "url": "http://ex.com/2", "score": 0.85}],
                confidence="MEDIUM",
            )
            manager.log_search(result2)

            # Verify both queries indexed
            queries_file = Path(tmpdir) / "search_intelligence" / "successful_queries.json"
            with open(queries_file) as f:
                queries = json.load(f)
                assert len(queries["RHEL_6_EOL"]) == 2
                # Check dict objects with "query" key
                query_strings = [q["query"] for q in queries["RHEL_6_EOL"]]
                assert "RHEL 6 EOL date" in query_strings
                assert "RHEL 6 support end" in query_strings

            # Verify both documents in topic index
            docs_file = Path(tmpdir) / "search_intelligence" / "topic_to_docs.json"
            with open(docs_file) as f:
                topics = json.load(f)
                assert len(topics["RHEL_6_EOL"]["best_docs"]) == 2


class TestIntelligenceRetrieval:
    """Tests for retrieving search intelligence during fixing phase.

    When fixing a ticket, the agent queries the intelligence manager to learn:
    - What queries previously worked for this topic
    - What documents should be retrievable
    - What search configuration was used when it worked
    """

    def test_get_search_intelligence_for_ticket_with_history(self):
        """Verify retrieving search intelligence for a ticket with prior successful searches.

        If previous tickets about RHEL 6 EOL were verified successfully,
        the intelligence for a new RHEL 6 EOL ticket should include:
        - List of queries that found relevant documents
        - The documents that were found
        - Confidence levels achieved
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            # Log a successful search
            result = SearchResult.from_verification(
                query="RHEL 6 end of life",
                topic="RHEL_6_EOL",
                ticket_key="RSPEED-100",
                found_docs=[{"title": "RHEL 6 EOL", "url": "http://ex.com/eol", "score": 0.9}],
                confidence="HIGH",
            )
            manager.log_search(result)

            # Retrieve intelligence by looking for the URL that was found
            intelligence = manager.get_search_intelligence_for_ticket(
                ticket_key="RSPEED-101", expected_urls=["http://ex.com/eol"]
            )

            assert intelligence is not None
            assert intelligence["found"] is True
            assert "topics" in intelligence
            assert len(intelligence["topics"]) == 1
            assert intelligence["topics"][0]["topic"] == "RHEL_6_EOL"
            assert "RHEL 6 end of life" in intelligence["topics"][0]["working_queries"]
            assert len(intelligence["topics"][0]["best_docs"]) == 1
            assert intelligence["topics"][0]["best_docs"][0]["title"] == "RHEL 6 EOL"

    def test_get_search_intelligence_no_history(self):
        """Verify intelligence retrieval returns None for unknown topics.

        If no previous searches exist for a topic, the manager should
        return None rather than empty structures. This signals to the
        fixing agent that it's working with a novel topic.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            intelligence = manager.get_search_intelligence_for_ticket(
                ticket_key="RSPEED-999", expected_urls=["http://unknown.com/doc"]
            )

            assert intelligence is None

    def test_get_working_queries_for_topic(self):
        """Verify retrieval of just the working queries for a specific topic.

        Fixing agents may only need the query list (not full documents)
        to understand what search terms successfully retrieved information.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            # Log searches for a topic
            for query in ["RHEL 6 EOL", "RHEL 6 lifecycle", "RHEL 6 support status"]:
                result = SearchResult.from_verification(
                    query=query,
                    topic="RHEL_6_EOL",
                    ticket_key=f"RSPEED-{hash(query)}",
                    found_docs=[{"title": "doc", "url": "http://ex.com", "score": 0.8}],
                    confidence="HIGH",
                )
                manager.log_search(result)

            queries = manager.get_working_queries_for_topic("RHEL_6_EOL")

            assert len(queries) == 3
            assert "RHEL 6 EOL" in queries
            assert "RHEL 6 lifecycle" in queries
            assert "RHEL 6 support status" in queries


class TestStatistics:
    """Tests for search statistics and analytics.

    Statistics help monitor:
    - Overall search success rate
    - Which topics have good vs poor search coverage
    - Search quality trends over time
    """

    def test_get_stats_with_searches_logged(self):
        """Verify statistics calculation with logged searches.

        Stats should include:
        - Total search count
        - Successful search count (HIGH or MEDIUM confidence)
        - Success rate percentage
        - Number of unique topics covered
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            # Log successful search
            result1 = SearchResult.from_verification(
                query="query1",
                topic="TOPIC_A",
                ticket_key="RSPEED-1",
                found_docs=[{"title": "doc", "url": "http://ex.com", "score": 0.9}],
                confidence="HIGH",
            )
            manager.log_search(result1)

            # Log failed search
            result2 = SearchResult.from_verification(
                query="query2",
                topic="TOPIC_B",
                ticket_key="RSPEED-2",
                found_docs=[],
                confidence="LOW",
            )
            manager.log_search(result2)

            stats = manager.get_stats()

            assert stats["total_searches"] == 2
            assert stats["topics_covered"] == 1  # Only TOPIC_A was HIGH
            assert stats["successful_queries"] == 1  # Only one successful query

    def test_get_stats_empty_manager(self):
        """Verify statistics on a fresh manager with no searches.

        A new manager should return valid stats structure with zero counts.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            stats = manager.get_stats()

            assert stats["total_searches"] == 0
            assert stats["topics_covered"] == 0
            assert stats["successful_queries"] == 0
            assert stats["unique_docs_found"] == 0


class TestFileIO:
    """Tests for JSON file persistence and loading.

    The manager must reliably save and load:
    - search_results.jsonl (append-only log, one JSON per line)
    - successful_queries.json (topic → query list mapping)
    - topic_to_docs.json (topic → document list mapping)
    """

    def test_save_and_load_json_roundtrip(self):
        """Verify JSON save/load roundtrip preserves data exactly.

        Data written to JSON should be loadable without corruption.
        This tests the internal _save_json and _load_json methods.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            test_data = {"key1": "value1", "key2": [1, 2, 3]}
            test_file = Path(tmpdir) / "test.json"

            manager._save_json(test_file, test_data)
            loaded_data = manager._load_json(test_file, default={})

            assert loaded_data == test_data

    def test_load_json_missing_file_uses_default(self):
        """Verify loading non-existent file returns default value.

        When a JSON file doesn't exist (e.g., fresh install), loading
        should return the provided default without error.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            missing_file = Path(tmpdir) / "nonexistent.json"
            loaded = manager._load_json(missing_file, default={"empty": True})

            assert loaded == {"empty": True}

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

    def test_persistence_across_manager_instances(self):
        """Verify search intelligence persists across manager restarts.

        If the manager logs searches, then a new manager instance is created
        (simulating restart), the new instance should load the prior data.
        """
        with TemporaryDirectory() as tmpdir:
            # First manager instance - log a search
            manager1 = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")
            result = SearchResult.from_verification(
                query="persistent query",
                topic="PERSISTENCE_TEST",
                ticket_key="RSPEED-PERSIST",
                found_docs=[{"title": "doc", "url": "http://ex.com", "score": 0.9}],
                confidence="HIGH",
            )
            manager1.log_search(result)

            # Second manager instance - should load prior data
            manager2 = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")
            queries = manager2.get_working_queries_for_topic("PERSISTENCE_TEST")

            assert "persistent query" in queries


class TestEdgeCases:
    """Tests for edge cases and error handling.

    Search intelligence must handle:
    - Malformed data gracefully
    - Concurrent writes (append-only log helps)
    - Disk full scenarios
    - Invalid JSON in existing files
    """

    def test_log_search_with_empty_query(self):
        """Verify handling of search result with empty query string.

        Empty queries might occur from malformed tickets. The manager
        should still log them but they won't be useful for intelligence.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            result = SearchResult.from_verification(
                query="",
                topic="EMPTY_QUERY",
                ticket_key="RSPEED-EMPTY",
                found_docs=[],
                confidence="LOW",
            )

            # Should not raise exception
            manager.log_search(result)

            stats = manager.get_stats()
            assert stats["total_searches"] == 1

    def test_log_search_with_very_long_topic_name(self):
        """Verify handling of unusually long topic names.

        Topic names are user/LLM-generated and might be excessively long.
        The manager should handle this without truncation or error.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            long_topic = "RHEL_" + "VERY_LONG_" * 50 + "TOPIC"
            result = SearchResult.from_verification(
                query="test query",
                topic=long_topic,
                ticket_key="RSPEED-LONG",
                found_docs=[{"title": "doc", "url": "http://ex.com", "score": 0.8}],
                confidence="HIGH",
            )

            manager.log_search(result)

            queries = manager.get_working_queries_for_topic(long_topic)
            assert "test query" in queries

    def test_multiple_searches_same_document_different_topics(self):
        """Verify same document can appear under multiple topics.

        A document about "RHEL lifecycle" might be relevant for both
        "RHEL_6_EOL" and "RHEL_7_EOL" topics. The manager should track
        this many-to-many relationship correctly.
        """
        with TemporaryDirectory() as tmpdir:
            manager = SearchIntelligenceManager(db_path=Path(tmpdir) / "search_intelligence")

            shared_doc = {"title": "RHEL Lifecycle", "url": "http://ex.com/lifecycle", "score": 0.9}

            # Log for RHEL 6
            result1 = SearchResult.from_verification(
                query="RHEL 6 EOL",
                topic="RHEL_6_EOL",
                ticket_key="RSPEED-6",
                found_docs=[shared_doc],
                confidence="HIGH",
            )
            manager.log_search(result1)

            # Log same doc for RHEL 7
            result2 = SearchResult.from_verification(
                query="RHEL 7 EOL",
                topic="RHEL_7_EOL",
                ticket_key="RSPEED-7",
                found_docs=[shared_doc],
                confidence="HIGH",
            )
            manager.log_search(result2)

            # Both topics should have the document when searching by URL
            intel1 = manager.get_search_intelligence_for_ticket(
                ticket_key="RSPEED-NEW-6", expected_urls=["http://ex.com/lifecycle"]
            )
            intel2 = manager.get_search_intelligence_for_ticket(
                ticket_key="RSPEED-NEW-7", expected_urls=["http://ex.com/lifecycle"]
            )

            # Should find the document under both topics
            assert intel1 is not None
            assert intel2 is not None
            # Both searches should return the same topics since they're looking for the same URL
            all_topics = {t["topic"] for t in intel1["topics"]} | {
                t["topic"] for t in intel2["topics"]
            }
            assert "RHEL_6_EOL" in all_topics
            assert "RHEL_7_EOL" in all_topics
