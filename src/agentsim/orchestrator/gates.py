"""Intervention gate types for human-in-the-loop experiment steering.

Gates pause the pipeline at key phase boundaries so the user can review
outputs, provide feedback, edit state, or trigger re-runs.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from agentsim.state.models import ExperimentState


class GateAction(str, Enum):
    """Action the user can take at an intervention gate."""

    APPROVE = "approve"     # Continue with current state
    EDIT = "edit"           # Continue with user-modified state
    REDO = "redo"           # Re-run the preceding phase with guidance
    ABORT = "abort"         # Stop the experiment
    FEEDBACK = "feedback"   # Scene visualization only: text feedback for re-generation


class GateCheckpoint(str, Enum):
    """Named locations in the pipeline where gates can fire."""

    PRE_HYPOTHESIS = "pre_hypothesis"
    POST_HYPOTHESIS = "post_hypothesis"
    PRE_EXECUTION = "pre_execution"
    SCENE_VISUALIZATION = "scene_visualization"
    POST_EXECUTION = "post_execution"


ALL_CHECKPOINTS: frozenset[str] = frozenset(c.value for c in GateCheckpoint)


class GateContext(BaseModel, frozen=True):
    """Data passed to an intervention handler at a gate."""

    checkpoint: GateCheckpoint
    state: ExperimentState
    phase_just_completed: str = ""
    phase_about_to_run: str = ""
    message: str = ""
    preview_paths: tuple[str, ...] = ()


class GateDecision(BaseModel, frozen=True):
    """The user's response at a gate."""

    action: GateAction
    updated_state: ExperimentState | None = None
    feedback_text: str = ""
    reason: str = ""


@runtime_checkable
class InterventionHandler(Protocol):
    """Protocol for handling intervention gates.

    Implementations present gate context to the user (CLI, web UI, etc.)
    and return their decision.
    """

    async def handle_gate(self, context: GateContext) -> GateDecision: ...
