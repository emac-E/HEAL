"""Tests for stability classification module."""

import pytest
from heal.core.stability_classifier import (
    StabilityStatus,
    classify_stability,
    format_classification_summary,
)


class TestStabilityClassifier:
    """Test stability classification across multiple evaluation runs."""

    def test_stable_passing(self):
        """All runs pass with low variance → STABLE_PASSING."""
        runs = [0.92, 0.91, 0.93, 0.91]
        result = classify_stability(runs, threshold=0.90)

        assert result.status == StabilityStatus.STABLE_PASSING
        assert result.skip is True
        assert result.needs_review is False
        assert result.priority == "LOW"
        assert result.failure_rate == 0.0
        assert 0.91 <= result.mean_score <= 0.92

    def test_unstable_passing(self):
        """All runs pass but high variance → UNSTABLE_PASSING."""
        # All above threshold but with high variance
        # Wide spread: 0.90 to 1.0 should give CV > 0.15
        runs = [1.0, 0.90, 1.0, 0.90, 1.0, 0.90]
        result = classify_stability(runs, threshold=0.90, high_cv_threshold=0.05)

        assert result.status == StabilityStatus.UNSTABLE_PASSING
        assert result.skip is True  # Skip but flag for review
        assert result.needs_review is True
        assert result.priority == "LOW"
        assert result.coefficient_of_variation > 0.05  # High variance

    def test_intermittent_failure_masked_by_averaging(self):
        """Catastrophic failure hidden by averaging → INTERMITTENT_FAILURE.

        This is the critical case: [0.95, 0.50, 0.95, 0.92]
        - Average: 0.83 (looks borderline)
        - Reality: One catastrophic failure (0.50)
        """
        runs = [0.95, 0.50, 0.95, 0.92]
        result = classify_stability(runs, threshold=0.90, catastrophic_threshold=0.70)

        assert result.status == StabilityStatus.INTERMITTENT_FAILURE
        assert result.skip is False  # Must fix
        assert result.needs_review is True  # Investigate why it fails sometimes
        assert result.priority == "HIGH"
        assert result.failure_rate == 0.25  # 1/4 runs failed
        assert result.min_score == 0.50  # Detected catastrophic failure

    def test_borderline(self):
        """Some runs barely fail, some pass → BORDERLINE."""
        runs = [0.88, 0.91, 0.87, 0.90]
        result = classify_stability(runs, threshold=0.90)

        assert result.status == StabilityStatus.BORDERLINE
        assert result.skip is False
        assert result.needs_review is False
        assert result.priority == "MEDIUM"
        assert result.failure_rate == 0.5  # 2/4 runs failed
        assert result.min_score < 0.90

    def test_consistently_failing(self):
        """All runs fail → CONSISTENTLY_FAILING."""
        runs = [0.65, 0.68, 0.62, 0.70]
        result = classify_stability(runs, threshold=0.90)

        assert result.status == StabilityStatus.CONSISTENTLY_FAILING
        assert result.skip is False
        assert result.needs_review is False
        assert result.priority == "HIGH"
        assert result.failure_rate == 1.0
        assert result.max_score < 0.90

    def test_single_run(self):
        """Single run (no std dev) → classified by pass/fail only."""
        # Passing
        result_pass = classify_stability([0.95], threshold=0.90)
        assert result_pass.status == StabilityStatus.STABLE_PASSING
        assert result_pass.std_dev == 0.0
        assert result_pass.coefficient_of_variation == 0.0

        # Failing
        result_fail = classify_stability([0.75], threshold=0.90)
        assert result_fail.status == StabilityStatus.CONSISTENTLY_FAILING
        assert result_fail.failure_rate == 1.0

    def test_measurement_noise_vs_intermittent_failure(self):
        """Distinguish measurement noise from real intermittent failures.

        Noise: [0.88, 0.90, 0.85, 0.92] - all close to threshold
        Intermittent: [0.95, 0.50, 0.95, 0.92] - one catastrophic fail
        """
        # Measurement noise (borderline)
        noise = [0.88, 0.90, 0.85, 0.92]
        result_noise = classify_stability(noise, threshold=0.90)
        assert result_noise.status == StabilityStatus.BORDERLINE
        assert result_noise.min_score >= 0.85  # No catastrophic failures

        # Intermittent failure (catastrophic)
        intermittent = [0.95, 0.50, 0.95, 0.92]
        result_intermittent = classify_stability(
            intermittent, threshold=0.90, catastrophic_threshold=0.70
        )
        assert result_intermittent.status == StabilityStatus.INTERMITTENT_FAILURE
        assert result_intermittent.min_score < 0.70  # Catastrophic failure detected

    def test_custom_thresholds(self):
        """Test with custom thresholds."""
        runs = [0.72, 0.75, 0.78, 0.74]

        # With threshold=0.75, some fail
        result_075 = classify_stability(runs, threshold=0.75)
        assert result_075.failure_rate > 0.0

        # With threshold=0.70, all pass
        result_070 = classify_stability(runs, threshold=0.70)
        assert result_070.failure_rate == 0.0
        assert result_070.status in [
            StabilityStatus.STABLE_PASSING,
            StabilityStatus.UNSTABLE_PASSING,
        ]

    def test_format_classification_summary(self):
        """Test formatting of classification results."""
        runs = [0.95, 0.50, 0.95, 0.92]
        result = classify_stability(runs, threshold=0.90)

        summary = format_classification_summary(result)

        assert "INTERMITTENT_FAILURE" in summary
        assert "Min:" in summary
        assert "0.500" in summary  # min score
        assert "Skip:" in summary
        assert "Priority:" in summary

    def test_empty_runs_raises_error(self):
        """Empty runs list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            classify_stability([])

    def test_coefficient_of_variation(self):
        """Test CV calculation (normalized variance)."""
        # Low variance
        low_variance = [0.91, 0.92, 0.91, 0.92]
        result_low = classify_stability(low_variance)
        assert result_low.coefficient_of_variation < 0.01

        # High variance
        high_variance = [0.70, 0.95, 0.75, 0.90]
        result_high = classify_stability(high_variance)
        assert result_high.coefficient_of_variation > 0.10

    def test_all_metrics_populated(self):
        """Verify all metrics are populated in result."""
        runs = [0.85, 0.90, 0.88, 0.92]
        result = classify_stability(runs, threshold=0.90)

        assert result.status is not None
        assert result.reason != ""
        assert 0.0 <= result.failure_rate <= 1.0
        assert result.min_score <= result.mean_score <= result.max_score
        assert result.std_dev >= 0.0
        assert result.coefficient_of_variation >= 0.0
        assert isinstance(result.skip, bool)
        assert isinstance(result.needs_review, bool)
        assert result.priority in ["HIGH", "MEDIUM", "LOW"]
