"""Analyst Agent — interprets results and proposes next experiments.

Takes evaluation metrics and the full experiment history, then produces
a high-level analysis: does the evidence support the hypothesis?
Should we continue experimenting? What should we try next?
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

from agentsim.physics.domains.schema import DomainKnowledge

ANALYST_PROMPT = """\
You are a scientific analysis agent. Your job is to interpret experimental
results, assess whether the evidence supports or contradicts the hypothesis,
and decide whether to continue experimenting or conclude.

## Your Task

Review the full experiment state including all evaluations and metrics.

## OUTPUT FORMAT — STRICT

Return a single JSON object. Do NOT wrap it in any outer object.

```json
{{
  "hypothesis_id": "<id of the hypothesis being tested>",
  "findings": ["<key finding as string>", "<key finding as string>"],
  "confidence": <0.0 to 1.0>,
  "supports_hypothesis": true | false | null,
  "next_experiments": ["<proposed follow-up as string>"],
  "should_stop": true | false,
  "reasoning": "<detailed reasoning for your conclusions>"
}}
```

CRITICAL: Do NOT wrap in an outer object like {{"analysis": ...}}.
"findings" and "next_experiments" MUST be flat lists of strings.
"hypothesis_id" should match the id from the experiment state.

## Decision Framework

### When to STOP (should_stop: true):
- Confidence >= 0.9 and clear support/rejection of hypothesis
- Maximum iterations reached (check iteration count)
- All parameter space has been explored
- Diminishing returns from additional experiments

### When to CONTINUE (should_stop: false):
- Confidence < 0.9 and more parameter space to explore
- Unexpected results that need investigation
- Initial results are promising but inconclusive
- Specific follow-up experiments could resolve ambiguity

## Guidelines

- Be rigorous: distinguish correlation from causation
- Consider confounding variables and assumptions
- Propose SPECIFIC follow-up experiments (not vague suggestions)
- Reference actual metric values in your findings
- If results are contradictory, explain possible reasons
- Consider statistical significance where applicable
- Track how confidence has evolved across iterations

{physics_section}## Current Experiment State

{state_context}
"""


def format_nlos_analysis_context(domain_knowledge: DomainKnowledge) -> str:
    """Format NLOS-specific validation criteria for the analyst.

    Deprecated: use agentsim.physics.context.format_analysis_context instead.

    Tells the analyst what physics-based checks to apply when
    evaluating NLOS transient imaging results.

    Args:
        domain_knowledge: Loaded NLOS DomainKnowledge from YAML.

    Returns:
        Formatted context string for inclusion in analyst prompt.
    """
    lines: list[str] = []
    lines.append("## NLOS Transient Imaging Result Validation")
    lines.append("")
    lines.append(
        "When analyzing NLOS experiment results, check these physics expectations:"
    )
    lines.append("")
    lines.append("### Signal Physics")
    lines.append(
        "- Transient signal should follow inverse-square falloff with distance"
    )
    lines.append(
        "- Temporal peak locations should match expected round-trip path lengths"
    )
    lines.append(
        "- Signal amplitude should decrease for objects farther from relay wall"
    )
    lines.append("")
    lines.append("### Reconstruction Quality")
    lines.append("- Spatial resolution bounded by relay wall sampling density")
    lines.append("- Depth resolution bounded by temporal bin width: c * dt / 2")
    lines.append(
        "- Reconstructed objects should be within the visibility cone of the relay wall"
    )
    lines.append("")
    lines.append("### Common Failure Modes")
    lines.append("- Missing or duplicate peaks in transient (geometry error)")
    lines.append("- Reconstruction artifacts outside physically possible volume")
    lines.append("- Resolution worse than Nyquist limit (undersampled relay wall)")
    lines.append("")

    # Add algorithm-specific checks from domain knowledge
    if domain_knowledge.reconstruction_algorithms:
        lines.append("### Algorithm-Specific Validation")
        for key, algo in domain_knowledge.reconstruction_algorithms.items():
            if algo.requires_confocal:
                lines.append(
                    f"- {algo.name}: requires confocal scanning data. "
                    "Non-confocal input will produce artifacts."
                )
            if algo.spatial_resolution:
                lines.append(f"- {algo.name}: {algo.spatial_resolution}")
        lines.append("")

    lines.append(
        "Flag any results that violate these physics expectations "
        "as potential simulation errors."
    )
    return "\n".join(lines)


def create_analyst_agent(
    analysis_context: str = "",
) -> AgentDefinition:
    """Create the Analyst Agent definition.

    Args:
        analysis_context: Optional physics validation criteria to inject.

    Uses opus model for deeper reasoning on result interpretation.
    """
    physics_section = f"\n{analysis_context}\n\n" if analysis_context else ""
    return AgentDefinition(
        description=(
            "Interprets experimental results, assesses hypothesis support, "
            "and proposes follow-up experiments. Use after the evaluator "
            "has produced metrics. Makes the continue/stop decision."
        ),
        prompt=ANALYST_PROMPT.format(
            state_context="{state_context}",
            physics_section=physics_section,
        ),
        tools=["Read", "Glob"],
        model="claude-opus-4-6",
    )
