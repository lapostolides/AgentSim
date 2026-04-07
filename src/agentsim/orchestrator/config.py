"""Orchestrator configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentsim.orchestrator.gates import ALL_CHECKPOINTS


class OrchestratorConfig(BaseModel, frozen=True):
    """Configuration for the experiment orchestrator."""

    # Experiment loop
    max_iterations: int = 5
    max_budget_usd: float = 10.0
    max_turns_per_phase: int = 15

    # Output
    output_dir: Path = Field(default_factory=lambda: Path("./output"))
    save_intermediate_state: bool = True

    # Extra Python packages to probe beyond the built-in list
    # Mapping of display_name → import_name
    extra_packages: dict[str, str] = Field(default_factory=dict)

    # Permissions — acceptEdits auto-approves file operations
    permission_mode: str = "acceptEdits"

    # Working directory for simulation execution
    cwd: Path = Field(default_factory=lambda: Path.cwd())

    # Human-in-the-loop intervention gates (all enabled by default)
    intervention_checkpoints: frozenset[str] = Field(
        default_factory=lambda: ALL_CHECKPOINTS,
    )

    # Max scene feedback rounds before forcing approval
    max_scene_feedback_rounds: int = 5
