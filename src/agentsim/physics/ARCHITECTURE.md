# Physics Validation Layer

> Deterministic physics validation pipeline that checks simulation code and parameters for physical correctness before execution -- no LLM dependency.

## Files

### __init__.py
Package entry point. Re-exports the three public functions: `run_deterministic_checks`, `run_nlos_checks`, `run_paradigm_checks`.

### models.py
Frozen Pydantic models for the entire physics module. Shares a single `pint.UnitRegistry` instance (`_ureg`) to avoid the multi-registry pitfall. Key models:

- **Severity** -- Enum with ERROR, WARNING, INFO levels.
- **CheckResult** -- Single finding from a physics check (check name, severity, message, parameter, details).
- **ValidationReport** -- Aggregated results with pass/fail status and duration.
- **PhysicalConstant / PhysicalParameter** -- Named physical values with SI units. `PhysicalParameter` provides `to_quantity()` / `from_quantity()` for Pint interop.
- **ExtractedParameter / ExtractedSimulationParams / ASTExtractionResult** -- Models for AST-based code analysis output.
- **PhysicsQuery / PhysicsGuidance / ConsultationLogEntry** -- Models for physics advisor agent interactions.
- **PhysicsValidation / PhysicsConsultationSummary** -- State-level models embedded in `ExperimentState`.

### constants.py
Curated physical constants registry. Two dictionaries:

- **UNIVERSAL** -- NIST CODATA constants (speed of light, Boltzmann, Planck, etc.).
- **COMPUTATIONAL_IMAGING** -- Domain-specific constants (radiometry, wave optics, sensor models, reconstruction).

Also provides **PARAMETER_RANGES** for plausibility checking (min/max/unit per parameter per domain).

Public API: `lookup_constant(name)`, `get_parameter_range(name, domain)`, `list_domains()`, `list_constants(domain)`.

### checker.py
Orchestrates the 7-step deterministic validation pipeline in cost order:

1. Unit consistency (Pint) -- <1ms
2. Parameter range plausibility -- <10ms
3. AST parameter extraction -- <100ms
4. SymPy equation tracing -- <1s
5. CFL numerical stability -- <100ms
6. Mesh quality (trimesh) -- <5s
7. Paradigm-specific checks (dispatched from YAML or hardcoded NLOS fallback)

**Fail-fast**: stops at the first ERROR-level finding. WARNINGs and INFOs accumulate.

Also provides `run_nlos_checks()` for standalone NLOS geometry validation and `run_paradigm_checks()` for YAML-driven validation rule dispatch (supports `python_check` and `range_check` rule types).

### consultation.py
Physics advisor consultation helper. Handles:

- **Reasoning query routing** (`_route_reasoning_query`) -- Routes `optimize_setup`, `sensor_query`, `algorithm_query`, and `explore_novel` query types to deterministic computation in the reasoning engine, bypassing the LLM advisor.
- **Prompt building** -- Formats PhysicsQuery + state context into advisor prompts.
- **Response parsing** -- Extracts JSON from agent responses (direct parse, code fence, embedded JSON).
- **JSONL logging** -- Appends consultation entries to `physics_consultations.jsonl`.
- **Summary tracking** -- Maintains immutable `PhysicsConsultationSummary` with running counts.
- **Main function**: `consult_physics_advisor()` -- async function that queries the advisor agent and logs the interaction.

### context.py
Generic context formatters that render domain, paradigm, and sensor data into structured Markdown for agent prompts. Paradigm-agnostic -- no hardcoded domain branches. Public formatters:

- `format_physics_context()` -- Base formatter with equations, dimensionless groups, algorithms, paradigm, sensors.
- `format_hypothesis_context()` -- Wraps base with hypothesis-specific framing (no sensor catalog).
- `format_analysis_context()` -- Adds signal physics expectations, reconstruction quality checks, failure modes.
- `format_scene_context()` -- Full context including sensor classes, algorithms, hard constraints, and published baselines.
- `format_optimizer_recommendation()` -- Renders OptimizerResult as Markdown for scene agent.

## Data Flow

```
Simulation code + parameters
        |
        v
run_deterministic_checks()
  1. check_unit_consistency()        -- units.py
  2. check_parameter_ranges()        -- ranges.py
  3. extract_physics_from_ast()      -- ast_extract.py
  4. trace_dimensions_from_ast()     -- equations.py
  5. check_cfl_stability()           -- stability.py
  6. check_mesh_quality()            -- mesh_quality.py
  7. run_paradigm_checks()           -- checker.py (dispatches to YAML rules)
        |
        v
    ValidationReport (pass/fail + all findings)
```

## Key Patterns

- **Fail-fast pipeline**: Each step checks for ERROR before proceeding to the next.
- **Immutable models**: All Pydantic models use `frozen=True`.
- **Single UnitRegistry**: Shared `_ureg` in models.py avoids Pint compatibility issues.
- **Cost-ordered execution**: Cheapest checks run first to minimize wasted computation.
- **Dual-path paradigm checks**: YAML-driven dispatch when `paradigm_knowledge` is provided; hardcoded NLOS fallback for backward compatibility.

## Dependencies

- **Depends on**: `pint`, `sympy`, `numpy`, `trimesh` (optional), `structlog`, `pydantic`, `claude_agent_sdk` (consultation only).
- **Internal**: `physics.checks.*`, `physics.domains.*`, `physics.reasoning.*`.
- **Depended on by**: `orchestrator.runner` (runs checks during scene phase), agent prompt formatters, state transitions.
