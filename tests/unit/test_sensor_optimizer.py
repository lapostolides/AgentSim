"""Tests for the sensor optimizer BO loop (11-03).

Verifies the full Bayesian optimization pipeline: parameter extraction,
search bounds, normalization, evaluation, per-family optimization, and
multi-family orchestration via optimize_sensors.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agentsim.knowledge_graph.models import (
    FAMILY_SCHEMAS,
    ConfidenceQualifier,
    ConstraintSatisfaction,
    FeasibilityResult,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorConfig,
    SensorFamily,
    SensorNode,
    TemporalProps,
)
from agentsim.knowledge_graph.optimizer.models import (
    BOMetadata,
    CostWeights,
    FamilyOptimizationResult,
    OptimizationResult,
)
from agentsim.knowledge_graph.ranges import ParameterRange, SensorFamilyRanges


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_spad_sensor(
    name: str = "TestSPAD",
    dead_time_ns: float = 15.0,
    afterpulsing_probability: float = 0.005,
    crosstalk_probability: float = 0.01,
    fill_factor: float = 0.10,
    pde: float = 0.30,
) -> SensorNode:
    """Create a minimal SPAD sensor for testing."""
    return SensorNode(
        name=name,
        family=SensorFamily.SPAD,
        geometric=GeometricProps(fov=20.0),
        temporal=TemporalProps(temporal_resolution=50.0, temporal_resolution_unit="picosecond"),
        radiometric=RadiometricProps(quantum_efficiency=0.30),
        operational=OperationalProps(
            cost_min_usd=100.0,
            cost_max_usd=500.0,
            power_w=2.0,
            weight_g=50.0,
        ),
        family_specs={
            "dead_time_ns": dead_time_ns,
            "afterpulsing_probability": afterpulsing_probability,
            "crosstalk_probability": crosstalk_probability,
            "fill_factor": fill_factor,
            "pde": pde,
        },
    )


def _make_coded_aperture_sensor(name: str = "TestCA") -> SensorNode:
    """Create a coded aperture sensor (has a string param: mask_pattern_type)."""
    return SensorNode(
        name=name,
        family=SensorFamily.CODED_APERTURE,
        geometric=GeometricProps(fov=30.0),
        temporal=TemporalProps(),
        radiometric=RadiometricProps(),
        operational=OperationalProps(
            cost_min_usd=50.0,
            cost_max_usd=200.0,
            power_w=1.0,
            weight_g=30.0,
        ),
        family_specs={
            "mask_pattern_type": "MURA",
            "mask_transmittance": 0.5,
            "psf_condition_number": 10.0,
        },
    )


def _make_spad_ranges() -> SensorFamilyRanges:
    """Create SPAD family ranges for testing."""
    return SensorFamilyRanges(
        family=SensorFamily.SPAD,
        display_name="SPAD",
        ranges={
            "dead_time_ns": ParameterRange(min=5.0, max=50.0, typical=15.0),
            "afterpulsing_probability": ParameterRange(min=0.001, max=0.01, typical=0.005),
            "crosstalk_probability": ParameterRange(min=0.001, max=0.05, typical=0.01),
            "fill_factor": ParameterRange(min=0.05, max=0.40, typical=0.10),
            "pde": ParameterRange(min=0.15, max=0.50, typical=0.30),
        },
    )


def _make_ca_ranges() -> SensorFamilyRanges:
    """Create coded aperture family ranges for testing."""
    return SensorFamilyRanges(
        family=SensorFamily.CODED_APERTURE,
        display_name="Coded Aperture",
        ranges={
            "mask_transmittance": ParameterRange(min=0.1, max=0.9, typical=0.5),
            "psf_condition_number": ParameterRange(min=1.0, max=100.0, typical=10.0),
        },
    )


def _make_feasibility_result(
    families: tuple[tuple[str, SensorFamily], ...] = (
        ("TestSPAD", SensorFamily.SPAD),
    ),
) -> FeasibilityResult:
    """Create a FeasibilityResult with ranked configs for testing."""
    configs = tuple(
        SensorConfig(
            sensor_name=name,
            sensor_family=family,
            algorithm_name="test_algo",
            rank=i + 1,
            feasibility_score=0.9 - i * 0.1,
        )
        for i, (name, family) in enumerate(families)
    )
    return FeasibilityResult(
        query_text="test query",
        ranked_configs=configs,
    )


# ---------------------------------------------------------------------------
# Tests for _numeric_params
# ---------------------------------------------------------------------------


class TestNumericParams:
    """Test _numeric_params extracts only float/int-typed keys."""

    def test_spad_returns_all_float_params(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _numeric_params

        params = _numeric_params(SensorFamily.SPAD)
        expected = {"dead_time_ns", "afterpulsing_probability", "crosstalk_probability",
                    "fill_factor", "pde"}
        assert set(params) == expected

    def test_coded_aperture_excludes_string_params(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _numeric_params

        params = _numeric_params(SensorFamily.CODED_APERTURE)
        assert "mask_pattern_type" not in params
        assert "mask_transmittance" in params
        assert "psf_condition_number" in params

    def test_structured_light_excludes_string_params(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _numeric_params

        params = _numeric_params(SensorFamily.STRUCTURED_LIGHT)
        assert "pattern_type" not in params
        assert "projector_resolution" not in params
        assert "baseline_mm" in params


# ---------------------------------------------------------------------------
# Tests for _build_search_bounds
# ---------------------------------------------------------------------------


class TestBuildSearchBounds:
    """Test search bounds construction from ParameterRange."""

    def test_returns_correct_shape(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _build_search_bounds

        ranges = _make_spad_ranges()
        params = ["dead_time_ns", "pde", "fill_factor"]
        bounds = _build_search_bounds(ranges, params)
        assert bounds.shape == (3, 2)

    def test_uses_min_max_from_ranges(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _build_search_bounds

        ranges = _make_spad_ranges()
        params = ["pde"]
        bounds = _build_search_bounds(ranges, params)
        assert bounds[0, 0] == pytest.approx(0.15)
        assert bounds[0, 1] == pytest.approx(0.50)

    def test_log_scale_for_wide_ranges(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _build_search_bounds

        # Create a range spanning >100x
        wide_ranges = SensorFamilyRanges(
            family=SensorFamily.SPAD,
            ranges={
                "test_param": ParameterRange(min=0.01, max=10.0, typical=1.0),
            },
        )
        bounds = _build_search_bounds(wide_ranges, ["test_param"])
        # Should use log10 scale: log10(0.01)=-2, log10(10)=1
        assert bounds[0, 0] == pytest.approx(-2.0)
        assert bounds[0, 1] == pytest.approx(1.0)

    def test_fallback_to_typical_when_min_max_none(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _build_search_bounds

        ranges = SensorFamilyRanges(
            family=SensorFamily.SPAD,
            ranges={
                "test_param": ParameterRange(typical=10.0),
            },
        )
        bounds = _build_search_bounds(ranges, ["test_param"])
        assert bounds[0, 0] == pytest.approx(5.0)
        assert bounds[0, 1] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Tests for _denormalize
# ---------------------------------------------------------------------------


class TestDenormalize:
    """Test denormalization from [0,1] back to physical space."""

    def test_endpoints(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _denormalize

        bounds = np.array([[5.0, 50.0]])
        assert _denormalize(np.array([0.0]), bounds) == pytest.approx(np.array([5.0]))
        assert _denormalize(np.array([1.0]), bounds) == pytest.approx(np.array([50.0]))

    def test_midpoint(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _denormalize

        bounds = np.array([[0.0, 10.0]])
        assert _denormalize(np.array([0.5]), bounds) == pytest.approx(np.array([5.0]))


# ---------------------------------------------------------------------------
# Tests for _evaluate_point
# ---------------------------------------------------------------------------


class TestEvaluatePoint:
    """Test single-point evaluation of CRB + cost + constraint margin."""

    @patch("agentsim.knowledge_graph.optimizer.optimizer.compute_crb")
    @patch("agentsim.knowledge_graph.optimizer.optimizer.check_constraints")
    def test_returns_three_tuple(self, mock_constraints, mock_crb) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _evaluate_point

        mock_crb.return_value = MagicMock(bound_value=0.5, bound_unit="meter")
        mock_constraints.return_value = (
            ConstraintSatisfaction(
                constraint_name="range_m", satisfied=True, margin=1.0
            ),
        )

        sensor = _make_spad_sensor()
        crb, cost, neg_margin = _evaluate_point(
            sensor=sensor,
            estimation_task="depth",
            constraints={"range_m": 3.0},
            cost_weights=CostWeights(),
            family_cost_range=(0.0, 1000.0),
            family_power_range=(0.0, 10.0),
            family_weight_range=(0.0, 500.0),
        )
        assert crb == pytest.approx(0.5)
        assert isinstance(cost, float)
        assert neg_margin < 0.0  # feasible => negative negated margin

    @patch("agentsim.knowledge_graph.optimizer.optimizer.compute_crb")
    def test_inf_crb_returns_inf_tuple(self, mock_crb) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _evaluate_point

        mock_crb.return_value = MagicMock(bound_value=float("inf"))

        sensor = _make_spad_sensor()
        crb, cost, neg_margin = _evaluate_point(
            sensor=sensor,
            estimation_task="depth",
            constraints={},
            cost_weights=CostWeights(),
            family_cost_range=(0.0, 1.0),
            family_power_range=(0.0, 1.0),
            family_weight_range=(0.0, 1.0),
        )
        assert crb == float("inf")
        assert cost == float("inf")
        assert neg_margin == float("inf")


# ---------------------------------------------------------------------------
# Tests for _load_sensor_by_name
# ---------------------------------------------------------------------------


class TestLoadSensorByName:
    """Test sensor lookup by name from YAML."""

    @patch("agentsim.knowledge_graph.optimizer.optimizer.load_sensors")
    def test_finds_sensor_by_name(self, mock_load) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _load_sensor_by_name

        sensor = _make_spad_sensor(name="MySPAD")
        mock_load.return_value = (_make_spad_sensor(name="Other"), sensor)

        result = _load_sensor_by_name("MySPAD", SensorFamily.SPAD)
        assert result.name == "MySPAD"
        mock_load.assert_called_once_with(families=(SensorFamily.SPAD,))

    @patch("agentsim.knowledge_graph.optimizer.optimizer.load_sensors")
    def test_raises_when_not_found(self, mock_load) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _load_sensor_by_name

        mock_load.return_value = (_make_spad_sensor(name="Other"),)

        with pytest.raises(ValueError, match="not found"):
            _load_sensor_by_name("NonExistent", SensorFamily.SPAD)


# ---------------------------------------------------------------------------
# Tests for _optimize_family
# ---------------------------------------------------------------------------


class TestOptimizeFamily:
    """Test per-family Bayesian optimization loop."""

    @patch("agentsim.knowledge_graph.optimizer.optimizer.compute_crb")
    @patch("agentsim.knowledge_graph.optimizer.optimizer.check_constraints")
    def test_returns_family_result_with_pareto_front(
        self, mock_constraints, mock_crb
    ) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _optimize_family

        # CRB returns a finite value that varies with parameters
        call_count = {"n": 0}
        def crb_side_effect(sensor, task, **kwargs):
            call_count["n"] += 1
            # Vary CRB based on pde to create a non-trivial landscape
            pde = sensor.family_specs.get("pde", 0.3)
            return MagicMock(
                bound_value=1.0 / (pde + 0.01),
                bound_unit="meter",
                confidence=ConfidenceQualifier.ANALYTICAL,
            )

        mock_crb.side_effect = crb_side_effect
        mock_constraints.return_value = (
            ConstraintSatisfaction(
                constraint_name="range_m", satisfied=True, margin=2.0
            ),
        )

        sensor = _make_spad_sensor()
        ranges = _make_spad_ranges()

        result = _optimize_family(
            base_sensor=sensor,
            family_ranges=ranges,
            estimation_task="depth",
            constraints={"range_m": 3.0},
            cost_weights=CostWeights(),
        )

        assert isinstance(result, FamilyOptimizationResult)
        assert result.family == SensorFamily.SPAD
        assert len(result.pareto_front) >= 1
        assert result.bo_metadata is not None
        assert result.bo_metadata.evaluations > 0

    @patch("agentsim.knowledge_graph.optimizer.optimizer.compute_crb")
    @patch("agentsim.knowledge_graph.optimizer.optimizer.check_constraints")
    def test_converges_on_flat_objective(self, mock_constraints, mock_crb) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import _optimize_family

        # Constant CRB = flat surface => should converge quickly
        mock_crb.return_value = MagicMock(
            bound_value=1.0,
            bound_unit="meter",
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        mock_constraints.return_value = (
            ConstraintSatisfaction(
                constraint_name="range_m", satisfied=True, margin=2.0
            ),
        )

        sensor = _make_spad_sensor()
        ranges = _make_spad_ranges()

        result = _optimize_family(
            base_sensor=sensor,
            family_ranges=ranges,
            estimation_task="depth",
            constraints={"range_m": 3.0},
            cost_weights=CostWeights(),
        )

        assert result.bo_metadata is not None
        assert result.bo_metadata.converged is True


# ---------------------------------------------------------------------------
# Tests for optimize_sensors
# ---------------------------------------------------------------------------


class TestOptimizeSensors:
    """Test the top-level multi-family optimization."""

    @patch("agentsim.knowledge_graph.optimizer.optimizer.load_family_ranges")
    @patch("agentsim.knowledge_graph.optimizer.optimizer._load_sensor_by_name")
    @patch("agentsim.knowledge_graph.optimizer.optimizer._optimize_family")
    def test_two_families_returns_two_results(
        self, mock_opt_family, mock_load_sensor, mock_load_ranges
    ) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import optimize_sensors

        spad_sensor = _make_spad_sensor()
        ca_sensor = _make_coded_aperture_sensor()

        mock_load_sensor.side_effect = lambda name, family: (
            spad_sensor if family == SensorFamily.SPAD else ca_sensor
        )
        mock_load_ranges.return_value = {
            SensorFamily.SPAD: _make_spad_ranges(),
            SensorFamily.CODED_APERTURE: _make_ca_ranges(),
        }
        mock_opt_family.return_value = FamilyOptimizationResult(
            family=SensorFamily.SPAD,
            pareto_front=(),
            bo_metadata=BOMetadata(
                evaluations=10, converged=True,
                final_acquisition_improvement=0.001,
                computation_time_s=1.0,
            ),
        )

        feasibility = _make_feasibility_result(
            families=(
                ("TestSPAD", SensorFamily.SPAD),
                ("TestCA", SensorFamily.CODED_APERTURE),
            )
        )

        result = optimize_sensors(feasibility)
        assert isinstance(result, OptimizationResult)
        assert len(result.family_results) == 2

    def test_empty_ranked_configs_returns_empty(self) -> None:
        from agentsim.knowledge_graph.optimizer.optimizer import optimize_sensors

        feasibility = FeasibilityResult(query_text="empty", ranked_configs=())
        result = optimize_sensors(feasibility)
        assert isinstance(result, OptimizationResult)
        assert len(result.family_results) == 0
        assert result.total_evaluations == 0

    @patch("agentsim.knowledge_graph.optimizer.optimizer.load_family_ranges")
    @patch("agentsim.knowledge_graph.optimizer.optimizer._load_sensor_by_name")
    @patch("agentsim.knowledge_graph.optimizer.optimizer._optimize_family")
    def test_full_pareto_front_no_scope_filtering(
        self, mock_opt_family, mock_load_sensor, mock_load_ranges
    ) -> None:
        """D-05: optimize_sensors returns FULL unfiltered Pareto front."""
        from agentsim.knowledge_graph.optimizer.optimizer import optimize_sensors

        mock_load_sensor.return_value = _make_spad_sensor()
        mock_load_ranges.return_value = {
            SensorFamily.SPAD: _make_spad_ranges(),
        }

        # Return a result with 10 Pareto points
        from agentsim.knowledge_graph.optimizer.models import ParetoPoint
        points = tuple(
            ParetoPoint(
                sensor_name="TestSPAD",
                family=SensorFamily.SPAD,
                parameter_values={"pde": 0.2 + i * 0.03},
                crb_bound=1.0 + i * 0.1,
                crb_unit="meter",
                operational_cost=0.5 - i * 0.04,
                constraint_margin=1.0,
                confidence=ConfidenceQualifier.ANALYTICAL,
            )
            for i in range(10)
        )
        mock_opt_family.return_value = FamilyOptimizationResult(
            family=SensorFamily.SPAD,
            pareto_front=points,
            bo_metadata=BOMetadata(
                evaluations=50, converged=True,
                final_acquisition_improvement=0.001,
                computation_time_s=2.0,
            ),
        )

        feasibility = _make_feasibility_result()
        result = optimize_sensors(feasibility)

        # All 10 points should be present (no scope filtering)
        assert len(result.family_results[0].pareto_front) == 10
