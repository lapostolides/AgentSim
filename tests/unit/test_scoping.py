"""Tests for optimizer scoping module -- scope filtering and auto-detection."""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily
from agentsim.knowledge_graph.optimizer.models import (
    BOMetadata,
    FamilyOptimizationResult,
    OptimizationResult,
    ParetoPoint,
)
from agentsim.knowledge_graph.optimizer.scoping import (
    VALID_SCOPES,
    detect_scope,
    filter_by_scope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_point(family: SensorFamily, crb: float, name: str = "sensor") -> ParetoPoint:
    """Create a ParetoPoint with the given family and CRB bound."""
    return ParetoPoint(
        sensor_name=name,
        family=family,
        parameter_values={"param": 1.0},
        crb_bound=crb,
        crb_unit="m",
        operational_cost=10.0,
        constraint_margin=0.5,
        confidence=ConfidenceQualifier.ANALYTICAL,
    )


def _make_metadata() -> BOMetadata:
    """Create a BOMetadata instance for testing."""
    return BOMetadata(
        evaluations=50,
        converged=True,
        final_acquisition_improvement=0.001,
        computation_time_s=2.5,
    )


def _make_family_result(
    family: SensorFamily,
    n_points: int,
    *,
    with_metadata: bool = False,
) -> FamilyOptimizationResult:
    """Create a FamilyOptimizationResult with n_points on its Pareto front."""
    points = tuple(
        _make_point(family, crb=float(i + 1), name=f"sensor_{i}")
        for i in range(n_points)
    )
    metadata = _make_metadata() if with_metadata else None
    return FamilyOptimizationResult(
        family=family,
        pareto_front=points,
        bo_metadata=metadata,
    )


# ---------------------------------------------------------------------------
# filter_by_scope tests
# ---------------------------------------------------------------------------


class TestFilterByScope:
    """Tests for filter_by_scope function."""

    def test_wide_returns_all_pareto_points(self) -> None:
        """Wide scope preserves all Pareto points across all families."""
        spad_result = _make_family_result(SensorFamily.SPAD, 10)
        tof_result = _make_family_result(SensorFamily.CW_TOF, 8)
        result = OptimizationResult(family_results=(spad_result, tof_result))

        filtered = filter_by_scope(result, "wide")

        assert len(filtered.family_results[0].pareto_front) == 10
        assert len(filtered.family_results[1].pareto_front) == 8
        assert filtered.scope == "wide"

    def test_medium_returns_at_most_5_per_family(self) -> None:
        """Medium scope caps at 5 points per family, sorted by crb_bound ascending."""
        spad_result = _make_family_result(SensorFamily.SPAD, 10)
        result = OptimizationResult(family_results=(spad_result,))

        filtered = filter_by_scope(result, "medium")

        front = filtered.family_results[0].pareto_front
        assert len(front) == 5
        # Sorted ascending by crb_bound
        crbs = [p.crb_bound for p in front]
        assert crbs == sorted(crbs)
        assert filtered.scope == "medium"

    def test_narrow_returns_exactly_1_per_family(self) -> None:
        """Narrow scope returns single best (lowest crb_bound) per family."""
        spad_result = _make_family_result(SensorFamily.SPAD, 10)
        result = OptimizationResult(family_results=(spad_result,))

        filtered = filter_by_scope(result, "narrow")

        front = filtered.family_results[0].pareto_front
        assert len(front) == 1
        assert front[0].crb_bound == 1.0  # lowest
        assert filtered.scope == "narrow"

    def test_narrow_on_empty_pareto_front(self) -> None:
        """Narrow scope on empty Pareto front returns empty tuple."""
        empty_result = FamilyOptimizationResult(family=SensorFamily.SPAD, pareto_front=())
        result = OptimizationResult(family_results=(empty_result,))

        filtered = filter_by_scope(result, "narrow")

        assert filtered.family_results[0].pareto_front == ()

    def test_preserves_bo_metadata(self) -> None:
        """Filtering preserves FamilyOptimizationResult.bo_metadata unchanged."""
        spad_result = _make_family_result(SensorFamily.SPAD, 10, with_metadata=True)
        metadata = spad_result.bo_metadata
        result = OptimizationResult(family_results=(spad_result,))

        filtered = filter_by_scope(result, "narrow")

        assert filtered.family_results[0].bo_metadata is metadata

    def test_raises_for_unknown_scope(self) -> None:
        """Unknown scope string raises ValueError."""
        result = OptimizationResult()
        with pytest.raises(ValueError, match="unknown"):
            filter_by_scope(result, "super_wide")

    def test_returns_new_object(self) -> None:
        """filter_by_scope returns a new OptimizationResult, not the same object."""
        result = OptimizationResult(
            family_results=(_make_family_result(SensorFamily.SPAD, 3),)
        )
        filtered = filter_by_scope(result, "wide")
        assert filtered is not result


# ---------------------------------------------------------------------------
# detect_scope tests
# ---------------------------------------------------------------------------


class TestDetectScope:
    """Tests for detect_scope function."""

    def test_narrow_for_specific_sensor_name(self) -> None:
        """Hypothesis mentioning a specific sensor model returns narrow."""
        assert detect_scope("Evaluate SwissSPAD2 for cave mapping") == "narrow"

    def test_wide_for_comparison_language(self) -> None:
        """Hypothesis with comparison language returns wide."""
        assert detect_scope("Compare sensors for underwater imaging") == "wide"

    def test_medium_for_generic_hypothesis(self) -> None:
        """Generic hypothesis without sensor names or comparison returns medium."""
        assert detect_scope("Improve depth estimation accuracy") == "medium"

    def test_medium_for_empty_string(self) -> None:
        """Empty string defaults to medium."""
        assert detect_scope("") == "medium"

    def test_case_insensitive_detection(self) -> None:
        """Detection is case-insensitive."""
        assert detect_scope("COMPARE SENSORS for depth") == "wide"
        assert detect_scope("Use HAMAMATSU sensor") == "narrow"


# ---------------------------------------------------------------------------
# VALID_SCOPES constant
# ---------------------------------------------------------------------------


class TestValidScopes:
    """Tests for the VALID_SCOPES constant."""

    def test_contains_all_three_scopes(self) -> None:
        assert VALID_SCOPES == frozenset({"wide", "medium", "narrow"})
