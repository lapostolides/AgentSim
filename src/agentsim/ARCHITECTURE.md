# agentsim

> Top-level package for AgentSim: a multi-agent autonomous hypothesis-driven simulation system for computational science research.

## Files

### __init__.py
Empty. All imports are explicit from subpackages.

### main.py
CLI entrypoint using Click. Defines the `agentsim` console script with two commands:

- **`agentsim run <hypothesis>`** -- Single-shot experiment execution. Accepts files (`-f`), output dir (`-o`), iteration limit (`-n`), budget (`-b`), and gate selection (`-g`). Runs the full pipeline via `run_experiment()` and prints a summary or JSON output.
- **`agentsim interactive`** -- REPL loop that prompts for hypotheses and optional files, running one iteration per input with live phase status.

Both commands share setup logic: `.env` loading (`_load_env`), authentication validation (`_validate_auth` checks for `ANTHROPIC_API_KEY` or OAuth credentials), gate resolution (`_resolve_checkpoints`), and `OrchestratorConfig` assembly.

Key exports: `cli` (Click group, also the `__main__` entrypoint).

## High-Level Data Flow

```
User hypothesis (natural language)
    |
    v
Literature Scout  -->  Citation Auditor
    |
    v
Hypothesis Agent  (formalize, refine, rate quality)
    |
    v
[Pre-scene Physics Optimization -- if domain detected]
    |
    v
Scene Agent  (generate Python simulation code)
    |
    v
Physics Validation  (deterministic checks + advisor fallback)
    |
    v
[Paradigm Auto-Fix loop -- if paradigm detected]
    |
    v
Executor  (run simulation code, capture outputs)
    |
    v
Evaluator  (compute metrics, compare to ground truth)
    |
    v
Analyst  (interpret results, decide continue/stop)
    |
    v
Literature Validator  (check findings against published work)
    |
    v
Loop back to Hypothesis if analyst says should_stop=false
```

Human intervention gates can pause execution at six checkpoints throughout this pipeline.

## Subpackages

- **agents/** -- Agent definitions (prompt templates + factory functions). One file per agent role.
- **orchestrator/** -- Pipeline orchestration: iteration loop, gate system, agent registry, configuration.
- **state/** -- Frozen Pydantic models, pure transition functions, serialization. The `ExperimentState` envelope flows through the entire pipeline.
- **physics/** -- Physics-aware validation layer: deterministic checks, constants registry, domain knowledge, LLM consultation, reasoning engine. *(Documented separately.)*
- **environment/** -- Runtime discovery of available Python packages (numpy, mitsuba, etc.) for agent prompts.
- **cli/** -- Terminal UI for intervention gates (`CliInterventionHandler`).
- **utils/** -- File handling, logging configuration.

## Key Patterns

- **Immutable state envelope**: `ExperimentState` is a frozen Pydantic model. Every phase produces a new instance via `model_copy(update={...})`.
- **Serialized handoff**: State is serialized to JSON between phases. Each agent receives it as prompt context via `state_to_prompt_context()`, keeping context windows clean.
- **Factory-based agents**: Each agent is an `AgentDefinition` built by a factory function. The registry wires them together with environment and domain context.
- **Budget partitioning**: Each agent phase gets `max_budget_usd / 5` of the total budget.

## Dependencies

- **External**: `click`, `structlog`, `python-dotenv`, `pydantic`, `claude-agent-sdk`
- **Internal**: All subpackages depend on `state.models`. The `orchestrator` depends on `agents`, `state`, `physics`, and `environment`.
