# Phase 11: Sensor Configuration Space - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-09
**Phase:** 11-sensor-configuration-space

## Areas Discussed

### 1. CRB Optimization Strategy

**Q: What optimization approach for finding best operating points?**
Options: Grid + refinement (Recommended), Bayesian optimization, Exhaustive grid only
**Selected:** Bayesian optimization

**Q: What should the optimizer's objective function minimize?**
Options: Minimize CRB bound (Recommended), Maximize feasibility score, Multi-objective Pareto front
**Selected:** Multi-objective Pareto front

**Q: Budget for BO evaluations?**
Options: 50 evaluations, 100 evaluations, User-configurable with default 50
**Selected:** Other — "Can this be adaptive?" → Captured as adaptive budget (converge-or-cap)

**Q: Which objectives on the Pareto front?**
Options: CRB + cost, CRB + cost + constraint margin, CRB only with cost constraint
**Selected:** CRB bound + cost + constraint margin (3-axis Pareto)

### 2. Experiment Scoping Model

**Q: What do wide/medium/narrow mean concretely?**
Options: Controls Pareto front resolution (Recommended), Controls BO search depth, Controls family breadth
**Selected:** Controls Pareto front resolution (post-filter)

**Q: How does user select scope?**
Options: CLI flag, Auto-detect, Both with fallback
**Selected:** Both: flag with auto-detect fallback

### 3. Configurability as Ranking Signal

**Q: How should tunability affect ranking?**
Options: Distance-weighted boost, Binary feasible/not, Pareto handles it naturally
**Selected:** Other — User clarified that cost axis = operational cost (USD/power/weight), NOT distance from defaults. Defaults hold no special value.

### 4. Pipeline Interaction

**Q: Where does optimizer run?**
Options: Inside feasibility phase, New optimization phase (Recommended), Lazy on-demand
**Selected:** New _run_optimization_phase after feasibility

**Q: How do optimized configs flow to agents?**
Options: Extend FeasibilityResult, New OptimizationResult, Replace ranked_configs
**Selected:** New OptimizationResult in ExperimentState

## Revisited Areas

### CRB Optimization — Pareto Front Details

**Q: How to composite operational cost?**
Options: Weighted sum configurable, Separate Pareto axes, User selects dimensions
**Selected:** Weighted sum with user-configurable weights

**Q: How many Pareto configs to return?**
Options: Up to 10 per family, Scope-dependent, Uncapped
**Selected:** Uncapped, let analyst summarize

### Task-Dependent Parameter Coupling (Extended Discussion)

User raised: "A SPAD with longer integration time has better CRB but worse frame rate for tracking. How is this handled?"

**Q: How should task-dependent coupling affect optimization?**
Options: 4th Pareto axis (task fitness), Encode in constraints, Defer to Phase 12
User asked for recommendation → Hybrid approach presented (Phase 11 hook, Phase 12 auto-generates)
**Selected:** Defer entirely to Phase 12

---

*Session ended: 2026-04-09*
