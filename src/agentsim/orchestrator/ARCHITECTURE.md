# orchestrator

> Coordinates the experiment pipeline: sequences agent phases, manages the iteration loop, enforces intervention gates, and handles state transitions.

## Files

### __init__.py
Exports `OrchestratorConfig` and `run_experiment`.

### config.py
Frozen Pydantic model `OrchestratorConfig` with all pipeline settings:

- `max_iterations` (default 5) -- iteration loop cap
- `max_budget_usd` (default 10.0) -- total budget, divided by 5 per phase
- `max_turns_per_phase` (default 15) -- agent conversation turn limit
- `output_dir` -- where state JSON is saved
- `save_intermediate_state` (default True)
- `extra_packages` -- additional packages to probe during environment discovery
- `permission_mode` (default "acceptEdits") -- file operation auto-approval
- `cwd` -- working directory for simulation execution
- `intervention_checkpoints` -- frozenset of enabled gate names (all by default)
- `max_scene_feedback_rounds` (default 5) -- feedback loop cap for scene visualization

### gates.py
Intervention gate types for human-in-the-loop experiment steering.

- **`GateAction`** enum: `APPROVE`, `EDIT`, `REDO`, `ABORT`, `FEEDBACK`
- **`GateCheckpoint`** enum: `PRE_HYPOTHESIS`, `POST_HYPOTHESIS`, `PRE_EXECUTION`, `SCENE_VISUALIZATION`, `POST_PHYSICS_VALIDATION`, `POST_EXECUTION`
- **`GateContext`** (frozen): data passed to a handler -- checkpoint, state, phase names, message, preview paths
- **`GateDecision`** (frozen): user's response -- action, optional updated state, feedback text, reason
- **`InterventionHandler`** protocol: async `handle_gate(context) -> GateDecision`. Implementations live in `cli/gates.py` (terminal UI) or could be a web UI.
- **`ALL_CHECKPOINTS`**: frozenset of all checkpoint values, used as the default.

### agent_registry.py
Builds the complete agent registry dictionary.

- **`build_agent_registry(environment, domain_context)`** -- Calls each agent factory function, wiring in the environment string and optional domain-specific context strings keyed by role (`"hypothesis"`, `"analyst"`, `"advisor"`, `"scene"`). Returns `dict[str, AgentDefinition]` with nine agents.
- **`get_agent_names()`** -- Returns the canonical ordered list of agent phase names.

### runner.py
The core experiment loop (largest file, ~1000+ lines). Key sections:

**Entry point**: `run_experiment()` -- async function that orchestrates everything:
1. Initialize state via `start_experiment()`
2. Discover environment (available Python packages)
3. Detect physics domain and paradigm, load domain knowledge, build context strings
4. Build agent registry with `build_agent_registry()`
5. Run literature scout + citation audit (once, before the loop)
6. Enter iteration loop (up to `max_iterations`):
   - Gate 1: Pre-hypothesis
   - Hypothesis phase (with redo loop on user feedback)
   - Pre-scene physics optimization (if domain/paradigm detected)
   - Scene generation (with feedback loop, up to `max_scene_feedback_rounds`)
   - Gates 3-4: Pre-execution + scene visualization
   - Physics validation (deterministic checks + LLM fallback)
   - Gate: Post-physics validation
   - Paradigm auto-fix loop (if paradigm detected)
   - Execution, evaluation, analysis, literature validation
   - Gate 5: Post-execution
   - Break if analyst sets `should_stop=true` or status is COMPLETED
7. Save final state JSON

**Phase runners**: Private async functions `_run_*_phase()` for each agent. Each:
1. Builds a prompt with `state_to_prompt_context(state)`
2. Calls `_run_agent_phase()` which creates `ClaudeAgentOptions` and streams `query()`
3. Extracts JSON from agent response via `_extract_json_from_text()`
4. Normalizes JSON via `_unwrap_json()` and field-specific coercion
5. Validates and constructs Pydantic models
6. Applies state transition function

**JSON normalization layer**: Handles the reality that agents return wildly different JSON shapes:
- `_unwrap_json()` -- Unwraps single-key nesting, applies `_FIELD_ALIASES` mapping
- `_extract_literature_entries()` -- Deep-searches for paper entries across variant structures (thematic clusters, nested dicts, different key names)
- `_coerce_to_str_list()` -- Flattens dicts, lists of dicts, or bare strings into `list[str]`
- `_FIELD_ALIASES` dict -- Maps common variant field names to canonical names (e.g., `"statement"` -> `"raw_text"`)

**Physics integration**:
- `_run_physics_validation_phase()` -- Runs deterministic checks on each scene, with LLM fallback for unknown parameters
- `_run_paradigm_autofix_loop()` -- Iteratively validates scenes against paradigm constraints, consulting the physics advisor for fix guidance and re-running the scene agent
- `_run_nlos_autofix_loop()` -- Deprecated wrapper for relay_wall paradigm
- NLOS parameter extraction helpers: `_extract_nlos_scene_params()`, `_extract_scene_params()`

**Gate helpers**: `_run_gate()` fires a gate if handler and checkpoint are enabled; `_is_abort()` checks for abort decisions.

## Data Flow

```
run_experiment()
  |
  +-- start_experiment() --> ExperimentState
  +-- discover_environment() --> EnvironmentInfo --> set_environment()
  +-- detect_domain() --> domain_context dict
  +-- build_agent_registry() --> dict[str, AgentDefinition]
  |
  +-- _run_literature_scout_phase() --> set_literature_context()
  +-- _run_citation_audit_phase() --> update verification_status on entries
  |
  +-- [iteration loop]
  |     +-- _run_gate(PRE_HYPOTHESIS)
  |     +-- _run_hypothesis_phase() --> add_hypothesis()
  |     +-- _run_gate(POST_HYPOTHESIS)
  |     +-- [optional] optimize_setup() --> set_physics_recommendation()
  |     +-- _run_scene_phase() --> add_scenes()
  |     +-- _run_preview_phase() --> add_scene_preview()
  |     +-- _run_gate(PRE_EXECUTION, SCENE_VISUALIZATION)
  |     +-- _run_physics_validation_phase() --> add_physics_validation()
  |     +-- _run_gate(POST_PHYSICS_VALIDATION)
  |     +-- [optional] _run_paradigm_autofix_loop()
  |     +-- _run_executor_phase() --> add_execution_result()
  |     +-- _run_gate(POST_EXECUTION)
  |     +-- _run_evaluator_phase() --> add_evaluation()
  |     +-- _run_analyst_phase() --> add_analysis()
  |     +-- _run_literature_validator_phase() --> set_literature_validation()
  |     +-- break if should_stop or COMPLETED
  |
  +-- _save_state() --> final_state.json
```

## Key Patterns

- **Serialized handoff**: State is serialized to JSON between every phase via `state_to_prompt_context()`. Each agent gets a fresh context window.
- **Budget partitioning**: `max_budget_usd / 5` per phase call.
- **Defensive JSON parsing**: Three strategies (direct parse, code fence extraction, embedded JSON extraction) before giving up.
- **Error recovery**: Outer try/except with retry counter (up to 2 retries per iteration).
- **Gate protocol**: Gates are optional (skipped if no handler or checkpoint disabled). `EDIT` replaces state, `REDO` loops back with feedback, `ABORT` marks failed.

## Dependencies

- **Depends on**: `agents/` (all factory functions), `state/` (models, transitions, serialization), `physics/` (validation, consultation, domains, reasoning), `environment/` (discovery), `claude_agent_sdk` (query, types)
- **Depended on by**: `main.py` (CLI entrypoint)
