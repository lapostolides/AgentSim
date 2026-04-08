"""Unit tests for DoE strategy selector and parameter samplers."""

from __future__ import annotations

import pytest

from agentsim.experimental_design.doe_selector import select_doe_strategy
from agentsim.experimental_design.lhs_sampler import (
    generate_full_factorial_design,
    generate_lhs_design,
    generate_sobol_design,
)
from agentsim.experimental_design.models import (
    DoEStrategy,
    DoEStrategyType,
    ParameterBound,
    ParameterSpace,
)


def _make_space(dim: int) -> ParameterSpace:
    """Create a ParameterSpace with `dim` parameters in [0, 1]."""
    params = tuple(
        ParameterBound(name=f"p{i}", low=0.0, high=1.0)
        for i in range(dim)
    )
    return ParameterSpace(parameters=params)


def _make_space_custom_bounds(bounds: list[tuple[float, float]]) -> ParameterSpace:
    """Create a ParameterSpace with custom bounds per parameter."""
    params = tuple(
        ParameterBound(name=f"p{i}", low=lo, high=hi)
        for i, (lo, hi) in enumerate(bounds)
    )
    return ParameterSpace(parameters=params)


class TestSelectDoEStrategy:
    """Tests for select_doe_strategy decision logic."""

    def test_low_dim_small_budget_returns_factorial(self) -> None:
        space = _make_space(1)
        result = select_doe_strategy(space, budget=8)
        assert result.strategy_type == DoEStrategyType.FULL_FACTORIAL

    def test_two_dim_small_budget_returns_factorial(self) -> None:
        space = _make_space(2)
        result = select_doe_strategy(space, budget=16)
        assert result.strategy_type == DoEStrategyType.FULL_FACTORIAL

    def test_medium_dim_returns_lhs(self) -> None:
        space = _make_space(3)
        result = select_doe_strategy(space, budget=16)
        assert result.strategy_type == DoEStrategyType.LHS

    def test_high_dim_returns_sobol(self) -> None:
        space = _make_space(8)
        result = select_doe_strategy(space, budget=200)
        assert result.strategy_type == DoEStrategyType.SOBOL

    def test_very_high_dim_large_budget_returns_bayesian(self) -> None:
        space = _make_space(12)
        result = select_doe_strategy(space, budget=500)
        assert result.strategy_type == DoEStrategyType.BAYESIAN

    def test_rationale_is_nonempty(self) -> None:
        space = _make_space(2)
        result = select_doe_strategy(space, budget=16)
        assert len(result.rationale) > 0

    def test_returns_doe_strategy_type(self) -> None:
        space = _make_space(4)
        result = select_doe_strategy(space, budget=32)
        assert isinstance(result, DoEStrategy)

    def test_sobol_n_samples_is_power_of_two(self) -> None:
        space = _make_space(6)
        result = select_doe_strategy(space, budget=100)
        assert result.strategy_type == DoEStrategyType.SOBOL
        # n_samples should be largest power of 2 <= budget
        assert result.n_samples & (result.n_samples - 1) == 0
        assert result.n_samples <= 100


class TestGenerateLHSDesign:
    """Tests for generate_lhs_design sampler."""

    def test_correct_shape(self) -> None:
        space = _make_space(3)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=16, rationale="test",
        )
        design = generate_lhs_design(space, strategy)
        assert design.n_runs == 16
        assert len(design.parameter_names) == 3

    def test_values_in_bounds(self) -> None:
        space = _make_space_custom_bounds([(0.0, 10.0), (5.0, 20.0)])
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=16, rationale="test",
        )
        design = generate_lhs_design(space, strategy)
        for row in design.design_matrix:
            assert 0.0 <= row[0] <= 10.0, f"p0={row[0]} out of [0, 10]"
            assert 5.0 <= row[1] <= 20.0, f"p1={row[1]} out of [5, 20]"

    def test_parameter_names_match(self) -> None:
        space = _make_space(2)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=8, rationale="test",
        )
        design = generate_lhs_design(space, strategy)
        assert design.parameter_names == space.names


class TestGenerateSobolDesign:
    """Tests for generate_sobol_design sampler."""

    def test_correct_shape(self) -> None:
        space = _make_space(3)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.SOBOL, n_samples=64, rationale="test",
        )
        design = generate_sobol_design(space, strategy)
        assert design.n_runs <= 64

    def test_values_in_bounds(self) -> None:
        space = _make_space_custom_bounds([(0.0, 5.0), (10.0, 20.0), (0.0, 1.0)])
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.SOBOL, n_samples=16, rationale="test",
        )
        design = generate_sobol_design(space, strategy)
        for row in design.design_matrix:
            assert 0.0 <= row[0] <= 5.0
            assert 10.0 <= row[1] <= 20.0
            assert 0.0 <= row[2] <= 1.0


class TestGenerateFullFactorialDesign:
    """Tests for generate_full_factorial_design sampler."""

    def test_1d_correct_runs(self) -> None:
        space = _make_space(1)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.FULL_FACTORIAL,
            n_samples=100,
            rationale="test",
        )
        design = generate_full_factorial_design(space, strategy, levels=5)
        assert design.n_runs == 5

    def test_2d_correct_runs(self) -> None:
        space = _make_space(2)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.FULL_FACTORIAL,
            n_samples=100,
            rationale="test",
        )
        design = generate_full_factorial_design(space, strategy, levels=3)
        assert design.n_runs == 9  # 3^2

    def test_values_in_bounds(self) -> None:
        space = _make_space_custom_bounds([(0.0, 10.0)])
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.FULL_FACTORIAL,
            n_samples=100,
            rationale="test",
        )
        design = generate_full_factorial_design(space, strategy, levels=5)
        for row in design.design_matrix:
            assert 0.0 <= row[0] <= 10.0

    def test_capped_at_n_samples(self) -> None:
        space = _make_space(3)
        strategy = DoEStrategy(
            strategy_type=DoEStrategyType.FULL_FACTORIAL,
            n_samples=10,
            rationale="test",
        )
        design = generate_full_factorial_design(space, strategy, levels=5)
        # 5^3 = 125, but capped at 10
        assert design.n_runs == 10


class TestAllDesignsInBounds:
    """Cross-cutting test: all generated designs have values within declared bounds."""

    def test_all_samplers_respect_bounds(self) -> None:
        bounds = [(0.0, 5.0), (10.0, 20.0)]
        space = _make_space_custom_bounds(bounds)

        lhs_strategy = DoEStrategy(
            strategy_type=DoEStrategyType.LHS, n_samples=8, rationale="test",
        )
        lhs_design = generate_lhs_design(space, lhs_strategy)
        for row in lhs_design.design_matrix:
            assert 0.0 <= row[0] <= 5.0
            assert 10.0 <= row[1] <= 20.0

        factorial_strategy = DoEStrategy(
            strategy_type=DoEStrategyType.FULL_FACTORIAL,
            n_samples=100, rationale="test",
        )
        factorial_design = generate_full_factorial_design(
            space, factorial_strategy, levels=4,
        )
        for row in factorial_design.design_matrix:
            assert 0.0 <= row[0] <= 5.0
            assert 10.0 <= row[1] <= 20.0
