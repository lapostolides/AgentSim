---
phase: 02-computational-imaging-domain-intelligence
plan: 03
subsystem: orchestrator, benchmarks, physics
tags: [nlos, auto-fix, benchmarks, reconstruction-sanity, runner]

requires:
  - phase: 02-computational-imaging-domain-intelligence
    plan: 01
    provides: "DomainKnowledge, detect_domain, load_domain"
  - phase: 02-computational-imaging-domain-intelligence
    plan: 02
    provides: "run_nlos_checks, NLOS geometry validators"
provides:
  - "3 NLOS benchmark scenes (confocal, non-confocal, retroreflective) with expected transient profiles"
  - "check_reconstruction_sanity validates visibility cone and timing bounds"
  - "_run_nlos_autofix_loop in runner with max 3 retries, physics advisor consultation"
  - "_extract_nlos_scene_params helper for SceneSpec geometry extraction"
affects: [orchestrator-runner, physics-checks, benchmarks]

tech-stack:
  added: []
  patterns: [auto-fix-loop, benchmark-scenes, reconstruction-validation]

key-files:
  created:
    - src/agentsim/benchmarks/__init__.py
    - src/agentsim/benchmarks/nlos_benchmarks.py
    - tests/unit/test_nlos_benchmarks.py
    - tests/unit/test_nlos_autofix.py
  modified:
    - src/agentsim/physics/checks/nlos_geometry.py
    - src/agentsim/orchestrator/runner.py

self-check:
  result: PASSED
  tests-run: 18
  tests-passed: 18
  coverage-note: "13 benchmark + reconstruction tests, 5 auto-fix tests"
---

## What was built

### NLOS Benchmark Scenes

Three canonical configurations in `nlos_benchmarks.py`:

1. **confocal_point_reflector** — Single sphere at 1.0m behind relay wall, confocal scanning. Expected peak at ~16.7ns (round-trip 2*(1.5+1.0)/c).
2. **non_confocal_two_objects** — Two spheres at 0.5m and 1.5m depths. Expected: two separable transient peaks.
3. **retroreflective_corner** — Corner reflector geometry. Expected: enhanced retroreflective return.

All three pass `run_nlos_checks` — they are known-good configurations.

### Reconstruction Sanity Check

`check_reconstruction_sanity` in `nlos_geometry.py` validates:
- Object is on the hidden side of relay wall (not sensor side)
- Object is within visibility cone (lateral extent bounded by wall size)
- Object depth does not exceed max resolvable depth (c * bins * dt / 2)

### Auto-Fix Loop

`_run_nlos_autofix_loop` in `runner.py`:
1. For each NLOS scene, runs geometry checks
2. On failure: consults physics advisor for fix guidance
3. Re-runs scene phase with fix feedback
4. Repeats up to 3 times
5. Wired into `run_experiment` between physics validation gate and execution

## Deviations

None. Implementation matches plan exactly.

## Tests

- 13 tests in `test_nlos_benchmarks.py` (scene definitions, registry, geometry validity, reconstruction sanity)
- 5 tests in `test_nlos_autofix.py` (param extraction, retry logic, domain detection)
- 81 total phase 2 tests pass with no regressions
