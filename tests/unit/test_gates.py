"""Tests for intervention gate types and helpers."""

import pytest

from agentsim.orchestrator.gates import (
    ALL_CHECKPOINTS,
    GateAction,
    GateCheckpoint,
    GateContext,
    GateDecision,
    InterventionHandler,
)
from agentsim.state.models import ExperimentState, ExperimentStatus
from agentsim.state.transitions import mark_failed, start_experiment


def _make_state(hypothesis_text: str = "test hypothesis") -> ExperimentState:
    return start_experiment(hypothesis_text)


class TestGateAction:
    def test_all_actions_exist(self):
        assert GateAction.APPROVE == "approve"
        assert GateAction.EDIT == "edit"
        assert GateAction.REDO == "redo"
        assert GateAction.ABORT == "abort"
        assert GateAction.FEEDBACK == "feedback"


class TestGateCheckpoint:
    def test_all_checkpoints_in_constant(self):
        for cp in GateCheckpoint:
            assert cp.value in ALL_CHECKPOINTS

    def test_checkpoint_count(self):
        assert len(ALL_CHECKPOINTS) == 6


class TestGateContext:
    def test_context_is_frozen(self):
        state = _make_state()
        ctx = GateContext(
            checkpoint=GateCheckpoint.PRE_HYPOTHESIS,
            state=state,
        )
        with pytest.raises(Exception):
            ctx.checkpoint = GateCheckpoint.POST_HYPOTHESIS

    def test_context_fields(self):
        state = _make_state()
        ctx = GateContext(
            checkpoint=GateCheckpoint.POST_HYPOTHESIS,
            state=state,
            phase_just_completed="hypothesis",
            phase_about_to_run="scene",
            message="Review hypothesis",
            preview_paths=("/tmp/preview.png",),
        )
        assert ctx.checkpoint == GateCheckpoint.POST_HYPOTHESIS
        assert ctx.phase_just_completed == "hypothesis"
        assert ctx.preview_paths == ("/tmp/preview.png",)


class TestGateDecision:
    def test_approve_decision(self):
        d = GateDecision(action=GateAction.APPROVE)
        assert d.action == GateAction.APPROVE
        assert d.updated_state is None
        assert d.feedback_text == ""

    def test_edit_decision_carries_state(self):
        state = _make_state("edited")
        d = GateDecision(action=GateAction.EDIT, updated_state=state)
        assert d.updated_state is not None
        assert d.updated_state.raw_hypothesis == "edited"

    def test_redo_decision_carries_feedback(self):
        d = GateDecision(action=GateAction.REDO, feedback_text="try again")
        assert d.feedback_text == "try again"

    def test_decision_is_frozen(self):
        d = GateDecision(action=GateAction.APPROVE)
        with pytest.raises(Exception):
            d.action = GateAction.ABORT


class TestInterventionHandlerProtocol:
    def test_protocol_is_runtime_checkable(self):
        class MockHandler:
            async def handle_gate(self, context: GateContext) -> GateDecision:
                return GateDecision(action=GateAction.APPROVE)

        assert isinstance(MockHandler(), InterventionHandler)

    def test_non_handler_fails_check(self):
        class NotAHandler:
            pass

        assert not isinstance(NotAHandler(), InterventionHandler)
