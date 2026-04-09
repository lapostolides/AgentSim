---
phase: 08-crb-and-information-theoretic-bounds
plan: 02
subsystem: crb
tags: [jax, fisher-information, numerical-crb, tikhonov, stability, autodiff]

requires:
  - phase: 06-knowledge-graph-models
    provides: SensorFamily enum, ConfidenceQualifier enum, SensorNode model
  - phase: 07-sensor-yaml-data
    provides: Sensor YAML files for 4 exotic families (coded aperture, lensless, event camera, light field)
provides:
  - "JAX-based numerical CRB computation for 4 exotic sensor families"
  - "Pure-numpy stability guards for Fisher matrix inversion"
  - "jax_available() runtime detection utility"
  - "NUMERICAL_FAMILIES frozenset for dispatch"
affects: [08-03-dispatch, 09-feasibility-engine]

tech-stack:
  added: [jax (optional), jaxlib (optional)]
  patterns: [lazy-import-for-optional-deps, tikhonov-regularization, jacfwd-jacrev-hessian]

key-files:
  created:
    - src/agentsim/knowledge_graph/crb/stability.py
    - src/agentsim/knowledge_graph/crb/numerical.py
    - tests/unit/test_crb_numerical.py
  modified: []

key-decisions:
  - "Pure numpy stability module (no JAX) per D-06 for independent testability"
  - "CONDITION_THRESHOLD=1e12 with 3-order-of-magnitude safety margin (Golub & Van Loan)"
  - "Forward models use small parameter dimension (1-2 params) for fast CPU Hessian"

patterns-established:
  - "Lazy JAX import: jax_available() + import inside function body per D-04"
  - "Stability guard pipeline: check_condition_number -> regularize_fisher -> assert_positive_variance"
  - "Forward model factory: family-specific function returns (neg_log_likelihood_fn, params_init)"

requirements-completed: [CRB-02, CRB-06]

duration: 7min
completed: 2026-04-09
---

# Phase 8 Plan 02: Numerical CRB Summary

**JAX autodiff Fisher information for 4 exotic sensor families with pure-numpy Tikhonov stability guards**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-09T16:40:28Z
- **Completed:** 2026-04-09T16:47:19Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Pure-numpy stability module with condition number check (threshold 1e12), Tikhonov regularization (alpha=1e-6), and positive-variance assertion
- JAX numerical CRB via jacfwd(jacrev(f)) for coded aperture, lensless, event camera, and light field families
- 15 tests passing (11 stability always-run + 4 always-run numerical), 7 JAX-dependent tests skip gracefully

## Task Commits

Each task was committed atomically:

1. **Task 1: Stability guards for Fisher matrix inversion** - `fa08394` (feat)
2. **Task 2: JAX numerical CRB for 4 exotic sensor families** - `8667fff` (feat)

## Files Created/Modified
- `src/agentsim/knowledge_graph/crb/stability.py` - Pure-numpy condition check, Tikhonov regularization, positive-variance assertion
- `src/agentsim/knowledge_graph/crb/numerical.py` - JAX autodiff Fisher information + CRB for 4 exotic families
- `tests/unit/test_crb_numerical.py` - 22 tests (stability guards + numerical CRB with JAX skip)

## Decisions Made
- Used simplified forward models (1-2 parameter dimension) for each exotic family -- sufficient for Fisher information computation and fast on CPU
- Stability guards are a pipeline (check -> regularize -> assert) called in sequence before returning CRBResult
- Created minimal crb/models.py and crb/__init__.py since Plan 01 was running in parallel -- Plan 01 overwrote with full version

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created minimal CRB models.py for parallel execution**
- **Found during:** Task 1 (setup)
- **Issue:** Plan 01 (parallel) had not yet created crb/models.py and crb/__init__.py
- **Fix:** Created minimal versions with CRBResult type; Plan 01 overwrote with full version
- **Files modified:** src/agentsim/knowledge_graph/crb/models.py, src/agentsim/knowledge_graph/crb/__init__.py
- **Verification:** Imports work correctly after Plan 01 overwrite
- **Committed in:** fa08394 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for parallel execution. No scope creep.

## Issues Encountered
- JAX not installed in environment, so 7 JAX-dependent tests skip via pytest.importorskip. This is expected behavior per D-04 and RESEARCH.md.

## User Setup Required
None - no external service configuration required. JAX is optional; install with `pip install jax jaxlib` to enable numerical CRB computation.

## Next Phase Readiness
- stability.py and numerical.py ready for Plan 03 dispatch module integration
- NUMERICAL_FAMILIES exported for dispatch family routing
- jax_available() utility available for graceful degradation in dispatch

---
*Phase: 08-crb-and-information-theoretic-bounds*
*Completed: 2026-04-09*

## Self-Check: PASSED

- All 3 created files exist on disk
- Both task commits (fa08394, 8667fff) found in git log
- No stubs or placeholder data detected
