"""Tests for ExperimentState.feasibility_result field and set_feasibility_result transition."""

from __future__ import annotations

from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    FeasibilityResult,
    SensorConfig,
    SensorFamily,
)
from agentsim.state.models import ExperimentState
from agentsim.state.transitions import set_feasibility_result


def _make_feasibility_result() -> FeasibilityResult:
    """Create a minimal FeasibilityResult for testing."""
    return FeasibilityResult(
        query_text="locate object in darkness",
        detected_task="localization",
        detected_domain="nlos",
        ranked_configs=(
            SensorConfig(
                sensor_name="SPAD-Array-1",
                sensor_family=SensorFamily.SPAD,
                algorithm_name="backprojection",
                crb_bound=0.005,
                crb_unit="meter",
                confidence=ConfidenceQualifier.ANALYTICAL,
                rank=1,
                feasibility_score=0.92,
            ),
        ),
        pruned_count=3,
        total_count=10,
    )


def test_default_feasibility_result_is_none() -> None:
    """ExperimentState() creates instance with feasibility_result=None."""
    state = ExperimentState()
    assert state.feasibility_result is None


def test_feasibility_result_stores_value() -> None:
    """ExperimentState(feasibility_result=some_result) stores FeasibilityResult."""
    result = _make_feasibility_result()
    state = ExperimentState(feasibility_result=result)
    assert state.feasibility_result is result
    assert state.feasibility_result.query_text == "locate object in darkness"


def test_set_feasibility_result_returns_new_state() -> None:
    """set_feasibility_result(state, result) returns new state with feasibility_result set."""
    state = ExperimentState()
    result = _make_feasibility_result()
    new_state = set_feasibility_result(state, result)
    assert new_state.feasibility_result is result
    assert new_state is not state


def test_set_feasibility_result_does_not_mutate_original() -> None:
    """set_feasibility_result does not mutate the original state (frozen model)."""
    state = ExperimentState()
    result = _make_feasibility_result()
    set_feasibility_result(state, result)
    assert state.feasibility_result is None


def test_existing_transitions_preserve_feasibility_result() -> None:
    """All existing transition functions pass through feasibility_result unchanged."""
    from agentsim.state.transitions import add_hypothesis

    result = _make_feasibility_result()
    state = ExperimentState(feasibility_result=result)

    from agentsim.state.models import Hypothesis

    h = Hypothesis(raw_text="test hypothesis")
    new_state = add_hypothesis(state, h)
    assert new_state.feasibility_result is result
