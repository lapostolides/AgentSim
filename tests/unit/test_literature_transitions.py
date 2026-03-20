"""Tests for literature-related state transitions."""

from agentsim.state.models import (
    ExperimentStatus,
    Hypothesis,
    LiteratureContext,
    LiteratureEntry,
    LiteratureValidation,
)
from agentsim.state.transitions import (
    add_hypothesis,
    set_literature_context,
    set_literature_validation,
    start_experiment,
)


class TestSetLiteratureContext:
    def test_basic(self):
        state = start_experiment("Does roughness matter?")
        ctx = LiteratureContext(
            entries=(LiteratureEntry(title="Paper A", relevance="Baseline"),),
            summary="One relevant paper.",
        )
        new_state = set_literature_context(state, ctx)

        assert new_state.literature_context is not None
        assert len(new_state.literature_context.entries) == 1
        assert new_state.status == ExperimentStatus.LITERATURE_REVIEWED

    def test_immutable(self):
        original = start_experiment("test")
        ctx = LiteratureContext(summary="Test context")
        new_state = set_literature_context(original, ctx)

        assert original.literature_context is None
        assert new_state.literature_context is not None
        assert original.id == new_state.id

    def test_preserves_other_fields(self):
        state = start_experiment(
            "test",
            file_paths=["/data/scene.stl"],
            file_descriptions={"/data/scene.stl": "Wall mesh"},
        )
        ctx = LiteratureContext(summary="Papers found")
        new_state = set_literature_context(state, ctx)

        assert new_state.raw_hypothesis == "test"
        assert len(new_state.files) == 1
        assert new_state.files[0].description == "Wall mesh"


class TestSetLiteratureValidation:
    def test_basic(self):
        state = start_experiment("test")
        state = add_hypothesis(state, Hypothesis(raw_text="test"))
        validation = LiteratureValidation(
            hypothesis_id=state.hypothesis.id,
            consistency_assessment="Consistent with prior work",
            novel_findings=("New finding",),
        )
        new_state = set_literature_validation(state, validation)

        assert new_state.literature_validation is not None
        assert new_state.literature_validation.consistency_assessment == "Consistent with prior work"

    def test_immutable(self):
        original = start_experiment("test")
        validation = LiteratureValidation(hypothesis_id="h1")
        new_state = set_literature_validation(original, validation)

        assert original.literature_validation is None
        assert new_state.literature_validation is not None

    def test_does_not_change_status(self):
        """Literature validation doesn't change experiment status — it's supplementary."""
        state = start_experiment("test")
        state = add_hypothesis(state, Hypothesis(raw_text="test"))
        original_status = state.status

        validation = LiteratureValidation(hypothesis_id="h1")
        new_state = set_literature_validation(state, validation)

        assert new_state.status == original_status
