"""Experiment loop — sequences agent phases and manages state.

Each phase is a separate query() call to keep context windows clean.
State is serialized between phases as JSON in the prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from claude_agent_sdk import query
from claude_agent_sdk.types import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
)

from agentsim.environment.discovery import discover_environment
from agentsim.orchestrator.agent_registry import build_agent_registry
from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.state.models import (
    AnalysisReport,
    EvaluationResult,
    ExecutionResult,
    ExperimentPlan,
    ExperimentState,
    ExperimentStatus,
    Hypothesis,
    LiteratureContext,
    LiteratureEntry,
    LiteratureValidation,
    SceneSpec,
)
from agentsim.state.serialization import serialize_state, state_to_prompt_context
from agentsim.state.transitions import (
    add_analysis,
    add_evaluation,
    add_execution_result,
    add_hypothesis,
    add_plan,
    add_scenes,
    mark_failed,
    set_environment,
    set_literature_context,
    set_literature_validation,
    start_experiment,
)

logger = structlog.get_logger()


def _extract_text(message: AssistantMessage) -> str:
    """Extract text content from an assistant message."""
    parts = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "\n".join(parts)


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from agent response text.

    Handles cases where the JSON is wrapped in markdown code fences.
    """
    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from code fences
    if "```" in text:
        for block in text.split("```"):
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                continue

    # Try finding JSON-like content between braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


async def _run_agent_phase(
    phase_name: str,
    prompt: str,
    config: OrchestratorConfig,
    agents: dict,
) -> tuple[str, ResultMessage | None]:
    """Execute a single agent phase via query().

    Returns the agent's text response and the result message.
    """
    logger.info("starting_phase", phase=phase_name)

    options = ClaudeAgentOptions(
        system_prompt=(
            f"You are the {phase_name} agent in the AgentSim pipeline. "
            "Follow your instructions precisely and output valid JSON."
        ),
        agents=agents,
        max_turns=config.max_turns_per_phase,
        max_budget_usd=config.max_budget_usd / 5,  # Budget per phase
        permission_mode=config.permission_mode,
        cwd=str(config.cwd),
    )

    response_text = ""
    result_msg = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            response_text = _extract_text(message)
        elif isinstance(message, ResultMessage):
            result_msg = message
            if message.result:
                response_text = message.result

    logger.info(
        "completed_phase",
        phase=phase_name,
        cost_usd=result_msg.total_cost_usd if result_msg else None,
        is_error=result_msg.is_error if result_msg else None,
    )

    return response_text, result_msg


async def run_experiment(
    hypothesis_text: str,
    file_paths: list[str] | None = None,
    file_descriptions: dict[str, str] | None = None,
    config: OrchestratorConfig | None = None,
    on_phase_complete: callable | None = None,
) -> ExperimentState:
    """Run a full experiment loop.

    Args:
        hypothesis_text: Natural language hypothesis from the user.
        file_paths: Optional paths to user-provided files.
        file_descriptions: Optional descriptions for each file.
        config: Orchestrator configuration.
        on_phase_complete: Optional callback(phase_name, state) for interactive mode.

    Returns:
        Final ExperimentState after all iterations.
    """
    config = config or OrchestratorConfig()

    # Ensure output directory exists
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize state
    state = start_experiment(hypothesis_text, file_paths, file_descriptions)
    logger.info("experiment_started", id=state.id, hypothesis=hypothesis_text[:100])

    # 2. Discover environment (what Python packages are available)
    environment = discover_environment(
        extra_packages=config.extra_packages or None,
    )
    state = set_environment(state, environment)

    # 3. Build agent registry with environment knowledge
    agents = build_agent_registry(environment)

    # 4. Literature scout (runs once before the experiment loop)
    state = await _run_literature_scout_phase(state, config, agents)
    if on_phase_complete:
        on_phase_complete("literature_scout", state)

    # 5. Experiment loop
    for iteration in range(config.max_iterations):
        logger.info("iteration_start", iteration=iteration, status=state.status.value)

        try:
            # Phase 1: Hypothesis
            state = await _run_hypothesis_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("hypothesis", state)

            # Phase 2: Scene Generation
            state = await _run_scene_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("scene", state)

            # Phase 3: Execution
            state = await _run_executor_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("executor", state)

            # Phase 4: Evaluation
            state = await _run_evaluator_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("evaluator", state)

            # Phase 5: Analysis
            state = await _run_analyst_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("analyst", state)

            # Phase 6: Literature validation
            state = await _run_literature_validator_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("literature_validator", state)

            # Check if we should stop
            if state.status == ExperimentStatus.COMPLETED:
                logger.info("experiment_completed", iteration=iteration)
                break

        except Exception as e:
            logger.error("phase_error", error=str(e), iteration=iteration)
            state = mark_failed(state, f"Error in iteration {iteration}: {e}")
            break

    # Save final state
    if config.save_intermediate_state:
        _save_state(state, config.output_dir / "final_state.json")

    return state


async def _run_literature_scout_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the literature scout agent phase (once, before hypothesis)."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Survey the academic literature relevant to this research question.\n\n"
        f"Research question: {state.raw_hypothesis}\n\n"
        f"Files provided: {[f.path for f in state.files]}\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase(
        "literature_scout", prompt, config, agents,
    )

    data = _extract_json_from_text(response_text)
    if data:
        # Parse entries if present
        entries = tuple(
            LiteratureEntry.model_validate(e)
            for e in data.get("entries", [])
        )
        lit_context = LiteratureContext(
            entries=entries,
            summary=data.get("summary", ""),
            open_questions=tuple(data.get("open_questions", [])),
            methodology_notes=data.get("methodology_notes", ""),
        )
        return set_literature_context(state, lit_context)

    # Fallback: store raw response as summary
    return set_literature_context(
        state,
        LiteratureContext(summary=response_text[:2000]),
    )


async def _run_hypothesis_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the hypothesis agent phase."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Analyze this hypothesis and produce a structured experiment specification.\n\n"
        f"Hypothesis: {state.raw_hypothesis}\n\n"
        f"Files provided: {[f.path for f in state.files]}\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("hypothesis", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data:
        hypothesis = Hypothesis.model_validate(data)
        return add_hypothesis(state, hypothesis)

    # Fallback: create hypothesis from raw text
    return add_hypothesis(
        state,
        Hypothesis(raw_text=state.raw_hypothesis, formalized=response_text[:500]),
    )


async def _run_scene_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the scene generation agent phase."""
    context = state_to_prompt_context(state)

    prompt = (
        f"Generate simulation scenes for this experiment.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("scene", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data:
        if "plan_id" in data and "scenes" not in data:
            plan = ExperimentPlan.model_validate(data)
            state = add_plan(state, plan)
        elif "scenes" in data:
            scenes = [SceneSpec.model_validate(s) for s in data["scenes"]]
            state = add_scenes(state, scenes)

    return state


async def _run_executor_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the executor agent phase."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Execute the following simulation scenes and report results.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("executor", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data and "results" in data:
        for result_data in data["results"]:
            result = ExecutionResult.model_validate(result_data)
            state = add_execution_result(state, result)

    return state


async def _run_evaluator_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the evaluator agent phase."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Evaluate the simulation results and compute metrics.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("evaluator", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data and "evaluations" in data:
        for eval_data in data["evaluations"]:
            evaluation = EvaluationResult.model_validate(eval_data)
            state = add_evaluation(state, evaluation)

    return state


async def _run_analyst_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the analyst agent phase."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Analyze the experimental results and decide next steps.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("analyst", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data:
        report = AnalysisReport.model_validate(data)
        return add_analysis(state, report)

    # Fallback: stop after failing to parse
    return add_analysis(
        state,
        AnalysisReport(
            hypothesis_id=state.hypothesis.id if state.hypothesis else "",
            findings=["Could not parse analyst response"],
            should_stop=True,
            reasoning=response_text[:500],
        ),
    )


async def _run_literature_validator_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    """Run the literature validator agent phase (after analyst)."""
    context = state_to_prompt_context(state)
    prompt = (
        f"Validate the experimental findings against the literature.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase(
        "literature_validator", prompt, config, agents,
    )

    data = _extract_json_from_text(response_text)
    if data:
        validation = LiteratureValidation.model_validate(data)
        return set_literature_validation(state, validation)

    # Fallback: minimal validation with raw reasoning
    hypothesis_id = state.hypothesis.id if state.hypothesis else ""
    return set_literature_validation(
        state,
        LiteratureValidation(
            hypothesis_id=hypothesis_id,
            reasoning=response_text[:1000],
        ),
    )


def _save_state(state: ExperimentState, path: Path) -> None:
    """Save experiment state to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_state(state))
    logger.info("state_saved", path=str(path))
