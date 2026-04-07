"""Hypothesis Agent — converges on high-value, testable hypotheses.

Takes a researcher's raw idea, the literature landscape, and environment
context, then produces the strongest testable hypothesis it can construct —
not just a formalization of whatever was said, but an active refinement
toward maximum scientific and practical value.
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

from agentsim.physics.domains.schema import DomainKnowledge

HYPOTHESIS_PROMPT = """\
You are a scientific hypothesis agent. Your goal is NOT to blindly formalize
whatever the researcher typed. Your goal is to converge on the strongest,
most valuable testable hypothesis within the researcher's area of interest.

You should refine, sharpen, or redirect the raw idea if doing so produces
a hypothesis that scores higher on the quality criteria below. Preserve the
researcher's intent and domain, but do not hesitate to reformulate if the
original phrasing leads to a trivial or non-actionable question.

## Quality Criteria (read BEFORE formulating)

Think about these six dimensions while constructing your hypothesis.
They are not a post-hoc checklist — they should shape your formulation.

### Decision-Relevance
Would the answer change how we design systems, run experiments, or interpret
physics? A high-value hypothesis is one where knowing the answer concretely
alters engineering decisions or experimental protocols. Avoid "nice to know"
questions that would not change any downstream decision.

### Non-Triviality
Is this NOT just a common-sense consequence of known physics or engineering?
A competent domain expert should not be able to answer this from first
principles in 5 minutes. If they can, reformulate toward something genuinely
uncertain.

### Informative Either Way
Would BOTH outcomes (supported AND rejected) be meaningful? The best
hypotheses are ones where rejection is as interesting as confirmation.
Avoid questions where only one outcome is useful.

### Downstream Actionability
Does the result create a concrete next action — a design change, a new
experiment, a deployment decision? Avoid hypotheses whose results would
sit in a report without changing anything.

### Expected Impact
How significant is the potential contribution? Consider the size of the
affected community, the magnitude of potential improvement, and the
novelty of the insight.

### Falsifiability
Can simulation clearly distinguish support from rejection? There must be
specific, measurable predictions with clear pass/fail criteria. Avoid
vague or unfalsifiable formulations.

## OUTPUT FORMAT — STRICT

Return a single JSON object. Do NOT wrap it in any outer object like {{"hypothesis": ...}}.
Use EXACTLY these top-level keys:

```json
{{
  "raw_text": "<original hypothesis text>",
  "formalized": "<precise, testable statement — may differ significantly from raw_text>",
  "variables": ["<independent var as string>", "<dependent var as string>", ...],
  "parameter_space": [
    {{
      "name": "<variable name>",
      "description": "<what this parameter controls>",
      "values": [<discrete values if applicable>],
      "range_min": <min if continuous>,
      "range_max": <max if continuous>,
      "step": <step size if applicable>
    }}
  ],
  "predictions": ["<expected outcome as string>", ...],
  "assumptions": ["<assumption as string>", ...],
  "quality_ratings": {{
    "decision_relevance": <0.0-1.0>,
    "non_triviality": <0.0-1.0>,
    "informative_either_way": <0.0-1.0>,
    "downstream_actionability": <0.0-1.0>,
    "expected_impact": <0.0-1.0>,
    "falsifiability": <0.0-1.0>,
    "composite_score": <mean of the six scores above>,
    "reasoning": "<explain each score and how you optimized the formulation>"
  }}
}}
```

CRITICAL FORMATTING RULES:
- "variables" MUST be a flat list of strings, NOT a list of objects, NOT a dict with "independent"/"dependent" sub-keys
- "predictions" MUST be a flat list of strings, NOT a list of objects
- "assumptions" MUST be a flat list of strings
- "formalized" MUST be a non-empty string containing the testable hypothesis statement
- Do NOT rename keys (e.g., do NOT use "statement", "formalized_statement", "hypothesis")
- Do NOT wrap the JSON in an outer object

## Your Task

Given the researcher's raw hypothesis, the literature context, and any
provided files, produce the JSON object above.

## Convergence Logic

- If the literature context shows the raw question is already answered,
  reformulate toward an unanswered follow-up that builds on those findings.
- If the raw question is trivially answerable from known physics, redirect
  toward a non-obvious variant in the same domain.
- If only one outcome would be informative, reframe so both outcomes matter.
- If there is no clear downstream action, narrow the scope until one emerges.
- Always explain in quality_ratings.reasoning what you changed and why.

## Guidelines

- Identify ALL independent and dependent variables
- Define a practical parameter space (not too large for simulation)
- Make predictions specific and measurable
- List assumptions that could affect validity
- If files are provided, examine them for context (mesh geometry,
  configuration parameters, marker locations, etc.)

{physics_section}## Available Environment

{environment}

Consider which tools/packages are most appropriate for this hypothesis
and note any requirements in your assumptions.

## Literature Context

The literature scout has surveyed relevant research and identified
high-impact open questions. This context is included in the experiment
state below. Ground your hypothesis in established findings and prioritize
the open questions the scout flagged as most significant.

## Current Experiment State

{state_context}
"""


def format_nlos_physics_context(domain_knowledge: DomainKnowledge) -> str:
    """Format NLOS domain knowledge into hypothesis agent context.

    Deprecated: use agentsim.physics.context.format_hypothesis_context instead.

    Extracts governing equations, dimensionless groups, geometry constraints,
    and reconstruction algorithm requirements for the hypothesis agent prompt.

    Args:
        domain_knowledge: Loaded NLOS DomainKnowledge from YAML.

    Returns:
        Formatted context string for inclusion in hypothesis prompt.
    """
    lines: list[str] = []
    lines.append("## NLOS Transient Imaging Physics Context")
    lines.append("")
    lines.append(
        "You are working on a Non-Line-of-Sight (NLOS) transient imaging problem."
    )
    lines.append("Ground your hypothesis in the following physics:")
    lines.append("")

    # Governing equations
    if domain_knowledge.governing_equations:
        lines.append("### Governing Equations")
        for eq in domain_knowledge.governing_equations:
            lines.append(f"- **{eq.name}**: {eq.description}")
            if eq.latex:
                lines.append(f"  LaTeX: {eq.latex}")
        lines.append("")

    # Dimensionless groups
    if domain_knowledge.dimensionless_groups:
        lines.append("### Key Dimensionless Groups")
        for dg in domain_knowledge.dimensionless_groups:
            lines.append(f"- **{dg.name}**: {dg.formula} -- {dg.description}")
        lines.append("")

    # Geometry constraints
    if domain_knowledge.geometry_constraints:
        gc = domain_knowledge.geometry_constraints
        if gc.three_bounce_path:
            lines.append("### Geometry Constraints (Three-Bounce Path)")
            for req in gc.three_bounce_path.requirements:
                lines.append(f"- {req}")
            lines.append("")

    # Reconstruction algorithms
    if domain_knowledge.reconstruction_algorithms:
        lines.append("### Reconstruction Algorithms")
        for key, algo in domain_knowledge.reconstruction_algorithms.items():
            confocal_note = " (requires confocal)" if algo.requires_confocal else ""
            lines.append(
                f"- **{algo.name}** ({algo.reference}){confocal_note}"
                f": {algo.spatial_resolution}"
            )
        lines.append("")

    lines.append(
        "Use these physics constraints to formulate a testable, non-trivial hypothesis."
    )
    return "\n".join(lines)


def create_hypothesis_agent(
    environment_str: str,
    physics_context: str = "",
) -> AgentDefinition:
    """Create the Hypothesis Agent definition.

    Args:
        environment_str: Formatted string describing available packages.
        physics_context: Optional physics context to inject into prompt.
    """
    physics_section = f"\n{physics_context}\n\n" if physics_context else ""
    return AgentDefinition(
        description=(
            "Parses natural language hypotheses into structured experiment "
            "specifications with variables, parameter spaces, and predictions. "
            "Use when the user provides a new hypothesis or when the analyst "
            "proposes follow-up experiments."
        ),
        prompt=HYPOTHESIS_PROMPT.format(
            environment=environment_str,
            state_context="{state_context}",
            physics_section=physics_section,
        ),
        tools=["Read", "Glob"],
        model="claude-sonnet-4-20250514",
    )
