---
phase: 05-mitsuba-3-transient-rendering-integration
plan: 01
subsystem: physics
tags: [mitsuba, mitransient, nlos, transient-rendering, pydantic, templates]

requires:
  - phase: 02.1-paradigm-agnostic-domain-architecture
    provides: NLOS domain YAML structure under nlos_transient_imaging/
provides:
  - NLOSSceneTemplate frozen base class with build() producing Mitsuba scene dicts
  - Three benchmark scene templates (confocal point, non-confocal mesh, retroreflective)
  - Template registry with get_template() and list_templates() API
  - Transient validation with OPL-to-time conversion and peak timing comparison
affects: [05-02, 05-03, scene-agent, executor-agent]

tech-stack:
  added: []
  patterns: [template-hierarchy-with-build, opl-time-conversion, scene-dict-without-mitsuba-import]

key-files:
  created:
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/__init__.py
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/base.py
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/confocal_point.py
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/nonconfocal_mesh.py
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/retroreflective.py
    - src/agentsim/physics/domains/nlos_transient_imaging/templates/validation.py
    - tests/unit/test_nlos_templates.py
    - tests/unit/test_transient_validation.py
  modified: []

key-decisions:
  - "Scene dicts use nested dict transforms (not mi.ScalarTransform4f) so templates work without mitsuba installed"
  - "Reflectance uses rgb dict value [1.0,1.0,1.0] for all surfaces (white diffuse)"
  - "auto_start_opl with 10% margin below minimum round-trip OPL for confocal scenes"

patterns-established:
  - "Template hierarchy: frozen Pydantic base with build() method, subclasses override _build_hidden_objects()"
  - "No mitsuba import at module level in template code -- scene dicts are plain Python dicts"
  - "OPL-to-time conversion pattern via SPEED_OF_LIGHT constant shared across modules"

requirements-completed: [MIT-01, MIT-02, MIT-03, MIT-04]

duration: 5min
completed: 2026-04-08
---

# Phase 05 Plan 01: NLOS Scene Templates Summary

**Frozen Pydantic template hierarchy producing Mitsuba scene dicts for three NLOS benchmark geometries, with OPL-to-time transient validation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T19:22:44Z
- **Completed:** 2026-04-08T19:27:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- NLOSSceneTemplate base class with build() producing complete Mitsuba scene dicts (integrator, relay wall, sensor, film)
- Three benchmark scene templates: ConfocalPointScene (sphere), NonConfocalMeshScene (.obj/.ply), RetroReflectiveScene (corner reflector)
- Template registry with get_template()/list_templates() public API
- Transient validation module with bidirectional OPL-time conversion and peak timing comparison
- 40 unit tests passing (28 template + 12 validation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Template base class, three scene-type templates, and __init__.py** - `4446e30` (feat)
2. **Task 2: Transient validation module** - `7e67ffe` (feat)

## Files Created/Modified
- `templates/base.py` - NLOSSceneTemplate frozen base class with build(), SPP_TIERS, SPEED_OF_LIGHT
- `templates/confocal_point.py` - ConfocalPointScene with hidden sphere and auto_start_opl
- `templates/nonconfocal_mesh.py` - NonConfocalMeshScene for .obj/.ply mesh loading
- `templates/retroreflective.py` - RetroReflectiveScene with corner reflector geometry
- `templates/__init__.py` - Registry with get_template() and list_templates()
- `templates/validation.py` - OPL-time conversion, peak timing extraction and comparison
- `tests/unit/test_nlos_templates.py` - 28 tests for template hierarchy and registry
- `tests/unit/test_transient_validation.py` - 12 tests for validation functions

## Decisions Made
- Scene dicts use nested dict transforms (not mi.ScalarTransform4f) so templates work without mitsuba installed
- Reflectance uses rgb dict value [1.0,1.0,1.0] for all surfaces (white diffuse)
- auto_start_opl with 10% margin below minimum round-trip OPL for confocal scenes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Template system ready for 05-02 (script generation) to use templates via get_template()
- Validation module ready for 05-03 (render integration) to validate transient outputs
- No blockers for subsequent plans

## Self-Check: PASSED

All 8 created files verified on disk. Both task commits (4446e30, 7e67ffe) found in git log.

---
*Phase: 05-mitsuba-3-transient-rendering-integration*
*Completed: 2026-04-08*
