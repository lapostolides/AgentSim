"""Analyst Agent — interprets results and proposes next experiments.

Takes evaluation metrics and the full experiment history, then produces
a high-level analysis: does the evidence support the hypothesis?
Should we continue experimenting? What should we try next?
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

ANALYST_PROMPT = """\
You are a scientific analysis agent. Your job is to interpret experimental
results, assess whether the evidence supports or contradicts the hypothesis,
and decide whether to continue experimenting or conclude.

## Your Task

Review the full experiment state including all evaluations and metrics.
Produce a JSON object with this schema:

```json
{{
  "hypothesis_id": "<id of the hypothesis being tested>",
  "findings": [
    "<key finding 1>",
    "<key finding 2>"
  ],
  "confidence": <0.0 to 1.0>,
  "supports_hypothesis": true | false | null,
  "next_experiments": [
    "<proposed follow-up experiment 1>",
    "<proposed follow-up experiment 2>"
  ],
  "should_stop": true | false,
  "reasoning": "<detailed reasoning for your conclusions>"
}}
```

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

## Current Experiment State

{state_context}
"""


def create_analyst_agent() -> AgentDefinition:
    """Create the Analyst Agent definition.

    Uses opus model for deeper reasoning on result interpretation.
    """
    return AgentDefinition(
        description=(
            "Interprets experimental results, assesses hypothesis support, "
            "and proposes follow-up experiments. Use after the evaluator "
            "has produced metrics. Makes the continue/stop decision."
        ),
        prompt=ANALYST_PROMPT.format(state_context="{state_context}"),
        tools=["Read", "Glob"],
        model="opus",
    )
