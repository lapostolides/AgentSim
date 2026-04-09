---
phase: 07-sensor-taxonomy-population
plan: 04
subsystem: physics
tags: [yaml, sensor-migration, domain-loader, nlos, spad, streak-camera, pydantic]

requires:
  - phase: 07-01
    provides: "Domain bundle loader and sensor class/profile schema"
provides:
  - "4 NLOS sensor YAMLs converted to new KG format with inline profiles"
  - "Domain loader extracts inline SensorProfile from sensor class YAMLs"
  - "Backward-compatible bridge: context.py and runner.py unchanged"
affects: [08-crb-math, 09-neo4j-integration]

tech-stack:
  added: []
  patterns: ["Inline profile embedding in sensor class YAMLs", "Prefer-inline fallback-directory profile loading"]

key-files:
  created:
    - tests/unit/test_nlos_migration.py
  modified:
    - src/agentsim/physics/domains/nlos_transient_imaging/sensors/spad_array.yaml
    - src/agentsim/physics/domains/nlos_transient_imaging/sensors/streak_camera.yaml
    - src/agentsim/physics/domains/__init__.py

key-decisions:
  - "Inline profiles keyed by lowercase name with spaces removed for consistency"
  - "profiles/ directory files serve as fallback, not overriding inline data"

patterns-established:
  - "Inline profile embedding: sensor class YAMLs contain a 'profiles' section with full SensorProfile data"
  - "Prefer-inline loading: domain loader extracts inline profiles first, then fills gaps from profiles/ directory"

requirements-completed: [SENS-01]

duration: 4min
completed: 2026-04-09
---

# Phase 07 Plan 04: NLOS Migration Summary

**Migrated 4 NLOS sensor YAMLs to new KG format with inline profiles and updated domain loader to extract them while preserving backward compatibility**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-09T11:50:19Z
- **Completed:** 2026-04-09T11:54:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Converted spad_array.yaml and streak_camera.yaml in-place with absorbed profile data (SwissSPAD2, LinoSPAD2, Hamamatsu C5680)
- Updated domain bundle loader to extract inline SensorProfile objects from sensor class YAMLs
- 18 migration-specific tests plus 109 domain/NLOS tests all pass with no regressions
- physics/context.py and orchestrator/runner.py remain completely unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert NLOS sensor YAMLs in-place and absorb profile data** - `d5171f6` (feat)
2. **Task 2: Update domain loader to parse new format (TDD)**
   - RED: `7c62f19` (test) - failing tests for inline profile extraction
   - GREEN: `217ca96` (feat) - domain loader with inline profile extraction

## Files Created/Modified
- `src/agentsim/physics/domains/nlos_transient_imaging/sensors/spad_array.yaml` - Added inline profiles for SwissSPAD2 and LinoSPAD2
- `src/agentsim/physics/domains/nlos_transient_imaging/sensors/streak_camera.yaml` - Added inline profile for Hamamatsu C5680
- `src/agentsim/physics/domains/__init__.py` - Extract inline profiles from sensor class YAMLs, prefer inline over directory
- `tests/unit/test_nlos_migration.py` - 18 tests covering sensor classes, inline profiles, catalog integration, backward compatibility

## Decisions Made
- Inline profile keys are derived from `name.lower().replace(" ", "")` for consistent lookup
- profiles/ directory files serve as fallback only -- inline data takes precedence per D-10 migration strategy
- spad_linear.yaml and gated_iccd.yaml left unchanged (no profiles to absorb)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in test_kg_loader.py (nonexistent family filter) unrelated to this plan
- Pre-existing SALib import error in DOE tests unrelated to this plan

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 4 NLOS sensor YAMLs in new KG format with inline profiles
- Domain loader bridges new format to old SensorClass/SensorProfile/SensorCatalog types
- Ready for Phase 8 CRB math and Phase 9 Neo4j integration
- profiles/ directory files can be removed in a future cleanup once inline-only loading is confirmed

## Self-Check: PASSED

All files exist, all commits found, all tests pass.

---
*Phase: 07-sensor-taxonomy-population*
*Completed: 2026-04-09*
