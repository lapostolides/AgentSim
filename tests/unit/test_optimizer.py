"""Tests for optimizer mode -- rank sensor+algorithm combinations.

Covers:
- Single and multi-combo cartesian product
- Computed metrics from propagation
- Score is finite float >= 0
- Descending score sort
- Empty sensors → empty setups
- Real NLOS data integration
- Score heuristic: more metrics → higher score
"""

from __future__ import annotations

import math

import pytest

from agentsim.physics.domains.schema import (
    AlgorithmKnowledge,
    DomainBundle,
    DomainKnowledge,
    ParadigmKnowledge,
    SensorClass,
    TransferFunction,
)
from agentsim.physics.reasoning.models import OptimizerResult, ScoredSetup
from agentsim.physics.reasoning.optimizer import _compute_setup_score, optimize_setup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_paradigm(
    *,
    transfer_functions: tuple[TransferFunction, ...] = (),
    compatible_sensor_classes: tuple[str, ...] = (),
    compatible_algorithms: tuple[str, ...] = (),
) -> ParadigmKnowledge:
    return ParadigmKnowledge(
        paradigm="test_paradigm",
        domain="test_domain",
        transfer_functions=transfer_functions,
        compatible_sensor_classes=compatible_sensor_classes,
        compatible_algorithms=compatible_algorithms,
    )


def _make_sensor_class(
    name: str,
    *,
    transfer_functions: tuple[TransferFunction, ...] = (),
) -> SensorClass:
    return SensorClass(name=name, transfer_functions=transfer_functions)


def _make_algorithm(
    name: str,
    *,
    compatible_paradigms: tuple[str, ...] = ("test_paradigm",),
    transfer_functions: tuple[TransferFunction, ...] = (),
) -> AlgorithmKnowledge:
    return AlgorithmKnowledge(
        name=name,
        algorithm=name,
        compatible_paradigms=compatible_paradigms,
        transfer_functions=transfer_functions,
    )


def _make_bundle(
    *,
    sensor_classes: dict[str, SensorClass] | None = None,
    algorithms: dict[str, AlgorithmKnowledge] | None = None,
) -> DomainBundle:
    return DomainBundle(
        domain=DomainKnowledge(domain="test_domain"),
        sensor_classes=sensor_classes or {},
        algorithms=algorithms or {},
    )


def _simple_tf(
    input_param: str = "temporal_resolution_ps",
    output_param: str = "depth_resolution_m",
    relationship: str = "linear",
    coupling_strength: str = "strong",
) -> TransferFunction:
    return TransferFunction(
        input=input_param,
        output=output_param,
        relationship=relationship,
        coupling_strength=coupling_strength,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOptimizeSetup:
    """Tests for optimize_setup function."""

    def test_single_sensor_single_algorithm(self) -> None:
        """optimize_setup with 1 sensor, 1 algorithm returns 1 ScoredSetup."""
        paradigm = _make_paradigm(
            compatible_sensor_classes=("s1",),
            compatible_algorithms=("a1",),
            transfer_functions=(_simple_tf(),),
        )
        bundle = _make_bundle(
            sensor_classes={"s1": _make_sensor_class("s1")},
            algorithms={"a1": _make_algorithm("a1")},
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        assert isinstance(result, OptimizerResult)
        assert len(result.setups) == 1
        assert result.setups[0].sensor_class == "s1"
        assert result.setups[0].algorithm == "a1"

    def test_cartesian_product_2x2(self) -> None:
        """optimize_setup with 2 sensors, 2 algorithms returns 4 ScoredSetups."""
        paradigm = _make_paradigm(
            compatible_sensor_classes=("s1", "s2"),
            compatible_algorithms=("a1", "a2"),
            transfer_functions=(_simple_tf(),),
        )
        bundle = _make_bundle(
            sensor_classes={
                "s1": _make_sensor_class("s1"),
                "s2": _make_sensor_class("s2"),
            },
            algorithms={
                "a1": _make_algorithm("a1"),
                "a2": _make_algorithm("a2"),
            },
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        assert len(result.setups) == 4

    def test_computed_metrics_populated(self) -> None:
        """ScoredSetup.computed_metrics contains ComputedValue entries."""
        paradigm = _make_paradigm(
            compatible_sensor_classes=("s1",),
            compatible_algorithms=("a1",),
            transfer_functions=(_simple_tf(),),
        )
        bundle = _make_bundle(
            sensor_classes={"s1": _make_sensor_class("s1")},
            algorithms={"a1": _make_algorithm("a1")},
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        setup = result.setups[0]
        assert len(setup.computed_metrics) > 0
        assert setup.computed_metrics[0].parameter == "depth_resolution_m"

    def test_score_is_finite_non_negative(self) -> None:
        """ScoredSetup.score is a finite float >= 0."""
        paradigm = _make_paradigm(
            compatible_sensor_classes=("s1",),
            compatible_algorithms=("a1",),
            transfer_functions=(_simple_tf(),),
        )
        bundle = _make_bundle(
            sensor_classes={"s1": _make_sensor_class("s1")},
            algorithms={"a1": _make_algorithm("a1")},
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        for setup in result.setups:
            assert math.isfinite(setup.score)
            assert setup.score >= 0

    def test_setups_sorted_descending(self) -> None:
        """Setups are sorted by score descending (first = best)."""
        # Give s1 extra TFs for higher score
        paradigm = _make_paradigm(
            compatible_sensor_classes=("s1", "s2"),
            compatible_algorithms=("a1",),
            transfer_functions=(_simple_tf(),),
        )
        bundle = _make_bundle(
            sensor_classes={
                "s1": _make_sensor_class(
                    "s1",
                    transfer_functions=(
                        _simple_tf("temporal_resolution_ps", "extra_metric", "linear", "strong"),
                    ),
                ),
                "s2": _make_sensor_class("s2"),
            },
            algorithms={"a1": _make_algorithm("a1")},
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        scores = [s.score for s in result.setups]
        assert scores == sorted(scores, reverse=True)

    def test_empty_sensors_returns_empty_setups(self) -> None:
        """optimize_setup with no compatible sensors returns empty setups."""
        paradigm = _make_paradigm(
            compatible_sensor_classes=("nonexistent",),
            compatible_algorithms=("a1",),
        )
        bundle = _make_bundle(
            algorithms={"a1": _make_algorithm("a1")},
        )
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        assert isinstance(result, OptimizerResult)
        assert len(result.setups) == 0

    def test_real_nlos_data(self) -> None:
        """Integration: relay_wall + spad_array + lct from YAML returns depth_resolution_m."""
        from agentsim.physics.domains import load_domain_bundle

        bundle = load_domain_bundle("nlos_transient_imaging")
        assert bundle is not None
        paradigm = bundle.paradigms["relay_wall"]
        result = optimize_setup({"temporal_resolution_ps": 32.0}, bundle, paradigm)
        assert len(result.setups) > 0
        # Check depth_resolution_m is in computed metrics
        all_metric_names = {
            cv.parameter for setup in result.setups for cv in setup.computed_metrics
        }
        assert "depth_resolution_m" in all_metric_names


class TestComputeSetupScore:
    """Tests for _compute_setup_score heuristic."""

    def test_more_metrics_higher_score(self) -> None:
        """More computed metrics yields higher score than fewer metrics."""
        from agentsim.physics.reasoning.models import ComputedValue, PropagationResult

        few = PropagationResult(
            computed=(
                ComputedValue(parameter="a", value=1.0),
            ),
        )
        many = PropagationResult(
            computed=(
                ComputedValue(parameter="a", value=1.0),
                ComputedValue(parameter="b", value=2.0),
                ComputedValue(parameter="c", value=3.0),
            ),
        )
        score_few = _compute_setup_score(few, {})
        score_many = _compute_setup_score(many, {})
        assert score_many > score_few
