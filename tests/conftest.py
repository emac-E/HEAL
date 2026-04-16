"""Pytest configuration for HEAL tests.

HEAL's Claude agents use ADC (gcloud auth application-default login).

The .env file is for lightspeed-evaluation integration:
- Sets credentials for the evaluation judge LLM
- Sets credentials for the LLM under test
- Not needed for HEAL's Claude Agent SDK (uses ADC)
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env for lightspeed-evaluation integration."""
    heal_root = Path(__file__).parent.parent
    env_file = heal_root / ".env"

    if env_file.exists():
        load_dotenv(env_file, override=True)


@pytest.fixture
def unset_google_creds_for_claude():
    """Temporarily unset GOOGLE_APPLICATION_CREDENTIALS for Claude SDK tests.

    Claude Agent SDK uses ADC. GOOGLE_APPLICATION_CREDENTIALS (set by .env
    for lightspeed-evaluation's judge) can interfere with Claude SDK.

    Usage:
        @pytest.mark.asyncio
        async def test_claude(unset_google_creds_for_claude):
            # Claude SDK calls work here
    """
    saved = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    yield
    if saved:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = saved
