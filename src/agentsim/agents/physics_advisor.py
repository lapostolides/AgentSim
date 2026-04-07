"""Physics Advisor Agent -- provides structured physics guidance.

Dedicated agent for physics consultation, using a curated constants
registry embedded directly in the prompt. Other agents consult this
agent via the consultation helper in agentsim.physics.consultation.
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

from agentsim.physics.constants import COMPUTATIONAL_IMAGING, UNIVERSAL
from agentsim.physics.domains.schema import DomainKnowledge

ADVISOR_PROMPT = """\
You are a physics advisor agent for computational science simulations.
Your role is to provide physics guidance to other agents in the pipeline.

## CRITICAL RULE
NEVER "recall" or "remember" physical constants from training data.
ALWAYS reference the constants registry provided below. If a constant
is not in the registry, say so explicitly and assess plausibility
based on dimensional analysis and physical reasoning.

## Constants Registry
{constants_registry}

{domain_knowledge_section}## Your Capabilities
- Identify governing equations for a given physical system
- Recommend dimensionless groups relevant to the simulation
- Assess parameter plausibility when not in the registry (per D-02)
- Detect physics domain from hypothesis and simulation context
- Recommend appropriate numerical methods and stability criteria
- Flag physically implausible scenarios or parameter combinations

## OUTPUT FORMAT -- STRICT
Return a single JSON object:
```json
{{
  "domain_detected": "<physics domain>",
  "confidence": <0.0-1.0>,
  "recommendations": ["<recommendation>", ...],
  "warnings": ["<warning>", ...],
  "governing_equations": ["<equation>", ...],
  "dimensionless_groups": ["<group>", ...]
}}
```

## Query Context
{query_context}

## Current Experiment State
{state_context}
"""


def _format_constants_for_prompt() -> str:
    """Format the constants registry for embedding in the advisor prompt.

    Returns:
        Formatted string listing all constants with name, symbol, value,
        unit, and description.
    """
    lines: list[str] = []
    lines.append("### Universal Constants (NIST 2018 CODATA)")
    for const in UNIVERSAL.values():
        lines.append(
            f"- {const.name} ({const.symbol}): "
            f"{const.magnitude} {const.unit} -- {const.description}"
        )

    lines.append("")
    lines.append("### Computational Imaging Constants")
    for const in COMPUTATIONAL_IMAGING.values():
        lines.append(
            f"- {const.name} ({const.symbol}): "
            f"{const.magnitude} {const.unit} -- {const.description}"
        )

    return "\n".join(lines)


def format_nlos_advisor_context(domain_knowledge: DomainKnowledge) -> str:
    """Format NLOS domain knowledge for the physics advisor prompt.

    Deprecated: use agentsim.physics.context.format_physics_context instead.

    Provides governing equations, parameter ranges, and reconstruction
    constraints for physics-grounded advisory when NLOS domain detected.

    Args:
        domain_knowledge: Loaded NLOS DomainKnowledge from YAML.

    Returns:
        Formatted context string.
    """
    lines: list[str] = []
    lines.append("### NLOS Transient Imaging Domain Knowledge")
    lines.append("")

    # Equations
    for eq in domain_knowledge.governing_equations:
        lines.append(f"- {eq.name}: {eq.description}")

    # Sensor params
    if domain_knowledge.sensor_parameters and domain_knowledge.sensor_parameters.spad:
        spad = domain_knowledge.sensor_parameters.spad
        lines.append("")
        lines.append("SPAD sensor typical parameters:")
        if spad.temporal_resolution_ps:
            lines.append(
                f"- Temporal resolution: {spad.temporal_resolution_ps.typical} ps "
                f"(range: {spad.temporal_resolution_ps.min}"
                f"-{spad.temporal_resolution_ps.max} ps)"
            )
        if spad.fov_degrees:
            lines.append(
                f"- FOV: {spad.fov_degrees.typical} deg "
                f"(range: {spad.fov_degrees.min}-{spad.fov_degrees.max} deg)"
            )

    # Published parameters
    if domain_knowledge.published_parameter_index:
        lines.append("")
        lines.append("Published NLOS experiment parameters:")
        for key, pub in domain_knowledge.published_parameter_index.items():
            lines.append(
                f"- {pub.paper} ({pub.venue}): "
                f"wall={pub.wall_size_m}m, dt={pub.temporal_resolution_ps}ps, "
                f"{pub.scanning}"
            )

    return "\n".join(lines)


def create_physics_advisor_agent(
    domain_knowledge: str = "",
) -> AgentDefinition:
    """Create the Physics Advisor AgentDefinition.

    The prompt embeds the full constants registry so the agent never
    needs to recall constants from training data.

    Args:
        domain_knowledge: Optional domain knowledge context to inject.

    Returns:
        AgentDefinition configured for physics advisory with model='sonnet'.
    """
    constants_str = _format_constants_for_prompt()
    domain_knowledge_section = (
        f"\n{domain_knowledge}\n\n" if domain_knowledge else ""
    )
    return AgentDefinition(
        description=(
            "Physics advisor providing structured guidance on governing equations, "
            "dimensionless groups, parameter plausibility, and numerical methods. "
            "Consult this agent when physics validation needs LLM interpretation."
        ),
        prompt=ADVISOR_PROMPT.format(
            constants_registry=constants_str,
            domain_knowledge_section=domain_knowledge_section,
            query_context="{query_context}",
            state_context="{state_context}",
        ),
        tools=["Read"],
        model="sonnet",
    )
