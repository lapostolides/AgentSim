"""Tests for serialization helpers."""

import json

from agentsim.state.models import (
    ExperimentState,
    ExperimentStatus,
    FileReference,
    Hypothesis,
    ParameterSpec,
    SceneSpec,
)
from agentsim.state.serialization import (
    deserialize_model,
    deserialize_state,
    serialize_model,
    serialize_state,
    state_to_prompt_context,
)
from agentsim.state.transitions import add_hypothesis, add_scene, start_experiment


class TestSerializeState:
    def test_roundtrip(self):
        state = start_experiment(
            "test hypothesis",
            file_paths=["/data/scene.stl"],
        )
        json_str = serialize_state(state)
        restored = deserialize_state(json_str)
        assert restored.raw_hypothesis == state.raw_hypothesis
        assert restored.id == state.id

    def test_with_nested_objects(self):
        state = start_experiment("test")
        state = add_hypothesis(
            state,
            Hypothesis(
                raw_text="test",
                parameter_space=[ParameterSpec(name="x", values=[1, 2, 3])],
            ),
        )
        state = add_scene(
            state,
            SceneSpec(plan_id="p1", code="print('hello')", parameters={"spp": 256}),
        )
        json_str = serialize_state(state)
        restored = deserialize_state(json_str)

        assert restored.hypothesis is not None
        assert restored.hypothesis.parameter_space[0].name == "x"
        assert len(restored.scenes) == 1
        assert restored.scenes[0].parameters["spp"] == 256


class TestSerializeModel:
    def test_file_reference(self):
        ref = FileReference(path="/data/scene.stl", file_type="stl", description="mesh")
        json_str = serialize_model(ref)
        restored = deserialize_model(json_str, FileReference)
        assert restored.path == ref.path
        assert restored.file_type == ref.file_type

    def test_hypothesis(self):
        h = Hypothesis(raw_text="test", formalized="formalized test")
        json_str = serialize_model(h)
        restored = deserialize_model(json_str, Hypothesis)
        assert restored.raw_text == h.raw_text
        assert restored.id == h.id


class TestStateToPromptContext:
    def test_normal_state(self):
        state = start_experiment("test hypothesis")
        context = state_to_prompt_context(state)
        assert "<experiment_state>" in context
        assert "test hypothesis" in context
        assert "</experiment_state>" in context

    def test_truncation(self):
        state = start_experiment("test")
        # Add enough scenes to exceed a small max_length
        for i in range(100):
            state = add_scene(
                state,
                SceneSpec(plan_id="p1", code=f"x = {i}\n" * 50),
            )
        context = state_to_prompt_context(state, max_length=1000)
        assert 'truncated="true"' in context
        parsed = json.loads(
            context.split("<experiment_state")[1]
            .split(">", 1)[1]
            .split("</experiment_state>")[0]
        )
        assert parsed["_truncated"] is True
        assert parsed["_total_scenes"] == 100
