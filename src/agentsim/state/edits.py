"""Pure helper functions for creating edited copies of frozen state.

Each function returns a NEW ExperimentState — no mutation occurs.
"""

from __future__ import annotations

from typing import Any

from agentsim.state.models import ExperimentState, Hypothesis, SceneSpec


def edit_raw_hypothesis(state: ExperimentState, new_text: str) -> ExperimentState:
    """Return new state with the raw hypothesis text replaced."""
    return state.model_copy(update={"raw_hypothesis": new_text})


def edit_hypothesis(state: ExperimentState, **updates: Any) -> ExperimentState:
    """Return new state with hypothesis fields updated.

    Example: edit_hypothesis(state, formalized="new text", predictions=["p1"])
    """
    if state.hypothesis is None:
        return state
    new_hyp = state.hypothesis.model_copy(update=updates)
    return state.model_copy(update={"hypothesis": new_hyp})


def replace_scenes(
    state: ExperimentState,
    scenes: list[SceneSpec],
) -> ExperimentState:
    """Return new state with scenes replaced and previews cleared."""
    return state.model_copy(
        update={"scenes": tuple(scenes), "scene_previews": ()},
    )
