"""Knowledge graph context formatters for agent prompts (D-06).

Each function takes an ExperimentState and returns a formatted markdown
string for a specific agent role, or empty string when feasibility_result
is None (D-14).
"""

from __future__ import annotations

from agentsim.knowledge_graph.crb.sensitivity import SensitivityResult
from agentsim.knowledge_graph.models import (
    FeasibilityResult,
    SensorConfig,
    SensorFamily,
)
from agentsim.knowledge_graph.seeder import SHARED_PHYSICS_EDGES
from agentsim.state.models import ExperimentState


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_crb_bound(config: SensorConfig) -> str:
    """Format a CRB bound value, or 'N/A' if None."""
    if config.crb_bound is None:
        return "N/A"
    return f"{config.crb_bound:.4g} {config.crb_unit}"


def _ranked_configs_table(configs: tuple[SensorConfig, ...], limit: int = 5) -> list[str]:
    """Render a markdown table of ranked sensor configurations.

    Args:
        configs: Ranked sensor configs from FeasibilityResult.
        limit: Maximum number of configs to show.

    Returns:
        List of formatted markdown lines.
    """
    lines: list[str] = []
    lines.append("### Ranked Sensor Configurations")
    lines.append("")
    lines.append("| Rank | Sensor | Family | CRB Bound | Score | Confidence |")
    lines.append("|------|--------|--------|-----------|-------|------------|")
    for config in configs[:limit]:
        lines.append(
            f"| {config.rank} "
            f"| {config.sensor_name} "
            f"| {config.sensor_family.value} "
            f"| {_format_crb_bound(config)} "
            f"| {config.feasibility_score:.2f} "
            f"| {config.confidence.value} |"
        )
    lines.append("")
    return lines


def _constraint_satisfaction_section(config: SensorConfig) -> list[str]:
    """Render constraint satisfaction for a single config.

    Args:
        config: Top-ranked config to detail.

    Returns:
        List of formatted markdown lines.
    """
    lines: list[str] = []
    if not config.constraint_satisfaction:
        return lines
    lines.append("### Constraint Satisfaction")
    lines.append("")
    lines.append(f"Top-ranked config: **{config.sensor_name}**")
    lines.append("")
    for cs in config.constraint_satisfaction:
        status = "satisfied" if cs.satisfied else "UNSATISFIED"
        margin_str = f" (margin: {cs.margin:.2g} {cs.unit})" if cs.unit else ""
        lines.append(f"- {cs.constraint_name}: {status}{margin_str}")
        if cs.details:
            lines.append(f"  {cs.details}")
    lines.append("")
    return lines


def _top_config(feasibility: FeasibilityResult) -> SensorConfig | None:
    """Return top-ranked config or None if empty."""
    if not feasibility.ranked_configs:
        return None
    return feasibility.ranked_configs[0]


def _crb_efficiency_section(config: SensorConfig, *, as_info: bool = False) -> list[str]:
    """Render CRB performance floor / efficiency ratio context.

    Args:
        config: Top-ranked config with optional CRB bound.
        as_info: If True, add analyst framing (informational, not trigger).

    Returns:
        List of formatted markdown lines.
    """
    lines: list[str] = []
    if config.crb_bound is not None:
        lines.append(f"**CRB bound:** {config.crb_bound:.4g} {config.crb_unit}")
        lines.append(
            f"**Sensor:** {config.sensor_name} ({config.sensor_family.value}) "
            f"+ {config.algorithm_name}"
        )
        lines.append("")
        lines.append(
            "This is the theoretical best achievable performance for this "
            "sensor+task combination."
        )
        lines.append("")
        lines.append(
            "Report the efficiency ratio: actual_error / crb_bound. "
            "Values close to 1.0 mean the algorithm is approaching the physics "
            "limit (this is GOOD -- it means the bottleneck is physical, not "
            "algorithmic). Values >> 1.0 suggest algorithmic improvement is possible."
        )
        if as_info:
            lines.append("")
            lines.append(
                "Use this as information for your analysis, not a trigger."
            )
    lines.append("")
    return lines


def _shares_physics_neighbors(family: SensorFamily) -> list[str]:
    """Find SHARED_PHYSICS edges involving a sensor family.

    Args:
        family: Sensor family to filter by.

    Returns:
        List of formatted markdown lines.
    """
    lines: list[str] = []
    neighbors: list[tuple[str, str]] = []
    for edge in SHARED_PHYSICS_EDGES:
        if edge.source_family == family:
            neighbors.append((edge.target_family.value, edge.shared_principle))
        elif edge.target_family == family:
            neighbors.append((edge.source_family.value, edge.shared_principle))

    if neighbors:
        lines.append("### Alternative Sensors (SHARES_PHYSICS)")
        lines.append("")
        lines.append(
            "These sensor families share underlying physics with "
            f"{family.value} and may offer alternative approaches:"
        )
        lines.append("")
        for neighbor_family, principle in neighbors:
            lines.append(f"- **{neighbor_family}**: {principle}")
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_hypothesis_graph_context(state: ExperimentState) -> str:
    """Render knowledge graph context for the hypothesis generation agent.

    Shows ranked sensor configurations, constraint satisfaction for the
    top config, pruned count, and research gap guidance.

    Args:
        state: Current experiment state.

    Returns:
        Formatted markdown string, or '' if feasibility_result is None.
    """
    if state.feasibility_result is None:
        return ""

    feasibility = state.feasibility_result
    lines: list[str] = []
    lines.append("## Knowledge Graph: Feasibility Context")
    lines.append("")

    # Ranked configs table (top 5)
    lines.extend(_ranked_configs_table(feasibility.ranked_configs, limit=5))

    # Constraint satisfaction for top config
    top = _top_config(feasibility)
    if top is not None:
        lines.extend(_constraint_satisfaction_section(top))

    # Pruned count
    if feasibility.pruned_count > 0:
        lines.append(
            f"{feasibility.pruned_count} sensors were pruned "
            "(did not satisfy constraints)."
        )
        lines.append("")

    # Research gaps
    lines.append("### Research Gaps")
    lines.append("")
    lines.append(
        "Identify sensor-task combinations with no experimental coverage. "
        "Proposing experiments that fill these gaps creates high-value novelty."
    )
    lines.append("")

    return "\n".join(lines)


def format_scene_graph_context(
    state: ExperimentState,
    sensitivity_result: SensitivityResult | None = None,
) -> str:
    """Render knowledge graph context for the scene generation agent.

    Shows sensitivity analysis rankings (if available) to guide parameter
    variation in generated scenes, plus top sensor reference.

    Args:
        state: Current experiment state.
        sensitivity_result: Optional Morris method sensitivity analysis.

    Returns:
        Formatted markdown string, or '' if feasibility_result is None.
    """
    if state.feasibility_result is None:
        return ""

    feasibility = state.feasibility_result
    top = _top_config(feasibility)
    lines: list[str] = []
    lines.append("## Knowledge Graph: Sensitivity-Guided Scene Generation")
    lines.append("")

    if sensitivity_result is not None and sensitivity_result.entries:
        lines.append("### Parameter Sensitivity Rankings (Morris Method)")
        lines.append("")
        lines.append("| Rank | Parameter | mu_star | Classification |")
        lines.append("|------|-----------|---------|----------------|")
        for entry in sensitivity_result.entries:
            lines.append(
                f"| {entry.rank} "
                f"| {entry.parameter_name} "
                f"| {entry.mu_star:.4g} "
                f"| {entry.classification} |"
            )
        lines.append("")
        lines.append(
            "Generate scenes that vary the HIGH-SENSITIVITY parameters across "
            "their range. Low-sensitivity parameters can use defaults."
        )
        lines.append("")
    else:
        lines.append(
            "No sensitivity analysis available. Use the top-ranked sensor "
            "configuration from feasibility results."
        )
        lines.append("")

    # Top sensor reference
    if top is not None:
        lines.append(
            f"**Top-ranked sensor:** {top.sensor_name} "
            f"({top.sensor_family.value})"
        )
        lines.append("")

    return "\n".join(lines)


def format_evaluator_graph_context(state: ExperimentState) -> str:
    """Render knowledge graph context for the evaluator agent.

    Shows CRB performance floor and efficiency ratio framing.
    No pass/fail language -- context for reasoning only (D-07).

    Args:
        state: Current experiment state.

    Returns:
        Formatted markdown string, or '' if feasibility_result is None.
    """
    if state.feasibility_result is None:
        return ""

    feasibility = state.feasibility_result
    top = _top_config(feasibility)
    lines: list[str] = []
    lines.append("## Knowledge Graph: CRB Performance Floor")
    lines.append("")

    if top is not None:
        lines.extend(_crb_efficiency_section(top))

    return "\n".join(lines)


def format_analyst_graph_context(state: ExperimentState) -> str:
    """Render comprehensive knowledge graph context for the analyst agent.

    Includes CRB efficiency, top sensor details, iteration trends,
    SHARES_PHYSICS neighbors, and re-query instructions (D-07, D-08).

    Args:
        state: Current experiment state.

    Returns:
        Formatted markdown string, or '' if feasibility_result is None.
    """
    if state.feasibility_result is None:
        return ""

    feasibility = state.feasibility_result
    top = _top_config(feasibility)
    lines: list[str] = []
    lines.append("## Knowledge Graph: Full Analysis Context")
    lines.append("")

    # Section 1: CRB efficiency
    if top is not None:
        lines.append("### CRB Efficiency Context")
        lines.append("")
        lines.extend(_crb_efficiency_section(top, as_info=True))

    # Section 2: Top sensor details
    if top is not None:
        lines.append("### Top Sensor Configuration")
        lines.append("")
        lines.append(f"- **Sensor:** {top.sensor_name}")
        lines.append(f"- **Family:** {top.sensor_family.value}")
        lines.append(f"- **Algorithm:** {top.algorithm_name}")
        lines.append(f"- **Feasibility score:** {top.feasibility_score:.2f}")
        if top.notes:
            lines.append(f"- **Notes:** {top.notes}")
        lines.append("")

    # Section 3: Iteration trend
    if len(state.evaluations) > 1:
        lines.append("### Iteration Trend")
        lines.append("")
        lines.append(
            f"Multiple evaluations available ({len(state.evaluations)}) -- "
            "look for convergence or divergence patterns."
        )
        lines.append("")

    # Section 4: SHARES_PHYSICS neighbors
    if top is not None:
        lines.extend(_shares_physics_neighbors(top.sensor_family))

    # Section 5: Re-query instruction
    lines.append("### Re-query Instruction")
    lines.append("")
    lines.append(
        "If you identify a parameter bottleneck, you MAY recommend constraint "
        "modifications. Include a 'constraint_modifications' dict in your output "
        '(e.g., {"temporal_resolution_s": 5e-11, "budget_usd": 10000}). '
        "The runner will re-query the knowledge graph with these constraints."
    )
    lines.append("")

    return "\n".join(lines)
