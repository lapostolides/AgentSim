"""Unit tests for the deterministic constraint propagation engine.

Tests cover: TF graph building, individual relationship evaluation,
cascading propagation with chains/cycles, and model immutability.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from agentsim.physics.domains.schema import TransferFunction
from agentsim.physics.reasoning.models import ComputedValue, PropagationResult
from agentsim.physics.reasoning.propagation import (
    build_tf_graph,
    evaluate_tf,
    propagate_constraints,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _tf(inp: str, out: str, rel: str, formula: str = "") -> TransferFunction:
    """Shorthand factory for TransferFunction."""
    return TransferFunction(input=inp, output=out, relationship=rel, formula=formula)


# ---------------------------------------------------------------------------
# build_tf_graph
# ---------------------------------------------------------------------------


class TestBuildTfGraph:
    """Tests for build_tf_graph."""

    def test_three_tfs_keyed_by_input(self) -> None:
        tfs = (
            _tf("A", "B", "linear"),
            _tf("A", "C", "inverse"),
            _tf("B", "D", "sqrt"),
        )
        graph = build_tf_graph(tfs)
        assert "A" in graph
        assert "B" in graph
        assert len(graph["A"]) == 2
        assert len(graph["B"]) == 1

    def test_deduplicates_same_input_output(self) -> None:
        tfs = (
            _tf("A", "B", "linear"),
            _tf("A", "B", "inverse"),  # same (input, output) pair
        )
        graph = build_tf_graph(tfs)
        assert len(graph["A"]) == 1  # only first kept


# ---------------------------------------------------------------------------
# evaluate_tf
# ---------------------------------------------------------------------------


class TestEvaluateTf:
    """Tests for evaluate_tf with each relationship type."""

    def test_linear_returns_input(self) -> None:
        tf = _tf("x", "y", "linear")
        assert evaluate_tf(tf, 5.0) == 5.0

    def test_inverse_on_four(self) -> None:
        tf = _tf("x", "y", "inverse")
        assert evaluate_tf(tf, 4.0) == pytest.approx(0.25)

    def test_sqrt_on_nine(self) -> None:
        tf = _tf("x", "y", "sqrt")
        assert evaluate_tf(tf, 9.0) == pytest.approx(3.0)

    def test_quadratic_on_three(self) -> None:
        tf = _tf("x", "y", "quadratic")
        assert evaluate_tf(tf, 3.0) == pytest.approx(9.0)

    def test_logarithmic_on_e(self) -> None:
        tf = _tf("x", "y", "logarithmic")
        assert evaluate_tf(tf, math.e) == pytest.approx(1.0)

    def test_proportional_returns_input(self) -> None:
        tf = _tf("x", "y", "proportional")
        assert evaluate_tf(tf, 7.0) == 7.0

    def test_inverse_sqrt_on_four(self) -> None:
        tf = _tf("x", "y", "inverse_sqrt")
        assert evaluate_tf(tf, 4.0) == pytest.approx(0.5)

    def test_unknown_relationship_passthrough(self) -> None:
        tf = _tf("x", "y", "exotic_nonlinear")
        assert evaluate_tf(tf, 42.0) == 42.0


# ---------------------------------------------------------------------------
# propagate_constraints
# ---------------------------------------------------------------------------


class TestPropagateConstraints:
    """Tests for the BFS cascading propagation."""

    def test_chain_a_b_c(self) -> None:
        tfs = (
            _tf("A", "B", "linear"),
            _tf("B", "C", "linear"),
        )
        result = propagate_constraints({"A": 10.0}, tfs)
        names = {cv.parameter for cv in result.computed}
        assert "B" in names
        assert "C" in names

    def test_relay_wall_temporal_to_spatial(self) -> None:
        tfs = (
            TransferFunction(
                input="temporal_resolution_ps",
                output="spatial_resolution_m",
                relationship="linear",
                formula="c * dt / 2",
                coupling_strength="strong",
            ),
        )
        result = propagate_constraints(
            {"temporal_resolution_ps": 32.0},
            tfs,
        )
        names = {cv.parameter for cv in result.computed}
        assert "spatial_resolution_m" in names

    def test_circular_tfs_terminate(self) -> None:
        tfs = (
            _tf("A", "B", "linear"),
            _tf("B", "A", "linear"),
        )
        # Must not hang — should terminate
        result = propagate_constraints({"A": 1.0}, tfs)
        assert isinstance(result, PropagationResult)

    def test_no_matching_tfs_empty(self) -> None:
        tfs = (
            _tf("X", "Y", "linear"),
        )
        result = propagate_constraints({"Z": 5.0}, tfs)
        assert result.computed == ()

    def test_computed_value_fields(self) -> None:
        tfs = (
            TransferFunction(
                input="A",
                output="B",
                relationship="sqrt",
                formula="B = sqrt(A)",
            ),
        )
        result = propagate_constraints({"A": 9.0}, tfs)
        assert len(result.computed) == 1
        cv = result.computed[0]
        assert cv.parameter == "B"
        assert cv.value == pytest.approx(3.0)
        assert cv.source_input == "A"
        assert cv.source_tf_formula == "B = sqrt(A)"
        assert cv.relationship == "sqrt"


# ---------------------------------------------------------------------------
# Model immutability
# ---------------------------------------------------------------------------


class TestModelImmutability:
    """All reasoning models must be frozen."""

    def test_computed_value_frozen(self) -> None:
        cv = ComputedValue(parameter="x", value=1.0)
        with pytest.raises(ValidationError):
            cv.parameter = "y"  # type: ignore[misc]

    def test_propagation_result_frozen(self) -> None:
        pr = PropagationResult()
        with pytest.raises(ValidationError):
            pr.inputs = {"a": 1.0}  # type: ignore[misc]
