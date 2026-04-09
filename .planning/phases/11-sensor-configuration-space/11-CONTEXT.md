# Phase 11: Sensor Configuration Space - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds configurable parameter optimization to the sensor feasibility pipeline. Each sensor's parameter ranges (already defined in YAMLs from Phase 7) become inputs to a Bayesian optimizer that finds Pareto-optimal operating points. The feasibility engine ranks sensors that CAN reach a target via parameter tuning, considering CRB performance, operational cost, and constraint margin. Experiment scoping (wide/medium/narrow) controls how many Pareto-optimal configs are surfaced to agents.

**NOT in scope:** Task-dependent parameter coupling (e.g., "tracking needs high frame rate so longer integration time is bad") — deferred to Phase 12 when structured Task nodes provide automatic task preferences.

</domain>

<decisions>
## Implementation Decisions

### CRB Optimization Strategy
- **D-01:** Bayesian optimization (GP surrogate + acquisition function) searches each sensor's parameter space for Pareto-optimal operating points.
- **D-02:** Adaptive budget — BO runs until GP acquisition function improvement drops below a convergence threshold, with a hard cap as safety. Analytical CRB families converge fast (sub-second per eval); JAX numerical families may take longer.
- **D-03:** 3-axis Pareto front: (1) CRB bound (minimize), (2) operational cost (minimize), (3) constraint margin (maximize). Constraint satisfaction is ALSO a hard filter — infeasible points excluded before Pareto ranking.
- **D-04:** Operational cost = weighted sum of USD cost, power consumption, and weight. Weights are user-configurable with sensible defaults (e.g., 0.5 USD + 0.3 power + 0.2 weight). Each dimension normalized 0-1 within the sensor family's parameter range.
- **D-05:** Pareto front is uncapped — return all non-dominated points. Analyst agent receives the full front and uses discretion to highlight the most interesting tradeoffs. Graph context formatters may summarize for other agents.

### Experiment Scoping Model
- **D-06:** Wide/medium/narrow = Pareto front resolution post-filter. Wide: full Pareto front across all families. Medium: top-5 configs per family. Narrow: single best config per family. Scoping does NOT affect BO computation — it filters results after optimization.
- **D-07:** User selects scope via CLI flag `--scope wide|medium|narrow` (default: medium). Auto-detect fallback: if no flag, infer from hypothesis specificity — vague hypotheses get wide, sensor-specific hypotheses get narrow.
- **D-08:** Scope level stored in ExperimentState so agents know the exploration depth and adjust prompts accordingly.

### Configurability as Ranking Signal
- **D-09:** Cost on the Pareto front = real operational cost from sensor metadata (PHYS-05: cost_range_usd, power_w, weight_g). NOT distance-from-default — defaults are "typical" values with no inherent superiority.
- **D-10:** A sensor that needs parameter tuning to satisfy constraints is not penalized for tuning itself — only for the real-world cost of the resulting configuration. Extreme parameter values are penalized only if they map to more expensive/power-hungry physical sensors.

### Pipeline Integration
- **D-11:** New `_run_optimization_phase` runs AFTER `_run_feasibility_phase` in the pipeline. Feasibility does fast constraint filtering; optimization does expensive Pareto search on surviving sensors. Clean separation of concerns.
- **D-12:** New `OptimizationResult` model in ExperimentState (frozen Pydantic), separate from FeasibilityResult. Contains Pareto-optimal configs per family, BO metadata (evaluations, convergence status), and scope level.
- **D-13:** Graph context formatters updated to include Pareto front information alongside (not replacing) feasibility rankings. Analyst gets full Pareto details; other agents get scope-filtered summaries.

### Task-Dependent Coupling (DEFERRED)
- **D-14:** Task-dependent parameter coupling (e.g., integration time improves CRB but degrades frame rate for tracking) is deferred to Phase 12. Phase 12's domain taxonomy will provide structured Task nodes that automatically generate task preferences.
- **D-15:** Phase 11 optimizer works with CRB + operational cost + constraint margin only. No task fitness scoring in this phase.

### Claude's Discretion
- Specific BO library choice (scipy.optimize, botorch, or custom GP implementation)
- Convergence threshold for adaptive budget
- Default operational cost weights (must be configurable)
- How to normalize parameter ranges for BO (log-scale for parameters spanning orders of magnitude?)
- Exact format of Pareto front in agent prompt context sections
- How auto-detect infers scope from hypothesis text (heuristic design)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Parameter Ranges (Phase 7)
- `src/agentsim/knowledge_graph/ranges.py` — ParameterRange and SensorFamilyRanges models
- `src/agentsim/knowledge_graph/loader.py` — `load_family_ranges()` loads from YAML
- `src/agentsim/knowledge_graph/sensors/*.yaml` — All 11 sensor YAMLs with `ranges:` sections

### CRB Computation (Phase 8)
- `src/agentsim/knowledge_graph/crb/dispatch.py` — `compute_crb()` dispatch per family
- `src/agentsim/knowledge_graph/crb/sensitivity.py` — Morris method sensitivity analysis
- `src/agentsim/knowledge_graph/crb/models.py` — CRBResult, SensitivityResult models

### Feasibility Engine (Phase 9)
- `src/agentsim/knowledge_graph/query_engine.py` — FeasibilityQueryEngine, SensorConfig ranking
- `src/agentsim/knowledge_graph/constraint_checker.py` — Constraint satisfaction logic
- `src/agentsim/knowledge_graph/models.py` — FeasibilityResult, SensorConfig, ConstraintSatisfaction

### Pipeline Integration (Phase 10)
- `src/agentsim/orchestrator/runner.py` — `_run_feasibility_phase()`, `run_experiment()` main loop
- `src/agentsim/state/models.py` — ExperimentState with feasibility_result field
- `src/agentsim/state/graph_context.py` — Per-agent KG context formatters
- `src/agentsim/state/transitions.py` — State transition functions (immutable pattern)

### Operational Metadata
- `src/agentsim/knowledge_graph/sensors/*.yaml` — PHYS-05 fields: cost_range_usd, power_w, weight_g per sensor profile

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ranges.py`: `ParameterRange(min, max, typical, unit)` and `SensorFamilyRanges(family, ranges)` — direct inputs to BO bounds
- `loader.py`: `load_family_ranges()` — loads ranges from YAML, returns SensorFamilyRanges per family
- `crb/dispatch.py`: `compute_crb(sensor, task)` — the objective function to minimize (call per BO evaluation)
- `constraint_checker.py`: Constraint satisfaction logic with margin calculation — reuse for constraint margin Pareto axis
- `query_engine.py`: FeasibilityQueryEngine — feasibility phase filters before optimization

### Established Patterns
- Frozen Pydantic models for all results (BO results must follow same pattern)
- Lazy imports in runner.py for optional dependencies (BO library should follow same pattern)
- Structlog for all phase logging
- `_run_*_phase()` pattern in runner.py for pipeline phases

### Integration Points
- New `_run_optimization_phase()` in runner.py after `_run_feasibility_phase()`
- New `OptimizationResult` model in state/models.py
- New `set_optimization_result()` transition in state/transitions.py
- Updated graph context formatters in state/graph_context.py for Pareto front display
- CLI flag `--scope` added to `agentsim run` command

</code_context>

<specifics>
## Specific Ideas

- User emphasized that "defaults don't hold significant value" — operational cost is what matters, not distance from typical values.
- User wants the analyst to receive the full uncapped Pareto front and use discretion to highlight interesting tradeoffs — consistent with Phase 10's D-07 (no hardcoded thresholds, agent discretion).
- Task-dependent parameter coupling (integration time vs frame rate for tracking) was explicitly discussed and deferred to Phase 12's domain taxonomy. Phase 11 should NOT attempt task fitness scoring.
- Adaptive BO budget was specifically requested over fixed evaluation counts — the optimizer should converge naturally rather than burn a fixed budget.

</specifics>

<deferred>
## Deferred Ideas

- Task-dependent parameter coupling → Phase 12 (Task-Aware Parameter Coupling: structured Task nodes with automatic parameter preferences)
- Natural language constraint parsing → future phase
- Multi-sensor fusion configurations → future phase

</deferred>

---

*Phase: 11-sensor-configuration-space*
*Context gathered: 2026-04-09*
