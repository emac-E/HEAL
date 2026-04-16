"""Real integration test for pattern discovery (no mocks).

Run with: uv run pytest tests/test_pattern_discovery_real.py -v -s
"""

import pytest
from heal.core.pattern_discovery import PatternDiscoveryAgent, TicketClassification


@pytest.mark.asyncio
async def test_discover_patterns_real_claude_call():
    """Test pattern discovery with actual Claude SDK call (no mocks).

    This test uses the real Claude SDK to discover patterns, helping debug
    issues that only appear when calling Vertex AI.
    """
    agent = PatternDiscoveryAgent()

    # Use the actual classifications from your checkpoint
    classifications = [
        TicketClassification(
            ticket_key="RSPEED-1930",
            query="How do I install packages on a system using rpm-ostree?",
            problem_type="OTHER",
            components=["packages", "rpm-ostree"],
            rhel_versions=[],
            keywords=["rpm-ostree", "install", "packages", "reboot", "atomic-host"],
        ),
        TicketClassification(
            ticket_key="RSPEED-1931",
            query="How to configure firewall rules?",
            problem_type="OTHER",
            components=["networking", "firewall"],
            rhel_versions=["8"],
            keywords=["firewall", "firewalld", "rules"],
        ),
        TicketClassification(
            ticket_key="RSPEED-1932",
            query="How to enable SELinux?",
            problem_type="OTHER",
            components=["security", "selinux"],
            rhel_versions=["9"],
            keywords=["selinux", "security", "enforcement"],
        ),
        TicketClassification(
            ticket_key="RSPEED-1933",
            query="How to install packages using dnf?",
            problem_type="OTHER",
            components=["packages", "dnf"],
            rhel_versions=["8", "9"],
            keywords=["dnf", "install", "packages"],
        ),
        TicketClassification(
            ticket_key="RSPEED-1934",
            query="How to manage systemd services?",
            problem_type="OTHER",
            components=["systemd", "services"],
            rhel_versions=[],
            keywords=["systemd", "services", "systemctl"],
        ),
    ]

    print(f"\n🔍 Discovering patterns for {len(classifications)} tickets (real Claude call)")

    # This will make an actual Claude SDK call
    patterns = await agent.discover_patterns(classifications)

    print(f"✅ Discovered {len(patterns)} patterns")

    for pattern in patterns:
        print(f"\n  Pattern: {pattern.pattern_id}")
        print(f"    Description: {pattern.description}")
        print(f"    Tickets: {pattern.ticket_count}")
        print(f"    Matched: {pattern.matched_tickets}")

    # With only 5 tickets all of type OTHER, may find 0-1 patterns
    assert isinstance(patterns, list)
