---
phase: 10-pipeline-integration
plan: 04
subsystem: orchestrator
tags: [knowledge-graph, analyst, re-query, crb, sensitivity, shares-physics]

# Dependency graph
requires:
  - phase: 10-pipeline-integration
    plan: 01
    provides: format_analyst_graph_context, ExperimentState.feasibility_result
  - phase: 10-pipeline-integration
    plan: 02
    provides: _run_feasibility_phase with constraint_overrides parameter
  - phase: 10-pipeline-integration
    plan: 03
    provides: AnalysisReport.constraint_modifications field
provides:
  - KG context injection in _run_analyst_phase (CRB, sensitivity, SHARES_PHYSICS, re-query instructions)
  - Re-query detection loop in run_experiment (analyst constraint_modifications triggers fresh feasibility query)
  - Re-query cap at 2 per experiment (prevents infinite loops)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [analyst-requery-loop, kg-context-in-analyst-prompt]

key-files:
  created:
    - tests/unit/test_analyst_requery.py
  modified:
    - src/agentsim/orchestrator/runner.py

key-decisions:
  - "All graph_context imports lazy inside phase functions to avoid import errors when knowledge_graph not installed"

patterns-established:
  - "Re-query detection pattern: check latest analysis for constraint_modifications, cap at max_requery"
  - "Analyst is most KG-aware agent -- receives full context including SHARES_PHYSICS neighbors and re-query instructions"

requirements-completed: [PIPE-07, PIPE-08]

# Metrics
duration: 3min
completed: 2026-04-09
---

# Phase 10 Plan 04: Analyst KG Context and Re-Query Loop Summary

**Analyst agent wired with full KG context (CRB, sensitivity, SHARES_PHYSICS, iteration trends) plus re-query loop that re-runs feasibility when analyst recommends constraint modifications**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-09T20:22:48Z
- **Completed:** 2026-04-09T20:26:00Z
- **Tasks:** 1 (TDD)
- **Files modified:** 2

## Accomplishments
- Analyst receives comprehensive KG context when feasibility_result exists (CRB efficiency, SHARES_PHYSICS neighbors, iteration trend, re-query instructions)
- Re-query detection in main experiment loop triggers _run_feasibility_phase when analyst outputs constraint_modifications
- Re-query capped at 2 per experiment to prevent infinite loops (Research Pitfall 4)
- constraint_modifications added to _unwrap_json expected keys for proper JSON extraction
- 6 tests covering KG context injection, re-query trigger, cap, no-trigger, and constraint passthrough

## Task Commits

Each task was committed atomically:

1. **Task 1: Inject KG context into analyst prompt and add re-query detection** - `b712936` (test, TDD RED) + `c6c6642` (feat, TDD GREEN)

## Files Created/Modified
- `src/agentsim/orchestrator/runner.py` - KG context in _run_analyst_phase, re-query detection in main loop, constraint_modifications in _unwrap_json keys
- `tests/unit/test_analyst_requery.py` - 6 tests for analyst re-query behavior (NEW)

## Decisions Made
- All graph_context imports are lazy (inside function bodies) to avoid import errors when knowledge_graph package is not installed -- consistent with Plans 02 and 03

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All four agent prompts now receive KG context (hypothesis, scene, evaluator, analyst)
- Analyst re-query loop enables iterative feasibility refinement
- Phase 10 pipeline integration is complete -- all agents are KG-aware

---
## Self-Check: PASSED

All files exist. All commits verified.

*Phase: 10-pipeline-integration*
*Completed: 2026-04-09*
