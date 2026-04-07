---
phase: 02-computational-imaging-domain-intelligence
plan: 02
subsystem: physics
tags: [nlos, geometry-validation, three-bounce, sensor-fov, temporal-resolution, checker-pipeline]

requires:
  - phase: 02-computational-imaging-domain-intelligence
    plan: 01
    provides: "DomainKnowledge schema, NLOS YAML, domain loader with auto-detection"
provides:
  - "Three-bounce geometry validator (sensor-to-wall visibility, wall normal, occluder blocking, return path)"
  - "Sensor FOV coverage check against relay wall angular extent"
  - "Temporal resolution sufficiency check using round-trip formula (c*dt/2)"
  - "run_nlos_checks standalone function for NLOS-only validation"
  - "Domain-based NLOS dispatch in run_deterministic_checks pipeline"
affects: [02-03, orchestrator-runner, physics-checker]

tech-stack:
  added: []
  patterns: [pure-function-checks, domain-dispatch, fail-fast-pipeline]

key-files:
  created:
    - src/agentsim/physics/checks/nlos_geometry.py
    - tests/unit/test_nlos_geometry.py
  modified:
    - src/agentsim/physics/checker.py
    - src/agentsim/physics/__init__.py
    - tests/unit/test_checker_pipeline.py

self-check:
  result: PASSED
  tests-run: 18
  tests-passed: 18
  coverage-note: "12 nlos_geometry tests + 6 checker pipeline tests (including NLOS dispatch)"
---

## What was built

Three deterministic NLOS geometry validation functions in `nlos_geometry.py`:

1. **check_three_bounce_geometry** — Validates the full three-bounce light path: sensor can see relay wall (dot product within FOV cone), wall normal faces sensor hemisphere, optional occluder does not block sensor-to-wall path, hidden objects are in the relay wall's far hemisphere for return path.

2. **check_sensor_fov** — Computes angular extent of relay wall as seen from sensor (`2 * atan2(wall_size/2, distance)`) and compares against sensor FOV. Uses practical threshold of 40% FOV coverage for scanning-based systems.

3. **check_temporal_resolution** — Validates time-bin width resolves hidden scene geometry using round-trip formula: `spatial_resolution = c * dt / 2`. Critical pitfall: uses `/2` for round-trip, not one-way distance.

## Pipeline integration

- `run_nlos_checks()` aggregates all three checks into a `ValidationReport`
- `run_deterministic_checks()` dispatches NLOS checks as Step 7 when domain is `nlos_transient_imaging` or `nlos_scene_params` is provided
- Existing 6-check pipeline unaffected for non-NLOS domains

## Deviations

None. Implementation matches plan exactly.

## Tests

- 12 tests in `test_nlos_geometry.py` covering valid/invalid geometries, edge cases, round-trip formula
- 6 tests in `test_checker_pipeline.py` for NLOS integration and backward compatibility
- All 18 tests pass in 0.47s
