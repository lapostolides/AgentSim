"""Unit tests for DoE data models: ParameterBound, ParameterSpace, DoEStrategy, SampledDesign."""

from __future__ import annotations

import pytest

from agentsim.experimental_design.models import (
    DoEStrategy,
    DoEStrategyType,
    ParameterBound,
    ParameterSpace,
    SampledDesign,
)
from agentsim.state.models import ParameterSpec


class TestParameterBound:
    """Tests for ParameterBound frozen model."""

    def test_create_basic(self) -> None:
        bound = ParameterBound(name="x", low=0.0, high=1.0)
        assert bound.name == "x"
        assert bound.low == 0.0
        assert bound.high == 1.0
        assert bound.description == ""
        assert bound.log_scale is False

    def test_immutable(self) -> None:
        bound = ParameterBound(name="x", low=0.0, high=1.0)
        with pytest.raises((TypeError, Exception)):
            bound.name = "y"  # type: ignore[misc]

    def test_with_description_and_log_scale(self) -> None:
        bound = ParameterBound(
            name="wavelength", low=400.0, high=700.0,
            description="Visible spectrum", log_scale=True,
        )
        assert bound.description == "Visible spectrum"
        assert bound.log_scale is True


class TestParameterSpace:
    """Tests for ParameterSpace frozen model."""

    def test_dimensionality_one(self) -> None:
        space = ParameterSpace(
            parameters=(ParameterBound(name="x", low=0.0, high=1.0),)
        )
        assert space.dimensionality == 1

    def test_dimensionality_five(self) -> None:
        params = tuple(
            ParameterBound(name=f"p{i}", low=0.0, high=float(i + 1))
            for i in range(5)
        )
        space = ParameterSpace(parameters=params)
        assert space.dimensionality == 5

    def test_names_property(self) -> None:
        space = ParameterSpace(
            parameters=(
                ParameterBound(name="alpha", low=0.0, high=1.0),
                ParameterBound(name="beta", low=0.0, high=2.0),
            )
        )
        assert space.names == ("alpha", "beta")

    def test_bounds_property_salib_format(self) -> None:
        space = ParameterSpace(
            parameters=(
                ParameterBound(name="x", low=0.0, high=1.0),
                ParameterBound(name="y", low=2.0, high=5.0),
            )
        )
        bounds = space.bounds
        assert len(bounds) == 2
        assert bounds[0] == {"name": "x", "bounds": [0.0, 1.0]}
        assert bounds[1] == {"name": "y", "bounds": [2.0, 5.0]}

    def test_immutable(self) -> None:
        space = ParameterSpace(
            parameters=(ParameterBound(name="x", low=0.0, high=1.0),)
        )
        with pytest.raises((TypeError, Exception)):
            space.parameters = ()  # type: ignore[misc]

    def test_from_hypothesis_params_basic(self) -> None:
        specs = [
            ParameterSpec(name="speed", description="m/s", range_min=0.0, range_max=10.0),
            ParameterSpec(name="angle", description="deg", range_min=0.0, range_max=90.0),
        ]
        space = ParameterSpace.from_hypothesis_params(specs)
        assert space.dimensionality == 2
        assert space.names == ("speed", "angle")
        assert space.parameters[0].low == 0.0
        assert space.parameters[0].high == 10.0

    def test_from_hypothesis_params_skips_no_range(self) -> None:
        specs = [
            ParameterSpec(name="speed", range_min=0.0, range_max=10.0),
            ParameterSpec(name="label", description="no range"),
            ParameterSpec(name="partial", range_min=5.0),
        ]
        space = ParameterSpace.from_hypothesis_params(specs)
        assert space.dimensionality == 1
        assert space.names == ("speed",)

    def test_empty_parameter_space(self) -> None:
        space = ParameterSpace()
        assert space.dimensionality == 0
        assert space.names == ()
        assert space.bounds == []


class TestDoEStrategyType:
    """Tests for DoEStrategyType enum."""

    def test_enum_values(self) -> None:
        assert DoEStrategyType.LHS == "lhs"
        assert DoEStrategyType.SOBOL == "sobol"
        assert DoEStrategyType.FULL_FACTORIAL == "full_factorial"
        assert DoEStrategyType.BAYESIAN == "bayesian"

    def test_all_four_values_exist(self) -> None:
        assert len(DoEStrategyType) == 4


class TestDoEStrategy:
    """Tests for DoEStrategy frozen model."""

    def test_create(self) -> None:
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS,
            n_samples=32,
            rationale="Space-filling design",
        )
        assert strategy.strategy_type == DoEStrategyType.LHS
        assert strategy.n_samples == 32
        assert strategy.rationale == "Space-filling design"

    def test_immutable(self) -> None:
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.SOBOL, n_samples=64,
        )
        with pytest.raises((TypeError, Exception)):
            strategy.n_samples = 128  # type: ignore[misc]


class TestSampledDesign:
    """Tests for SampledDesign frozen model."""

    def _make_strategy(self) -> DoEStrategy:
        return DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=1, rationale="test",
        )

    def test_n_runs_single(self) -> None:
        design = SampledDesign(
            strategy=self._make_strategy(),
            parameter_names=("x",),
            design_matrix=((0.5,),),
        )
        assert design.n_runs == 1

    def test_n_runs_many(self) -> None:
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=32, rationale="test",
        )
        matrix = tuple(
            tuple(float(i + j) for j in range(3)) for i in range(32)
        )
        design = SampledDesign(
            strategy=strategy,
            parameter_names=("a", "b", "c"),
            design_matrix=matrix,
        )
        assert design.n_runs == 32

    def test_to_parameter_dicts(self) -> None:
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=3, rationale="test",
        )
        design = SampledDesign(
            strategy=strategy,
            parameter_names=("x", "y", "z"),
            design_matrix=(
                (1.0, 2.0, 3.0),
                (4.0, 5.0, 6.0),
                (7.0, 8.0, 9.0),
            ),
        )
        dicts = design.to_parameter_dicts()
        assert len(dicts) == 3
        assert dicts[0] == {"x": 1.0, "y": 2.0, "z": 3.0}
        assert dicts[2] == {"x": 7.0, "y": 8.0, "z": 9.0}

    def test_to_parameter_dicts_five_runs_three_params(self) -> None:
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=5, rationale="test",
        )
        matrix = tuple(
            tuple(float(i * 3 + j) for j in range(3)) for i in range(5)
        )
        design = SampledDesign(
            strategy=strategy,
            parameter_names=("a", "b", "c"),
            design_matrix=matrix,
        )
        dicts = design.to_parameter_dicts()
        assert len(dicts) == 5
        for d in dicts:
            assert set(d.keys()) == {"a", "b", "c"}

    def test_immutable(self) -> None:
        design = SampledDesign(
            strategy=self._make_strategy(),
            parameter_names=("x",),
            design_matrix=((0.5,),),
        )
        with pytest.raises((TypeError, Exception)):
            design.parameter_names = ("y",)  # type: ignore[misc]
