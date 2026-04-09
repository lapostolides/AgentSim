---
phase: 10-pipeline-integration
plan: 03
subsystem: orchestrator
tags: [knowledge-graph, prompt-injection, crb, sensitivity, runner]

# Dependency graph
requires:
  - phase: 10-pipeline-integration
    plan: 01
    provides: format_hypothesis_graph_context, format_scene_graph_context, format_evaluator_graph_context, ExperimentState.feasibility_result
provides:
  - KG context injection in _run_hypothesis_phase (ranked sensors, CRB bounds, research gaps)
  - KG context injection in _run_scene_phase (Morris sensitivity rankings)
  - KG context injection in _run_evaluator_phase (CRB performance floor, efficiency ratio)
  - AnalysisReport.constraint_modifications field for re-query support
affects: [10-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy-import-in-phase-functions, prompt-level-kg-injection]

key-files:
  created: []
  modified:
    - src/agentsim/orchestrator/runner.py
    - src/agentsim/state/models.py

key-decisions:
  - "All graph_context imports are lazy (inside functions) to avoid import errors when knowledge_graph not installed"

patterns-established:
  - "Lazy import pattern: import inside phase function body, not at module top level"
  - "KG context appended to prompt string between guidance/feedback and state context sections"
  - "Sensitivity computation is best-effort with try/except around GraphClient usage"

requirements-completed: [PIPE-02, PIPE-05, PIPE-06]

# Metrics
duration: 2min
completed: 2026-04-09
---

# Phase 10 Plan 03: KG Agent Prompt Injection Summary

**Three agent prompts (hypothesis, scene, evaluator) enriched with tailored KG context at runtime plus AnalysisReport extended with constraint_modifications for re-query support**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T20:18:35Z
- **Completed:** 2026-04-09T20:20:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extended AnalysisReport with optional constraint_modifications field for analyst re-query (D-09)
- Injected KG context into hypothesis prompt (ranked sensors, CRB bounds, research gaps)
- Injected sensitivity-guided KG context into scene prompt with lazy Morris computation
- Injected CRB performance floor and efficiency ratio framing into evaluator prompt
- All three agents gracefully degrade to pre-Phase-10 behavior when feasibility_result is None

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend AnalysisReport with constraint_modifications field** - `6e8d370` (feat)
2. **Task 2: Inject KG context into hypothesis, scene, and evaluator prompts** - `0275535` (feat)

## Files Created/Modified
- `src/agentsim/state/models.py` - Added constraint_modifications: dict[str, float | str] | None to AnalysisReport
- `src/agentsim/orchestrator/runner.py` - KG context injection in _run_hypothesis_phase, _run_scene_phase, _run_evaluator_phase

## Decisions Made
- All graph_context imports are lazy (inside function bodies) to avoid import errors when knowledge_graph package is not installed -- consistent with existing lazy import patterns in runner.py (e.g., preview module)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three agent prompts now receive KG context when feasibility_result exists
- AnalysisReport.constraint_modifications ready for Plan 04's analyst re-query loop
- format_analyst_graph_context (from Plan 01) available for Plan 04's analyst injection

---
*Phase: 10-pipeline-integration*
*Completed: 2026-04-09*
