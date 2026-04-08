"""Physics advisor consultation helper with structured logging.

Provides functions for querying the physics advisor agent, parsing
responses, logging consultations to JSONL, and tracking summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from agentsim.physics.models import (
    ConsultationLogEntry,
    PhysicsConsultationSummary,
    PhysicsGuidance,
    PhysicsQuery,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# D-02 reasoning query routing
# ---------------------------------------------------------------------------

# D-02 query type mapping: SensorQuery, AlgorithmQuery -> optimize_setup;
# ExplorerQuery -> find_novel_regions. optimize_setup is the combined mode.
_OPTIMIZER_QUERY_TYPES = frozenset({"optimize_setup", "sensor_query", "algorithm_query"})


def _route_reasoning_query(
    query: PhysicsQuery,
    bundle: Any,
    paradigm: Any,
) -> Any:
    """Route reasoning query types to deterministic computation.

    Returns deterministic result for known query types, None for unknown
    (which should be handled by the standard LLM advisor path).

    Per D-02, three named sub-query types are supported:
    - sensor_query: which sensor class for these constraints (routes to optimize_setup)
    - algorithm_query: which algorithm for this paradigm+sensor combo (routes to optimize_setup)
    - optimize_setup: combined sensor+algorithm optimization
    - explore_novel: parameter regions not covered by published baselines

    Args:
        query: Physics query with query_type and parameters.
        bundle: Loaded domain bundle (required for optimize_setup).
        paradigm: Detected paradigm (required for both modes).

    Returns:
        OptimizerResult, ExplorerResult, or None.
    """
    if paradigm is None:
        return None

    hypothesis_params = {
        k: v for k, v in query.parameters.items()
        if isinstance(v, (int, float))
    }

    if query.query_type in _OPTIMIZER_QUERY_TYPES and bundle is not None:
        from agentsim.physics.reasoning import optimize_setup
        return optimize_setup(hypothesis_params, bundle, paradigm)

    if query.query_type == "explore_novel":
        from agentsim.physics.reasoning import find_novel_regions
        return find_novel_regions(hypothesis_params, paradigm)

    return None


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_advisor_prompt(query: PhysicsQuery, state_context: str) -> str:
    """Build the advisor prompt from a query and state context.

    Args:
        query: The physics query to embed in the prompt.
        state_context: Serialized experiment state for context.

    Returns:
        Formatted prompt string for the physics advisor.
    """
    params_str = ", ".join(
        f"{k}={v}" for k, v in query.parameters.items()
    )
    return (
        f"Query type: {query.query_type}\n"
        f"Context: {query.context}\n"
        f"Parameters: {params_str}\n\n"
        f"Experiment state:\n{state_context}"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _extract_json_from_response(text: str) -> dict | None:
    """Extract JSON from agent response text.

    Tries multiple strategies: direct parse, code fence extraction,
    embedded JSON object.

    Args:
        text: Raw response text from the advisor agent.

    Returns:
        Parsed dict or None if extraction fails.
    """
    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: code fence extraction
    if "```" in text:
        for block in text.split("```"):
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                continue

    # Strategy 3: embedded JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _parse_guidance(response_text: str) -> PhysicsGuidance:
    """Parse advisor response into PhysicsGuidance.

    Handles valid JSON, code-fenced JSON, and embedded JSON.
    Returns a default PhysicsGuidance on parse failure.

    Args:
        response_text: Raw text response from the physics advisor.

    Returns:
        PhysicsGuidance with parsed or default values.
    """
    data = _extract_json_from_response(response_text)
    if data is None:
        return PhysicsGuidance(
            domain_detected="unknown",
            confidence=0.0,
            recommendations=(),
            warnings=("Failed to parse advisor response",),
        )

    return PhysicsGuidance(
        domain_detected=data.get("domain_detected", ""),
        confidence=float(data.get("confidence", 0.0)),
        recommendations=tuple(data.get("recommendations", ())),
        warnings=tuple(data.get("warnings", ())),
        governing_equations=tuple(data.get("governing_equations", ())),
        dimensionless_groups=tuple(data.get("dimensionless_groups", ())),
    )


# ---------------------------------------------------------------------------
# Consultation logging
# ---------------------------------------------------------------------------


def _append_consultation_log(log_dir: Path, entry: ConsultationLogEntry) -> None:
    """Append a consultation log entry to JSONL file.

    Creates the file if it does not exist.

    Args:
        log_dir: Directory to write the log file in.
        entry: Consultation entry to log.
    """
    log_file = log_dir / "physics_consultations.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry_dict = entry.model_dump(mode="json")
    with open(log_file, "a") as f:
        f.write(json.dumps(entry_dict) + "\n")


# ---------------------------------------------------------------------------
# Consultation summary tracking
# ---------------------------------------------------------------------------


def _update_consultation_summary(
    current: PhysicsConsultationSummary | None,
    entry: ConsultationLogEntry,
) -> PhysicsConsultationSummary:
    """Update the consultation summary with a new entry.

    Creates a new summary if current is None. Returns a new immutable
    summary with incremented counts.

    Args:
        current: Existing summary or None for first consultation.
        entry: New consultation log entry to incorporate.

    Returns:
        New PhysicsConsultationSummary with updated counts.
    """
    if current is None:
        current = PhysicsConsultationSummary()

    # Add domain if not already present
    domains = list(current.domains_consulted)
    if entry.domain and entry.domain not in domains:
        domains.append(entry.domain)

    warning_count = len(entry.response.warnings)

    return PhysicsConsultationSummary(
        total_consultations=current.total_consultations + 1,
        domains_consulted=tuple(domains),
        total_errors=current.total_errors,
        total_warnings=current.total_warnings + warning_count,
    )


# ---------------------------------------------------------------------------
# Main consultation function
# ---------------------------------------------------------------------------


async def consult_physics_advisor(
    query: PhysicsQuery,
    state_context: str,
    config: Any,
    agents: dict,
    log_dir: Path | None = None,
) -> tuple[PhysicsGuidance, ConsultationLogEntry]:
    """Consult the physics advisor agent and log the interaction.

    Args:
        query: The physics query to send.
        state_context: Serialized experiment state for context.
        config: OrchestratorConfig for agent phase execution.
        agents: Agent registry dict.
        log_dir: Optional directory for JSONL logging.

    Returns:
        Tuple of (PhysicsGuidance, ConsultationLogEntry).
    """
    # Lazy import to avoid circular dependency (consultation <-> runner)
    from agentsim.orchestrator.runner import _run_agent_phase

    prompt = _build_advisor_prompt(query, state_context)

    response_text, _ = await _run_agent_phase(
        "physics_advisor", prompt, config, agents,
    )

    guidance = _parse_guidance(response_text)

    entry = ConsultationLogEntry(
        query=query,
        response=guidance,
        domain=guidance.domain_detected,
        confidence=guidance.confidence,
    )

    logger.info(
        "physics_consultation",
        query_type=query.query_type,
        domain=guidance.domain_detected,
        confidence=guidance.confidence,
    )

    if log_dir is not None:
        _append_consultation_log(log_dir, entry)

    return guidance, entry
