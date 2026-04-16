"""Data models for evaluation tickets matching lightspeed-evaluation YAML schema.

Simple dataclasses that map directly to YAML structure.
Use dataclasses.asdict() to convert to dict for YAML output.

Reference: /home/emackey/Work/lightspeed-core/lightspeed-evaluation/src/lightspeed_evaluation/core/models/data.py
"""

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class Turn:
    """Single turn in a conversation.

    Matches lightspeed-evaluation TurnData YAML structure.
    """

    # Required
    turn_id: str
    query: str

    # Optional - populated by API or provided for validation
    response: Optional[str] = None
    contexts: Optional[list[str]] = None

    # Expected values for evaluation
    expected_response: Optional[Union[str, list[str]]] = None
    expected_urls: Optional[list[str]] = None
    expected_keywords: Optional[list[list[str]]] = None
    forbidden_claims: Optional[list[str]] = None

    # Quality metadata from extraction (Review Agent score)
    review_score: Optional[float] = None  # Score from autonomous review loop (0.0-1.0)

    # Optional - metrics override (usually use system defaults via --metrics CLI flag)
    turn_metrics: Optional[list[str]] = None

    # Token usage tracking
    api_input_tokens: int = 0
    api_output_tokens: int = 0


@dataclass
class Conversation:
    """Conversation group - matches lightspeed-evaluation EvaluationData YAML structure."""

    # Required
    conversation_group_id: str
    turns: list[Turn] = field(default_factory=list)

    # Optional
    description: Optional[str] = None
    tag: str = "eval"
