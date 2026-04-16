"""Statistical stability classification for multi-run evaluation results.

This module provides tools to analyze evaluation results across multiple runs
and detect patterns that averaging would mask:
- Intermittent failures (some runs fail catastrophically)
- Borderline performance (some runs barely pass/fail)
- Unstable passing (all pass but high variance)
- Stable passing (consistent good performance)
"""

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import List


class StabilityStatus(Enum):
    """Classification of ticket stability across multiple runs."""

    STABLE_PASSING = "STABLE_PASSING"  # All passed, low variance
    UNSTABLE_PASSING = "UNSTABLE_PASSING"  # All passed, high variance
    BORDERLINE = "BORDERLINE"  # Some close failures, some passes
    INTERMITTENT_FAILURE = "INTERMITTENT_FAILURE"  # Some catastrophic failures
    CONSISTENTLY_FAILING = "CONSISTENTLY_FAILING"  # All runs failed


@dataclass
class StabilityClassification:
    """Result of stability analysis for a ticket."""

    status: StabilityStatus
    reason: str
    failure_rate: float  # 0.0 to 1.0
    min_score: float
    max_score: float
    mean_score: float
    std_dev: float
    coefficient_of_variation: float  # CV = std_dev / mean (normalized variance)
    skip: bool  # Should this ticket be skipped in next iteration?
    needs_review: bool  # Needs human review (unstable, intermittent)
    priority: str  # HIGH, MEDIUM, LOW


def classify_stability(
    runs: List[float],
    threshold: float = 0.90,
    catastrophic_threshold: float = 0.70,
    high_cv_threshold: float = 0.15,
) -> StabilityClassification:
    """Statistically classify ticket stability across multiple runs.

    Detects patterns that averaging would mask:
    - [0.95, 0.50, 0.95, 0.92] → INTERMITTENT_FAILURE (not avg=0.83)
    - [0.88, 0.90, 0.85, 0.92] → UNSTABLE_PASSING (not "high variance")

    Args:
        runs: List of scores from multiple evaluation runs
        threshold: Passing threshold (default: 0.90)
        catastrophic_threshold: Below this is catastrophic failure (default: 0.70)
        high_cv_threshold: Coefficient of variation threshold for instability (default: 0.15)

    Returns:
        StabilityClassification with status, metrics, and recommendations
    """
    if not runs:
        raise ValueError("Cannot classify stability with empty runs list")

    min_score = min(runs)
    max_score = max(runs)
    mean_score = statistics.mean(runs)
    std_dev = statistics.stdev(runs) if len(runs) > 1 else 0.0

    # Coefficient of variation (normalized variance)
    cv = std_dev / mean_score if mean_score > 0 else 0.0

    # Count failures
    failure_count = sum(1 for r in runs if r < threshold)
    failure_rate = failure_count / len(runs)

    # Classify based on failure pattern
    if failure_rate == 1.0:
        # All runs failed
        status = StabilityStatus.CONSISTENTLY_FAILING
        reason = f"All {len(runs)} runs failed (mean={mean_score:.2f})"
        skip = False
        needs_review = False
        priority = "HIGH"

    elif failure_count > 0:
        # At least one run failed - check severity
        if min_score < catastrophic_threshold:
            # Catastrophic failure in at least one run
            status = StabilityStatus.INTERMITTENT_FAILURE
            reason = (
                f"{failure_count}/{len(runs)} runs failed, "
                f"min={min_score:.2f} (catastrophic < {catastrophic_threshold})"
            )
            skip = False
            needs_review = True  # Intermittent issues need investigation
            priority = "HIGH"
        else:
            # Close to threshold failures
            status = StabilityStatus.BORDERLINE
            reason = f"{failure_count}/{len(runs)} runs failed, min={min_score:.2f}"
            skip = False
            needs_review = False
            priority = "MEDIUM"

    else:
        # All runs passed - check stability
        if cv > high_cv_threshold:
            # High variance despite passing
            status = StabilityStatus.UNSTABLE_PASSING
            reason = f"All passed but high variance (CV={cv:.2f}, std={std_dev:.2f})"
            skip = True  # May not be fixable
            needs_review = True  # Investigate why variance is high
            priority = "LOW"
        else:
            # Low variance, all passing
            status = StabilityStatus.STABLE_PASSING
            reason = f"All passed, low variance (CV={cv:.2f})"
            skip = True  # Skip in future iterations
            needs_review = False
            priority = "LOW"

    return StabilityClassification(
        status=status,
        reason=reason,
        failure_rate=failure_rate,
        min_score=min_score,
        max_score=max_score,
        mean_score=mean_score,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        skip=skip,
        needs_review=needs_review,
        priority=priority,
    )


def format_classification_summary(classification: StabilityClassification) -> str:
    """Format classification as human-readable summary.

    Args:
        classification: StabilityClassification to format

    Returns:
        Formatted string with status, metrics, and recommendations
    """
    lines = []

    # Status with emoji
    status_emoji = {
        StabilityStatus.STABLE_PASSING: "✅",
        StabilityStatus.UNSTABLE_PASSING: "⚠️",
        StabilityStatus.BORDERLINE: "❌",
        StabilityStatus.INTERMITTENT_FAILURE: "❌",
        StabilityStatus.CONSISTENTLY_FAILING: "❌",
    }
    emoji = status_emoji.get(classification.status, "❓")

    lines.append(f"{emoji} Status: {classification.status.value}")
    lines.append(f"   {classification.reason}")
    lines.append("")
    lines.append("📊 Metrics:")
    lines.append(f"   Min:         {classification.min_score:.3f}")
    lines.append(f"   Max:         {classification.max_score:.3f}")
    lines.append(f"   Mean:        {classification.mean_score:.3f}")
    lines.append(f"   Std Dev:     {classification.std_dev:.3f}")
    lines.append(f"   CV:          {classification.coefficient_of_variation:.3f}")
    lines.append(f"   Failure Rate: {classification.failure_rate:.1%}")
    lines.append("")
    lines.append("🎯 Recommendations:")
    lines.append(f"   Skip:        {classification.skip}")
    lines.append(f"   Needs Review: {classification.needs_review}")
    lines.append(f"   Priority:    {classification.priority}")

    return "\n".join(lines)
