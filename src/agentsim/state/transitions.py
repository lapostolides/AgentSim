"""Pure state transition functions.

Each function takes an ExperimentState and returns a NEW ExperimentState
with the relevant field updated. No mutation occurs.
"""

from __future__ import annotations

from pathlib import Path

from agentsim.state.models import (
    AnalysisReport,
    EnvironmentInfo,
    EvaluationResult,
    ExecutionResult,
    ExperimentPlan,
    ExperimentState,
    ExperimentStatus,
    FileReference,
    Hypothesis,
    LiteratureContext,
    LiteratureValidation,
    SceneSpec,
)


def _detect_file_type(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    type_map = {
        "stl": "stl",
        "obj": "mesh",
        "ply": "mesh",
        "yaml": "yaml",
        "yml": "yaml",
        "json": "json",
        "csv": "csv",
        "png": "image",
        "jpg": "image",
        "jpeg": "image",
        "exr": "image",
        "hdr": "image",
        "xml": "xml",
        "py": "script",
    }
    return type_map.get(suffix, "unknown")


def start_experiment(
    hypothesis_text: str,
    file_paths: list[str] | None = None,
    file_descriptions: dict[str, str] | None = None,
) -> ExperimentState:
    """Create initial experiment state from user input."""
    files: list[FileReference] = []
    descriptions = file_descriptions or {}

    for path in file_paths or []:
        files.append(
            FileReference(
                path=path,
                file_type=_detect_file_type(path),
                description=descriptions.get(path, ""),
            )
        )

    return ExperimentState(
        raw_hypothesis=hypothesis_text,
        files=tuple(files),
        status=ExperimentStatus.INITIALIZED,
    )


def set_environment(
    state: ExperimentState,
    environment: EnvironmentInfo,
) -> ExperimentState:
    """Record discovered environment info (available Python packages)."""
    return state.model_copy(
        update={"environment": environment},
    )


def set_literature_context(
    state: ExperimentState,
    context: LiteratureContext,
) -> ExperimentState:
    """Transition: literature scout produced a literature review."""
    return state.model_copy(
        update={
            "literature_context": context,
            "status": ExperimentStatus.LITERATURE_REVIEWED,
        },
    )


def set_literature_validation(
    state: ExperimentState,
    validation: LiteratureValidation,
) -> ExperimentState:
    """Record literature validation (supplementary — does not change status)."""
    return state.model_copy(
        update={"literature_validation": validation},
    )


def add_hypothesis(
    state: ExperimentState,
    hypothesis: Hypothesis,
) -> ExperimentState:
    """Transition: hypothesis agent produced a structured hypothesis."""
    return state.model_copy(
        update={
            "hypothesis": hypothesis,
            "status": ExperimentStatus.HYPOTHESIS_READY,
        },
    )


def add_plan(
    state: ExperimentState,
    plan: ExperimentPlan,
) -> ExperimentState:
    """Transition: scene agent produced an experiment plan."""
    return state.model_copy(
        update={
            "plan": plan,
            "status": ExperimentStatus.PLAN_READY,
        },
    )


def add_scene(
    state: ExperimentState,
    scene: SceneSpec,
) -> ExperimentState:
    """Transition: scene agent generated a simulation scene."""
    return state.model_copy(
        update={
            "scenes": (*state.scenes, scene),
            "status": ExperimentStatus.SCENES_READY,
        },
    )


def add_scenes(
    state: ExperimentState,
    scenes: list[SceneSpec],
) -> ExperimentState:
    """Transition: scene agent generated multiple scenes at once."""
    return state.model_copy(
        update={
            "scenes": (*state.scenes, *scenes),
            "status": ExperimentStatus.SCENES_READY,
        },
    )


def add_execution_result(
    state: ExperimentState,
    result: ExecutionResult,
) -> ExperimentState:
    """Transition: executor finished running a scene."""
    return state.model_copy(
        update={
            "execution_results": (*state.execution_results, result),
            "status": ExperimentStatus.EXECUTED,
        },
    )


def add_evaluation(
    state: ExperimentState,
    evaluation: EvaluationResult,
) -> ExperimentState:
    """Transition: evaluator produced metrics for a scene."""
    return state.model_copy(
        update={
            "evaluations": (*state.evaluations, evaluation),
            "status": ExperimentStatus.EVALUATED,
        },
    )


def add_analysis(
    state: ExperimentState,
    report: AnalysisReport,
) -> ExperimentState:
    """Transition: analyst interpreted results and may propose follow-ups."""
    new_status = ExperimentStatus.COMPLETED if report.should_stop else ExperimentStatus.ANALYZED
    return state.model_copy(
        update={
            "analyses": (*state.analyses, report),
            "status": new_status,
            "iteration": state.iteration + 1,
        },
    )


def add_error(
    state: ExperimentState,
    error_message: str,
) -> ExperimentState:
    """Record an error without changing status."""
    return state.model_copy(
        update={"errors": (*state.errors, error_message)},
    )


def mark_failed(
    state: ExperimentState,
    error_message: str,
) -> ExperimentState:
    """Mark experiment as failed."""
    return state.model_copy(
        update={
            "errors": (*state.errors, error_message),
            "status": ExperimentStatus.FAILED,
        },
    )
