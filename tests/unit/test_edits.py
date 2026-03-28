"""Tests for state edit helpers — verify immutability is preserved."""

import pytest

from agentsim.state.edits import edit_hypothesis, edit_raw_hypothesis, replace_scenes
from agentsim.state.models import (
    ExperimentState,
    Hypothesis,
    ScenePreview,
    SceneSpec,
)
from agentsim.state.transitions import (
    add_hypothesis,
    add_scene_preview,
    add_scenes,
    start_experiment,
)


def _state_with_hypothesis() -> ExperimentState:
    state = start_experiment("original hypothesis")
    hyp = Hypothesis(raw_text="original", formalized="formal version")
    return add_hypothesis(state, hyp)


def _state_with_scenes() -> ExperimentState:
    state = _state_with_hypothesis()
    scenes = [
        SceneSpec(plan_id="p1", code="print('hello')"),
        SceneSpec(plan_id="p1", code="print('world')"),
    ]
    state = add_scenes(state, scenes)
    preview = ScenePreview(scene_id=state.scenes[0].id, preview_path="/tmp/p.png")
    return add_scene_preview(state, preview)


class TestEditRawHypothesis:
    def test_returns_new_state(self):
        original = start_experiment("old")
        edited = edit_raw_hypothesis(original, "new")
        assert edited.raw_hypothesis == "new"
        assert original.raw_hypothesis == "old"  # unchanged

    def test_preserves_other_fields(self):
        original = start_experiment("old")
        edited = edit_raw_hypothesis(original, "new")
        assert edited.id == original.id
        assert edited.created_at == original.created_at
        assert edited.status == original.status


class TestEditHypothesis:
    def test_edit_formalized(self):
        state = _state_with_hypothesis()
        edited = edit_hypothesis(state, formalized="better version")
        assert edited.hypothesis.formalized == "better version"
        assert state.hypothesis.formalized == "formal version"  # unchanged

    def test_edit_multiple_fields(self):
        state = _state_with_hypothesis()
        edited = edit_hypothesis(
            state,
            formalized="v2",
            predictions=["prediction A"],
        )
        assert edited.hypothesis.formalized == "v2"
        assert edited.hypothesis.predictions == ["prediction A"]

    def test_noop_when_no_hypothesis(self):
        state = start_experiment("test")
        edited = edit_hypothesis(state, formalized="anything")
        assert edited is state  # same object, no change

    def test_preserves_hypothesis_id(self):
        state = _state_with_hypothesis()
        original_id = state.hypothesis.id
        edited = edit_hypothesis(state, formalized="new")
        assert edited.hypothesis.id == original_id


class TestReplaceScenes:
    def test_replaces_scenes_and_clears_previews(self):
        state = _state_with_scenes()
        assert len(state.scenes) == 2
        assert len(state.scene_previews) == 1

        new_scenes = [SceneSpec(plan_id="p2", code="print('replaced')")]
        edited = replace_scenes(state, new_scenes)

        assert len(edited.scenes) == 1
        assert edited.scenes[0].code == "print('replaced')"
        assert len(edited.scene_previews) == 0  # cleared

    def test_original_unchanged(self):
        state = _state_with_scenes()
        replace_scenes(state, [])
        assert len(state.scenes) == 2  # original preserved
