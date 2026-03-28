"""Experiment loop — sequences agent phases and manages state.

Each phase is a separate query() call to keep context windows clean.
State is serialized between phases as JSON in the prompt.

Human-in-the-loop intervention gates pause the pipeline at key
boundaries so the user can review, edit, or redirect.
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
from agentsim.orchestrator.gates import (
    GateAction,
    GateCheckpoint,
    GateContext,
    GateDecision,
    InterventionHandler,
)
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
    OpenQuestion,
    ScenePreview,
    SceneSpec,
)
from agentsim.state.serialization import serialize_state, state_to_prompt_context
from agentsim.state.transitions import (
    add_analysis,
    add_evaluation,
    add_execution_result,
    add_hypothesis,
    add_plan,
    add_scene_preview,
    add_scenes,
    mark_failed,
    set_environment,
    set_literature_context,
    set_literature_validation,
    start_experiment,
)

logger = structlog.get_logger()


# ── Text / JSON extraction ───────────────────────────────────────────

def _extract_text(message: AssistantMessage) -> str:
    parts = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "\n".join(parts)


def _extract_json_from_text(text: str) -> dict | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    if "```" in text:
        for block in text.split("```"):
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


# ── Gate helpers ─────────────────────────────────────────────────────

async def _run_gate(
    handler: InterventionHandler | None,
    config: OrchestratorConfig,
    checkpoint: GateCheckpoint,
    state: ExperimentState,
    *,
    phase_just_completed: str = "",
    phase_about_to_run: str = "",
    message: str = "",
    preview_paths: tuple[str, ...] = (),
) -> tuple[GateDecision | None, ExperimentState]:
    """Fire a gate if the handler and checkpoint are enabled.

    Returns (decision, state) — decision is None if the gate was skipped.
    """
    if not handler or checkpoint.value not in config.intervention_checkpoints:
        return None, state

    context = GateContext(
        checkpoint=checkpoint,
        state=state,
        phase_just_completed=phase_just_completed,
        phase_about_to_run=phase_about_to_run,
        message=message,
        preview_paths=preview_paths,
    )
    decision = await handler.handle_gate(context)

    if decision.action == GateAction.EDIT and decision.updated_state is not None:
        return decision, decision.updated_state
    if decision.action == GateAction.ABORT:
        return decision, mark_failed(state, f"Aborted by user at {checkpoint.value}")

    return decision, state


def _is_abort(decision: GateDecision | None) -> bool:
    return decision is not None and decision.action == GateAction.ABORT


# ── Agent phase runner ───────────────────────────────────────────────

async def _run_agent_phase(
    phase_name: str,
    prompt: str,
    config: OrchestratorConfig,
    agents: dict,
) -> tuple[str, ResultMessage | None]:
    logger.info("starting_phase", phase=phase_name)

    options = ClaudeAgentOptions(
        system_prompt=(
            f"You are the {phase_name} agent in the AgentSim pipeline. "
            "Follow your instructions precisely and output valid JSON."
        ),
        agents=agents,
        max_turns=config.max_turns_per_phase,
        max_budget_usd=config.max_budget_usd / 5,
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


# ── Main experiment loop ─────────────────────────────────────────────

async def run_experiment(
    hypothesis_text: str,
    file_paths: list[str] | None = None,
    file_descriptions: dict[str, str] | None = None,
    config: OrchestratorConfig | None = None,
    on_phase_complete: callable | None = None,
    intervention_handler: InterventionHandler | None = None,
) -> ExperimentState:
    """Run a full experiment loop with optional human intervention gates.

    Args:
        hypothesis_text: Natural language hypothesis from the user.
        file_paths: Optional paths to user-provided files.
        file_descriptions: Optional descriptions for each file.
        config: Orchestrator configuration.
        on_phase_complete: Optional callback(phase_name, state) for status updates.
        intervention_handler: Optional handler for human-in-the-loop gates.

    Returns:
        Final ExperimentState after all iterations.
    """
    config = config or OrchestratorConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize
    state = start_experiment(hypothesis_text, file_paths, file_descriptions)
    logger.info("experiment_started", id=state.id, hypothesis=hypothesis_text[:100])

    # 2. Discover environment
    environment = discover_environment(
        extra_packages=config.extra_packages or None,
    )
    state = set_environment(state, environment)

    # 3. Build agent registry
    agents = build_agent_registry(environment)

    # 4. Literature scout
    state = await _run_literature_scout_phase(state, config, agents)
    if on_phase_complete:
        on_phase_complete("literature_scout", state)

    # 4b. Citation audit
    state = await _run_citation_audit_phase(state, config, agents)
    if on_phase_complete:
        on_phase_complete("citation_auditor", state)

    # 5. Experiment loop
    for iteration in range(config.max_iterations):
        logger.info("iteration_start", iteration=iteration, status=state.status.value)

        try:
            # ── GATE 1: Pre-hypothesis ────────────────────────────
            decision, state = await _run_gate(
                intervention_handler, config,
                GateCheckpoint.PRE_HYPOTHESIS, state,
                phase_just_completed="citation_auditor",
                phase_about_to_run="hypothesis",
                message="Review literature context and refine your hypothesis before formalization.",
            )
            if _is_abort(decision):
                break

            # ── Hypothesis phase (with redo loop) ─────────────────
            user_guidance = ""
            while True:
                state = await _run_hypothesis_phase(
                    state, config, agents, user_guidance=user_guidance,
                )
                if on_phase_complete:
                    on_phase_complete("hypothesis", state)

                # ── GATE 2: Post-hypothesis ───────────────────────
                decision, state = await _run_gate(
                    intervention_handler, config,
                    GateCheckpoint.POST_HYPOTHESIS, state,
                    phase_just_completed="hypothesis",
                    phase_about_to_run="scene",
                    message="Review formalized hypothesis, quality ratings, and parameter space.",
                )
                if _is_abort(decision):
                    break
                if decision and decision.action == GateAction.REDO:
                    user_guidance = decision.feedback_text
                    logger.info("hypothesis_redo", guidance=user_guidance[:100])
                    continue
                break

            if _is_abort(decision):
                break

            # ── Scene generation (with feedback loop) ─────────────
            user_feedback = ""
            for feedback_round in range(config.max_scene_feedback_rounds):
                state = await _run_scene_phase(
                    state, config, agents, user_feedback=user_feedback,
                )
                if on_phase_complete:
                    on_phase_complete("scene", state)

                # Preview render
                state = await _run_preview_phase(state, config)
                if on_phase_complete:
                    on_phase_complete("preview", state)

                # ── GATE 3: Pre-execution (review code/params) ────
                decision, state = await _run_gate(
                    intervention_handler, config,
                    GateCheckpoint.PRE_EXECUTION, state,
                    phase_just_completed="scene",
                    phase_about_to_run="executor",
                    message="Review generated simulation code and parameters.",
                )
                if _is_abort(decision):
                    break
                if decision and decision.action == GateAction.REDO:
                    user_feedback = decision.feedback_text
                    logger.info("scene_redo", guidance=user_feedback[:100])
                    continue

                # ── GATE 4: Scene visualization ───────────────────
                preview_paths = tuple(
                    p.preview_path for p in state.scene_previews
                    if p.preview_path
                )
                decision, state = await _run_gate(
                    intervention_handler, config,
                    GateCheckpoint.SCENE_VISUALIZATION, state,
                    phase_just_completed="preview",
                    phase_about_to_run="executor",
                    message="Review the rendered scene visualization.",
                    preview_paths=preview_paths,
                )
                if _is_abort(decision):
                    break
                if decision and decision.action == GateAction.FEEDBACK:
                    user_feedback = decision.feedback_text
                    logger.info("scene_feedback", feedback=user_feedback[:100])
                    continue
                break

            if _is_abort(decision):
                break

            # ── Execution ─────────────────────────────────────────
            state = await _run_executor_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("executor", state)

            # ── GATE 5: Post-execution ────────────────────────────
            decision, state = await _run_gate(
                intervention_handler, config,
                GateCheckpoint.POST_EXECUTION, state,
                phase_just_completed="executor",
                phase_about_to_run="evaluator",
                message="Review execution results before evaluation.",
            )
            if _is_abort(decision):
                break

            # ── Evaluation ────────────────────────────────────────
            state = await _run_evaluator_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("evaluator", state)

            # ── Analysis ──────────────────────────────────────────
            state = await _run_analyst_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("analyst", state)

            # ── Literature validation ─────────────────────────────
            state = await _run_literature_validator_phase(state, config, agents)
            if on_phase_complete:
                on_phase_complete("literature_validator", state)

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


# ── Individual phase functions ───────────────────────────────────────

async def _run_literature_scout_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
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
        entries = tuple(
            LiteratureEntry.model_validate(e)
            for e in data.get("entries", [])
        )
        raw_questions = data.get("open_questions", [])
        open_questions = tuple(
            OpenQuestion.model_validate(q) if isinstance(q, dict)
            else OpenQuestion(question=q)
            for q in raw_questions
        )
        lit_context = LiteratureContext(
            entries=entries,
            summary=data.get("summary", ""),
            open_questions=open_questions,
            trivial_gaps=tuple(data.get("trivial_gaps", [])),
            methodology_notes=data.get("methodology_notes", ""),
        )
        return set_literature_context(state, lit_context)

    return set_literature_context(
        state,
        LiteratureContext(summary=response_text[:2000]),
    )


async def _run_citation_audit_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
    if not state.literature_context or not state.literature_context.entries:
        return state

    context = state_to_prompt_context(state)
    prompt = (
        f"Verify each citation in the literature context.\n\n"
        f"There are {len(state.literature_context.entries)} citations to check.\n\n"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase(
        "citation_auditor", prompt, config, agents,
    )

    data = _extract_json_from_text(response_text)
    if not data or "audited_entries" not in data:
        logger.warning("citation_audit_parse_failed", response=response_text[:200])
        return state

    audit_lookup: dict[str, dict] = {}
    for audited in data["audited_entries"]:
        original_title = audited.get("original_title", "")
        audit_lookup[original_title.lower().strip()] = audited

    verified_entries: list[LiteratureEntry] = []
    fabricated_count = 0
    for entry in state.literature_context.entries:
        audit = audit_lookup.get(entry.title.lower().strip())
        if audit and audit.get("verification_status") == "fabricated":
            fabricated_count += 1
            logger.warning(
                "fabricated_citation_removed",
                title=entry.title,
                note=audit.get("verification_note", ""),
            )
            continue

        if audit:
            corrected_entry = LiteratureEntry(
                title=audit.get("corrected_title", entry.title),
                authors=tuple(audit.get("corrected_authors", entry.authors)),
                year=audit.get("corrected_year", entry.year),
                key_findings=entry.key_findings,
                relevance=entry.relevance,
                url=audit.get("corrected_url", entry.url) or entry.url,
                doi=audit.get("corrected_doi", entry.doi) or entry.doi,
                verification_status="verified",
                verification_note=audit.get("verification_note", ""),
            )
            verified_entries.append(corrected_entry)
        else:
            verified_entries.append(entry)

    logger.info(
        "citation_audit_complete",
        total=len(state.literature_context.entries),
        verified=len(verified_entries),
        fabricated=fabricated_count,
    )

    audited_context = LiteratureContext(
        entries=tuple(verified_entries),
        summary=state.literature_context.summary,
        open_questions=state.literature_context.open_questions,
        trivial_gaps=state.literature_context.trivial_gaps,
        methodology_notes=state.literature_context.methodology_notes,
    )
    return set_literature_context(state, audited_context)


async def _run_hypothesis_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
    *,
    user_guidance: str = "",
) -> ExperimentState:
    context = state_to_prompt_context(state)

    guidance_section = ""
    if user_guidance:
        guidance_section = (
            f"\n\nIMPORTANT — User feedback on previous formalization:\n"
            f"{user_guidance}\n"
            f"Incorporate this feedback into your revised hypothesis.\n"
        )

    prompt = (
        f"Analyze this hypothesis and produce a structured experiment specification.\n\n"
        f"Hypothesis: {state.raw_hypothesis}\n\n"
        f"Files provided: {[f.path for f in state.files]}\n\n"
        f"{guidance_section}"
        f"{context}"
    )

    response_text, _ = await _run_agent_phase("hypothesis", prompt, config, agents)

    data = _extract_json_from_text(response_text)
    if data:
        hypothesis = Hypothesis.model_validate(data)
        state = add_hypothesis(state, hypothesis)
        logger.info(
            "hypothesis_quality",
            composite_score=hypothesis.quality_ratings.composite_score
            if hypothesis.quality_ratings else None,
        )
        return state

    return add_hypothesis(
        state,
        Hypothesis(raw_text=state.raw_hypothesis, formalized=response_text[:500]),
    )


async def _run_scene_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
    *,
    user_feedback: str = "",
) -> ExperimentState:
    context = state_to_prompt_context(state)

    feedback_section = ""
    if user_feedback:
        feedback_section = (
            f"\n\nIMPORTANT — User feedback on the scene/simulation:\n"
            f"{user_feedback}\n"
            f"Revise the simulation code to address this feedback.\n"
        )

    prompt = (
        f"Generate simulation scenes for this experiment.\n\n"
        f"{feedback_section}"
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


async def _run_preview_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
) -> ExperimentState:
    try:
        from agentsim.preview.renderer import preview_scene
        from agentsim.preview.scene_description import SceneDescription
    except ImportError:
        logger.warning("preview_skip", reason="preview module not available")
        return state

    for scene_spec in state.scenes:
        scene_desc_data = scene_spec.parameters.get("scene_description")
        if not scene_desc_data:
            logger.info("preview_skip_scene", scene_id=scene_spec.id,
                        reason="no scene_description in parameters")
            continue

        try:
            scene_desc = SceneDescription.model_validate(scene_desc_data)
            output_path = config.output_dir / f"preview_{scene_spec.id}.png"

            preview_scene(scene_desc, output_path)

            preview = ScenePreview(
                scene_id=scene_spec.id,
                preview_path=str(output_path),
            )
            state = add_scene_preview(state, preview)
            logger.info("preview_rendered", scene_id=scene_spec.id,
                        path=str(output_path))

        except FileNotFoundError:
            logger.warning("preview_skip_scene", scene_id=scene_spec.id,
                           reason="Blender not found")
            break
        except Exception as e:
            logger.warning("preview_failed", scene_id=scene_spec.id,
                           error=str(e))
            preview = ScenePreview(
                scene_id=scene_spec.id,
                is_valid=False,
                warnings=[str(e)],
            )
            state = add_scene_preview(state, preview)

    return state


async def _run_executor_phase(
    state: ExperimentState,
    config: OrchestratorConfig,
    agents: dict,
) -> ExperimentState:
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

    hypothesis_id = state.hypothesis.id if state.hypothesis else ""
    return set_literature_validation(
        state,
        LiteratureValidation(
            hypothesis_id=hypothesis_id,
            reasoning=response_text[:1000],
        ),
    )


def _save_state(state: ExperimentState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_state(state))
    logger.info("state_saved", path=str(path))
