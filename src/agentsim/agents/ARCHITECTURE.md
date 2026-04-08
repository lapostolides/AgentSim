# agents

> Factory functions that build `AgentDefinition` instances for each role in the experiment pipeline.

## Files

### __init__.py
Barrel export of the six primary agent factory functions: `create_analyst_agent`, `create_evaluator_agent`, `create_executor_agent`, `create_hypothesis_agent`, `create_physics_advisor_agent`, `create_scene_agent`.

### literature_scout.py
**Literature Scout** -- First agent in the pipeline. Surveys academic literature for a given hypothesis using web search and fetch. Produces a `LiteratureContext` with paper entries, a synthesis summary, impact-filtered open questions, trivial gaps, and methodology notes.

- Model: `claude-opus-4-6` (deep reasoning for research synthesis)
- Tools: `WebSearch`, `WebFetch`, `Read`
- Factory: `create_literature_scout_agent()`

### citation_auditor.py
**Citation Auditor** -- Runs immediately after literature scout. Verifies each citation is real (not hallucinated) via DOI lookup and web search. Returns audited entries with verification status, corrections, and a fabrication count.

- Model: `claude-sonnet-4-20250514` (systematic checking, cost-efficient)
- Tools: `WebSearch`, `WebFetch`, `Read`
- Factory: `create_citation_auditor_agent()`

### hypothesis.py
**Hypothesis Agent** -- Takes the raw research question plus literature context and produces a structured, high-quality hypothesis. Actively refines and redirects (not just formalizes) toward maximum scientific value. Self-rates on six quality dimensions (decision-relevance, non-triviality, informative-either-way, downstream-actionability, expected-impact, falsifiability).

- Model: `claude-sonnet-4-20250514`
- Tools: `Read`, `Glob`
- Factory: `create_hypothesis_agent(environment_str, physics_context="")`
- Also exports: `format_nlos_physics_context()` (deprecated, use `physics.context`)

### scene.py
**Scene Agent** -- Generates executable Python simulation code from the structured hypothesis and plan. Writes complete, runnable scripts using available packages. Parameterized by environment discovery results.

- Model: `sonnet`
- Tools: `Read`
- Factory: `create_scene_agent(environment_str, physics_context="")`

### executor.py
**Executor Agent** -- Runs generated Python simulation code, captures stdout/stderr, output paths, timing, and error details. Handles failures gracefully (capture and continue).

- Model: `sonnet`
- Tools: `Bash`, `Read`
- Factory: `create_executor_agent()`

### evaluator.py
**Evaluator Agent** -- Analyzes simulation outputs and computes quantitative metrics (PSNR, SSIM, MSE, etc.). Compares against ground truth when available. Can write and execute Python analysis scripts.

- Model: `sonnet`
- Tools: `Bash`, `Read`, `Glob`
- Factory: `create_evaluator_agent()`

### analyst.py
**Analyst Agent** -- Interprets evaluation metrics and experiment history. Decides whether evidence supports/contradicts the hypothesis and whether to continue or stop. Proposes specific follow-up experiments. Controls the iteration loop via `should_stop`.

- Model: `claude-opus-4-6` (deepest reasoning for result interpretation)
- Tools: `Read`, `Glob`
- Factory: `create_analyst_agent(analysis_context="")`
- Also exports: `format_nlos_analysis_context()` (deprecated, use `physics.context`)

### literature_validator.py
**Literature Validator** -- Post-analysis agent that checks experimental conclusions against published research. Identifies consistency, novelty, and methodological concerns. Produces a confidence adjustment (-0.3 to +0.3).

- Model: `claude-sonnet-4-20250514`
- Tools: `WebSearch`, `Read`
- Factory: `create_literature_validator_agent()`

### physics_advisor.py
**Physics Advisor** -- Dedicated physics consultation agent. Embeds a curated constants registry (NIST CODATA universal constants + computational imaging constants) directly in its prompt so it never recalls constants from training data. Provides guidance on governing equations, dimensionless groups, parameter plausibility, and numerical methods.

- Model: `sonnet`
- Tools: `Read`
- Factory: `create_physics_advisor_agent(domain_knowledge="")`
- Also exports: `format_nlos_advisor_context()` (deprecated, use `physics.context`)

## Key Patterns

- **Factory function pattern**: Every agent file exports a `create_*_agent()` function returning `AgentDefinition` (from `claude_agent_sdk.types`). The definition includes `description`, `prompt`, `tools`, and `model`.
- **Prompt template with placeholders**: Prompts use `{state_context}` (filled at query time by the runner), plus optional `{environment}`, `{physics_section}`, `{physics_context}`, or `{query_context}` (filled at construction time by the factory).
- **Strict JSON output contracts**: Every agent prompt specifies an exact JSON schema with `CRITICAL` formatting rules. The runner's `_unwrap_json()` normalizes deviations.
- **Optional physics injection**: Hypothesis, analyst, scene, and physics advisor agents accept optional physics/domain context strings that are injected into their prompts when a domain is detected.

## Model Selection Strategy

| Agent | Model | Rationale |
|-------|-------|-----------|
| Literature Scout | `claude-opus-4-6` | Deep reasoning for research synthesis |
| Citation Auditor | `claude-sonnet-4-20250514` | Systematic verification, cost-efficient |
| Hypothesis | `claude-sonnet-4-20250514` | Balance of reasoning and cost |
| Scene | `sonnet` | Code generation |
| Executor | `sonnet` | Code execution management |
| Evaluator | `sonnet` | Metric computation |
| Analyst | `claude-opus-4-6` | Deepest reasoning for interpretation |
| Literature Validator | `claude-sonnet-4-20250514` | Verification against literature |
| Physics Advisor | `sonnet` | Structured physics guidance |

## Dependencies

- **Depends on**: `claude_agent_sdk.types.AgentDefinition`, `agentsim.physics.domains.schema.DomainKnowledge`, `agentsim.physics.constants`
- **Depended on by**: `agentsim.orchestrator.agent_registry` (builds the full registry from these factories)
