"""Unit tests for optimizer core: data models, Pareto extraction, and cost computation.

Tests cover frozen Pydantic models, non-dominated sorting with infeasible
point filtering, and weighted normalized operational cost.
"""

from __future__ import annotations

import numpy as np
import pytest

from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorFamily,
    SensorNode,
    TemporalProps,
)
from agentsim.knowledge_graph.optimizer.cost import compute_operational_cost
from agentsim.knowledge_graph.optimizer.models import (
    BOMetadata,
    CostWeights,
    FamilyOptimizationResult,
    OptimizationResult,
    ParetoPoint,
)
from agentsim.knowledge_graph.optimizer.pareto import extract_pareto_front


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sensor(
    name: str = "test_sensor",
    family: SensorFamily = SensorFamily.SPAD,
    operational: OperationalProps | None = None,
) -> SensorNode:
    """Create a minimal SensorNode for testing."""
    return SensorNode(
        name=name,
        family=family,
        geometric=GeometricProps(fov=90.0),
        temporal=TemporalProps(),
        radiometric=RadiometricProps(),
        operational=operational,
        family_specs={
            "dead_time_ns": 50.0,
            "afterpulsing_probability": 0.01,
            "crosstalk_probability": 0.02,
            "fill_factor": 0.5,
            "pde": 0.3,
        },
    )


# ---------------------------------------------------------------------------
# CostWeights tests
# ---------------------------------------------------------------------------


class TestCostWeights:
    """Tests for CostWeights frozen model."""

    def test_default_values(self) -> None:
        w = CostWeights()
        assert w.usd == 0.5
        assert w.power == 0.3
        assert w.weight == 0.2

    def test_defaults_sum_to_one(self) -> None:
        w = CostWeights()
        assert abs(w.usd + w.power + w.weight - 1.0) < 1e-10

    def test_frozen(self) -> None:
        w = CostWeights()
        with pytest.raises(Exception):
            w.usd = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ParetoPoint tests
# ---------------------------------------------------------------------------


class TestParetoPoint:
    """Tests for ParetoPoint frozen model."""

    def test_construction(self) -> None:
        p = ParetoPoint(
            sensor_name="spad_a",
            family=SensorFamily.SPAD,
            parameter_values={"dead_time_ns": 50.0, "pde": 0.3},
            crb_bound=0.01,
            crb_unit="meter",
            operational_cost=0.5,
            constraint_margin=0.8,
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        assert p.sensor_name == "spad_a"
        assert p.family == SensorFamily.SPAD
        assert isinstance(p.parameter_values, dict)
        assert p.crb_bound == 0.01
        assert p.crb_unit == "meter"
        assert p.operational_cost == 0.5
        assert p.constraint_margin == 0.8
        assert p.confidence == ConfidenceQualifier.ANALYTICAL

    def test_frozen(self) -> None:
        p = ParetoPoint(
            sensor_name="spad_a",
            family=SensorFamily.SPAD,
            parameter_values={},
            crb_bound=0.01,
            crb_unit="meter",
            operational_cost=0.5,
            constraint_margin=0.8,
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        with pytest.raises(Exception):
            p.crb_bound = 99.0  # type: ignore[misc]

    def test_parameter_values_is_dict_str_float(self) -> None:
        p = ParetoPoint(
            sensor_name="s",
            family=SensorFamily.RGB,
            parameter_values={"pixel_pitch_um": 3.45},
            crb_bound=0.1,
            crb_unit="m",
            operational_cost=0.0,
            constraint_margin=1.0,
            confidence=ConfidenceQualifier.UNKNOWN,
        )
        for k, v in p.parameter_values.items():
            assert isinstance(k, str)
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# OptimizationResult tests
# ---------------------------------------------------------------------------


class TestOptimizationResult:
    """Tests for OptimizationResult frozen model."""

    def test_construction(self) -> None:
        r = OptimizationResult(
            family_results=(),
            scope="medium",
            cost_weights=CostWeights(),
            total_evaluations=100,
            total_computation_time_s=5.0,
        )
        assert r.scope == "medium"
        assert r.total_evaluations == 100
        assert r.total_computation_time_s == 5.0

    def test_frozen(self) -> None:
        r = OptimizationResult()
        with pytest.raises(Exception):
            r.scope = "wide"  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = OptimizationResult()
        assert r.family_results == ()
        assert r.scope == "medium"
        assert isinstance(r.cost_weights, CostWeights)
        assert r.total_evaluations == 0
        assert r.total_computation_time_s == 0.0


# ---------------------------------------------------------------------------
# extract_pareto_front tests
# ---------------------------------------------------------------------------


class TestExtractParetoFront:
    """Tests for Pareto non-dominated sorting."""

    def test_two_dominated_two_non_dominated(self) -> None:
        # Objectives: minimize all three columns.
        # Row 0: (1, 1, -0.5) -- neg margin col already negated -> margin was 0.5 (feasible)
        # Row 1: (2, 2, -0.5) -- dominated by row 0
        # Row 2: (0.5, 3, -0.5) -- not dominated (better in col0)
        # Row 3: (3, 3, -0.5) -- dominated by row 0
        objectives = np.array([
            [1.0, 1.0, -0.5],
            [2.0, 2.0, -0.5],
            [0.5, 3.0, -0.5],
            [3.0, 3.0, -0.5],
        ])
        indices = extract_pareto_front(objectives)
        assert set(indices.tolist()) == {0, 2}

    def test_all_non_dominated(self) -> None:
        # Each point is better in at least one dimension.
        objectives = np.array([
            [1.0, 3.0, -0.5],
            [2.0, 2.0, -0.5],
            [3.0, 1.0, -0.5],
        ])
        indices = extract_pareto_front(objectives)
        assert set(indices.tolist()) == {0, 1, 2}

    def test_excludes_infeasible_points(self) -> None:
        # Col 2 > 0 means original constraint margin was negative (infeasible).
        # (Margin was negated for minimization, so positive here = originally negative.)
        objectives = np.array([
            [1.0, 1.0, -0.5],   # feasible (margin was 0.5)
            [0.5, 0.5, 0.5],    # infeasible (margin was -0.5)
            [2.0, 2.0, -0.3],   # feasible (margin was 0.3)
        ])
        indices = extract_pareto_front(objectives)
        # Row 1 excluded (infeasible). Row 0 dominates row 2.
        assert set(indices.tolist()) == {0}

    def test_empty_input(self) -> None:
        objectives = np.empty((0, 3))
        indices = extract_pareto_front(objectives)
        assert len(indices) == 0


# ---------------------------------------------------------------------------
# compute_operational_cost tests
# ---------------------------------------------------------------------------


class TestComputeOperationalCost:
    """Tests for operational cost computation."""

    def test_none_operational_returns_zero(self) -> None:
        sensor = _make_sensor(operational=None)
        cost = compute_operational_cost(sensor, CostWeights())
        assert cost == 0.0

    def test_weighted_normalized_sum(self) -> None:
        ops = OperationalProps(cost_max_usd=1000.0, power_w=5.0, weight_g=200.0)
        sensor = _make_sensor(operational=ops)
        weights = CostWeights()  # usd=0.5, power=0.3, weight=0.2

        # Ranges: cost [0, 2000], power [0, 10], weight [0, 500]
        cost = compute_operational_cost(
            sensor,
            weights,
            family_cost_range=(0.0, 2000.0),
            family_power_range=(0.0, 10.0),
            family_weight_range=(0.0, 500.0),
        )
        # norm_cost = 1000/2000 = 0.5
        # norm_power = 5/10 = 0.5
        # norm_weight = 200/500 = 0.4
        expected = 0.5 * 0.5 + 0.3 * 0.5 + 0.2 * 0.4
        assert abs(cost - expected) < 1e-10

    def test_normalizes_with_family_ranges(self) -> None:
        ops = OperationalProps(cost_max_usd=500.0, power_w=3.0, weight_g=100.0)
        sensor = _make_sensor(operational=ops)
        weights = CostWeights(usd=1.0, power=0.0, weight=0.0)

        cost = compute_operational_cost(
            sensor,
            weights,
            family_cost_range=(100.0, 900.0),
        )
        # norm_cost = (500 - 100) / (900 - 100) = 400/800 = 0.5
        expected = 1.0 * 0.5
        assert abs(cost - expected) < 1e-10

    def test_division_by_zero_range(self) -> None:
        ops = OperationalProps(cost_max_usd=100.0, power_w=5.0, weight_g=50.0)
        sensor = _make_sensor(operational=ops)
        weights = CostWeights(usd=1.0, power=0.0, weight=0.0)

        # Same min and max -> span is 0 -> normalized value should be 0.5
        cost = compute_operational_cost(
            sensor,
            weights,
            family_cost_range=(100.0, 100.0),
        )
        expected = 1.0 * 0.5
        assert abs(cost - expected) < 1e-10
