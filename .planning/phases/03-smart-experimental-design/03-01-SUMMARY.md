---
phase: 03-smart-experimental-design
plan: 01
subsystem: experimental-design
tags: [doe, lhs, sobol, salib, pydantic, sampling]

requires:
  - phase: 01-physics-validation
    provides: Pydantic frozen model patterns and ParameterSpec from state models
provides:
  - DoE data models (ParameterBound, ParameterSpace, DoEStrategy, SampledDesign)
  - Automatic strategy selector (select_doe_strategy)
  - LHS, Sobol, and full factorial parameter samplers
  - ParameterSpace.from_hypothesis_params() bridge from existing ParameterSpec
affects: [03-smart-experimental-design, scene-generation]

tech-stack:
  added: [SALib]
  patterns: [nested-tuple-immutability, salib-problem-dict]

key-files:
  created:
    - src/agentsim/experimental_design/__init__.py
    - src/agentsim/experimental_design/models.py
    - src/agentsim/experimental_design/doe_selector.py
    - src/agentsim/experimental_design/lhs_sampler.py
    - tests/unit/test_doe_models.py
    - tests/unit/test_doe_sampler.py
  modified: []

key-decisions:
  - "Nested tuples for design_matrix immutability instead of numpy arrays"
  - "SALib for LHS and Sobol sampling (already a declared dependency)"
  - "Decision thresholds: factorial<=2D/50budget, Sobol>=5D, Bayesian>=10D/300budget"

patterns-established:
  - "Nested tuple immutability: design matrices stored as tuple[tuple[float, ...], ...] for Pydantic frozen models"
  - "SALib problem dict: _to_salib_problem() helper converts ParameterSpace to SALib format"

requirements-completed: [SEXP-01, SEXP-03]

duration: 3min
completed: 2026-04-08
---

# Phase 03 Plan 01: DoE Models, Strategy Selector & Samplers Summary

**Frozen Pydantic DoE models with automatic LHS/Sobol/factorial/Bayesian strategy selection and SALib-backed parameter samplers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-08T20:04:51Z
- **Completed:** 2026-04-08T20:08:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Complete experimental_design package with 5 frozen Pydantic models (ParameterBound, ParameterSpace, DoEStrategyType, DoEStrategy, SampledDesign)
- Automatic DoE strategy selector that picks the right sampling method based on dimensionality and budget thresholds
- Three parameter samplers (LHS, Sobol, full factorial) using SALib for real quasi-random sequences
- ParameterSpace.from_hypothesis_params() bridges existing ParameterSpec from hypothesis to DoE parameter space
- 38 unit tests passing covering all models, selector decision boundaries, and sampler output correctness

## Task Commits

Each task was committed atomically:

1. **Task 1: DoE data models** - `ef64aee` (feat)
2. **Task 2: DoE strategy selector and parameter samplers** - `c410e09` (feat)

## Files Created/Modified
- `src/agentsim/experimental_design/__init__.py` - Package init re-exporting public API
- `src/agentsim/experimental_design/models.py` - Frozen Pydantic models for DoE
- `src/agentsim/experimental_design/doe_selector.py` - Strategy selection logic with dimensionality/budget thresholds
- `src/agentsim/experimental_design/lhs_sampler.py` - LHS, Sobol, and full factorial samplers using SALib
- `tests/unit/test_doe_models.py` - 20 tests for models and properties
- `tests/unit/test_doe_sampler.py` - 18 tests for selector and samplers

## Decisions Made
- Used nested tuples (tuple[tuple[float, ...], ...]) for design_matrix to maintain Pydantic frozen model immutability while storing numeric matrices
- SALib used directly for LHS and Sobol sampling rather than hand-rolled implementations
- Strategy decision thresholds set at: factorial for 1-2D with <=50 budget, Sobol for >=5D, Bayesian for >=10D with >=300 budget, LHS as default

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed SALib dependency**
- **Found during:** Task 2 (sampler implementation)
- **Issue:** SALib not installed in venv despite being declared in pyproject.toml
- **Fix:** Installed via `uv pip install SALib`
- **Files modified:** None (runtime dependency only)
- **Verification:** All 38 tests pass with real SALib output
- **Committed in:** c410e09 (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** SALib installation was necessary for sampler functionality. No scope creep.

## Issues Encountered
None beyond the SALib installation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DoE models and samplers ready for sensitivity analysis (Plan 02) and convergence monitoring (Plan 03)
- SampledDesign.to_parameter_dicts() produces scene-ready parameter dictionaries for scene agent integration
- ParameterSpace.from_hypothesis_params() enables automatic conversion from existing hypothesis parameter specs

## Self-Check: PASSED

All 6 created files verified on disk. Both task commits (ef64aee, c410e09) found in git log.

---
*Phase: 03-smart-experimental-design*
*Completed: 2026-04-08*
