---
phase: 02-computational-imaging-domain-intelligence
verified: 2026-04-07T07:30:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 2: Computational Imaging Domain Intelligence — Verification Report

**Phase Goal:** The system deeply understands NLOS transient imaging — it validates three-bounce geometry, checks sensor FOV against relay wall coverage, verifies temporal bin resolution, and blocks physically impossible scene configurations before execution. Domain knowledge is curated from published NLOS codebases (O'Toole, Lindell, Liu, Nam) and stored as extensible YAML. The architecture supports adding new CI subdomains (ptychography, lensless, coded aperture) via the same YAML schema.

**Verified:** 2026-04-07T07:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Three-bounce geometry validation confirms sensor sees relay wall, relay wall illuminates hidden scene, return path unoccluded | VERIFIED | `check_three_bounce_geometry` in `nlos_geometry.py` implements all four sub-checks; 12 tests pass |
| 2 | Sensor FOV validates SPAD coverage of relay wall scan area | VERIFIED | `check_sensor_fov` computes angular extent vs FOV with 5% coverage threshold; test_sensor_fov_* pass |
| 3 | Temporal resolution check verifies time-bin width resolves hidden scene geometry | VERIFIED | `check_temporal_resolution` uses round-trip formula c*dt/2; temporal tests pass |
| 4 | NLOS domain YAML contains governing equations, 3 reconstruction algorithm constraints, published parameters from 4 key papers | VERIFIED | `nlos.yaml` has `transient_transport` equation, lct/fk_migration/phasor_fields algorithms, otoole_2018/lindell_2019/liu_2019/nam_2021 |
| 5 | Pre-execution auto-fix loop catches/corrects invalid NLOS configurations (max 3 retries) | VERIFIED | `_run_nlos_autofix_loop` in `runner.py` confirmed; wired after physics gate before execution |
| 6 | Adding a new CI subdomain requires only a YAML file and optional _DOMAIN_FILE_MAP entry | VERIFIED | `load_domain` resolves via `_DOMAIN_FILE_MAP`; schema extensible; no core pipeline changes needed |
| 7 | At least 3 NLOS benchmark scenes (confocal, non-confocal, retroreflective) with known transient profiles | VERIFIED | `nlos_benchmarks.py` defines `CONFOCAL_POINT_REFLECTOR`, `NON_CONFOCAL_TWO_OBJECTS`, `RETROREFLECTIVE_CORNER`; all 3 pass `run_nlos_checks` |
| 8 | Hypothesis agent receives NLOS-specific physics context when generating CI hypotheses | VERIFIED | `format_nlos_physics_context` in `hypothesis.py` — outputs transient transport, algorithms, dimensionless groups, geometry constraints; injected via `nlos_physics_context` param |
| 9 | Analyst agent consults NLOS validation criteria when analyzing transient imaging results | VERIFIED | `format_nlos_analysis_context` in `analyst.py` — outputs inverse-square falloff, temporal peak locations, reconstruction resolution limits |
| 10 | Domain auto-detection returns "nlos_transient_imaging" for NLOS keywords | VERIFIED | `detect_domain` uses frozenset of 14 keywords with threshold 2+; returns correct domain |
| 11 | NLOS checks dispatched through checker pipeline when domain is nlos_transient_imaging | VERIFIED | `run_deterministic_checks` Step 7 calls `run_nlos_checks` when domain matches or `nlos_scene_params` present |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/agentsim/physics/domains/schema.py` | 10 frozen Pydantic models | VERIFIED | 122 lines; all models frozen=True; exports DomainKnowledge, GoverningEquation, GeometryConstraint, SensorParameters, ReconstructionAlgorithm, PublishedParameterSet, DimensionlessGroup |
| `src/agentsim/physics/domains/nlos.yaml` | NLOS domain knowledge | VERIFIED | 160 lines; domain: nlos_transient_imaging; 4 published papers; transient_transport equation; 3 reconstruction algorithms; SPAD sensor params; 3 dimensionless groups |
| `src/agentsim/physics/domains/__init__.py` | Cached loader + auto-detection | VERIFIED | Exports load_domain, detect_domain, NLOS_KEYWORDS; uses yaml.safe_load; _DOMAIN_FILE_MAP for name-to-file translation |
| `src/agentsim/physics/checks/nlos_geometry.py` | Three NLOS check functions + reconstruction sanity | VERIFIED | 517 lines; exports check_three_bounce_geometry, check_sensor_fov, check_temporal_resolution, check_reconstruction_sanity |
| `src/agentsim/physics/checker.py` | Extended pipeline with NLOS dispatch | VERIFIED | run_nlos_checks and run_deterministic_checks with Step 7 NLOS dispatch; run_nlos_checks exported from physics/__init__.py |
| `src/agentsim/benchmarks/nlos_benchmarks.py` | 3 benchmark scene definitions | VERIFIED | 137 lines; CONFOCAL_POINT_REFLECTOR (peak 16.7ns), NON_CONFOCAL_TWO_OBJECTS, RETROREFLECTIVE_CORNER; list_benchmarks/get_benchmark_scene functions |
| `src/agentsim/orchestrator/runner.py` | NLOS auto-fix loop + NLOS context injection | VERIFIED | _run_nlos_autofix_loop, _extract_nlos_scene_params present; detect_domain imported; nlos_context dict built and passed to build_agent_registry |
| `src/agentsim/agents/hypothesis.py` | NLOS physics context injection | VERIFIED | format_nlos_physics_context, nlos_physics_context parameter, {nlos_section} placeholder in prompt |
| `src/agentsim/agents/analyst.py` | NLOS analysis context injection | VERIFIED | format_nlos_analysis_context, nlos_analysis_context parameter |
| `src/agentsim/agents/physics_advisor.py` | NLOS domain knowledge injection | VERIFIED | format_nlos_advisor_context, nlos_domain_knowledge parameter |
| `src/agentsim/orchestrator/agent_registry.py` | nlos_context propagation | VERIFIED | build_agent_registry accepts nlos_context dict; distributes to hypothesis, physics_advisor, analyst factories |
| `tests/unit/test_domain_schema.py` | Schema validation tests | VERIFIED | 10 tests, all pass |
| `tests/unit/test_domain_loader.py` | Loader + auto-detection tests | VERIFIED | 10 tests, all pass |
| `tests/unit/test_nlos_geometry.py` | NLOS check function tests | VERIFIED | 12 tests, all pass |
| `tests/unit/test_checker_pipeline.py` | Pipeline + NLOS dispatch tests | VERIFIED | 16 tests (10 existing + 6 NLOS), all pass |
| `tests/unit/test_nlos_llm_integration.py` | NLOS context injection tests | VERIFIED | 15 tests, all pass |
| `tests/unit/test_nlos_benchmarks.py` | Benchmark + sanity check tests | VERIFIED | 13 tests, all pass |
| `tests/unit/test_nlos_autofix.py` | Auto-fix loop tests | VERIFIED | 5 tests, all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `physics/domains/__init__.py` | `nlos.yaml` | yaml.safe_load + DomainKnowledge.model_validate | WIRED | Pattern confirmed in load_domain(); verified at runtime: 4 papers, 3 algorithms loaded |
| `physics/domains/__init__.py` | `physics/domains/schema.py` | `from agentsim.physics.domains.schema import DomainKnowledge` | WIRED | Import confirmed line 19 |
| `physics/checks/nlos_geometry.py` | `physics/models.py` | `from agentsim.physics.models import CheckResult, Severity` | WIRED | Line 15 confirmed |
| `physics/checker.py` | `physics/checks/nlos_geometry.py` | `from agentsim.physics.checks.nlos_geometry import ...` | WIRED | Lines 21-25 confirmed; all three functions imported |
| `orchestrator/runner.py` | `physics/__init__.py` | `from agentsim.physics import run_nlos_checks` | WIRED | Line 143 confirmed (inside autofix loop) |
| `orchestrator/runner.py` | `physics/domains/__init__.py` | `from agentsim.physics.domains import detect_domain` | WIRED | Line 25 confirmed |
| `agents/hypothesis.py` | NLOS physics context string | `nlos_physics_context` parameter in create_hypothesis_agent | WIRED | Parameter at line 214; {nlos_section} placeholder at line 129 |
| `agents/analyst.py` | NLOS analysis context string | `nlos_analysis_context` parameter in create_analyst_agent | WIRED | Parameter at line 137 confirmed |
| `orchestrator/agent_registry.py` | All three agents | nlos_context dict distribution | WIRED | nlos.get("hypothesis",""), nlos.get("advisor",""), nlos.get("analyst","") at lines 53, 57, 62 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `runner.py` NLOS context injection | `nlos_context` dict | `load_domain("nlos_transient_imaging")` + `format_nlos_*` | Yes — loads from YAML, formats to strings | FLOWING |
| `checker.py` Step 7 | `nlos_report` | `run_nlos_checks(**nlos_scene_params)` | Yes — geometry math, returns CheckResult tuples | FLOWING |
| `nlos_geometry.py` checks | `spatial_resolution_m` | `SPEED_OF_LIGHT * dt / 2.0` | Yes — deterministic float computation | FLOWING |
| `nlos_benchmarks.py` peak timing | `expected_peak_ns` | `round(2*(1.5+1.0)/SPEED_OF_LIGHT*1e9, 1)` | Yes — evaluates to 16.7 at module load | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| load_domain returns 4 published papers | `load_domain("nlos_transient_imaging")` — len(published_parameter_index) | 4 | PASS |
| detect_domain identifies NLOS from keywords | `detect_domain("NLOS relay wall transient imaging SPAD sensor")` | "nlos_transient_imaging" | PASS |
| run_nlos_checks passes valid confocal geometry | `run_nlos_checks(sensor_pos=(0,-1.5,0), ...)` | passed=True | PASS |
| 3 benchmark scenes registered | `list_benchmarks()` | ('confocal_point_reflector', 'non_confocal_two_objects', 'retroreflective_corner') | PASS |
| format_nlos_physics_context produces complete context | format call on loaded DK | has transient_transport, algorithms, dimensionless groups, geometry | PASS |
| format_nlos_analysis_context produces validation criteria | format call on loaded DK | has inverse-square, temporal peak locations, reconstruction resolution | PASS |
| All 81 phase 2 unit tests pass | pytest 7 test files | 81/81 passed in 0.48s | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CIDK-01 | 02-01 | NLOS YAML with governing equations, geometry, SPAD params, reconstruction algorithms | SATISFIED | `nlos.yaml` confirmed; transient_transport, lct/fk_migration/phasor_fields, SPAD params present |
| CIDK-02 | 02-01 | Extensible YAML schema and loader with auto-detection | SATISFIED | `schema.py` + `__init__.py`; new domain = YAML + optional _DOMAIN_FILE_MAP entry |
| CIDK-03 | 02-01 | Published parameter index from O'Toole 2018, Lindell 2019, Liu 2019, Nam 2021 | SATISFIED | All 4 entries in nlos.yaml published_parameter_index |
| NLOS-01 | 02-02 | Three-bounce geometry validator | SATISFIED | `check_three_bounce_geometry` confirmed; blocks sensor-behind-wall, bad normal, occluder, wrong side |
| NLOS-02 | 02-02 | Sensor FOV checker | SATISFIED | `check_sensor_fov` confirmed; compares angular wall extent to FOV with 5% coverage threshold |
| NLOS-03 | 02-02 | Temporal resolution validator | SATISFIED | `check_temporal_resolution` confirmed; round-trip c*dt/2 formula; errors when insufficient |
| NLOS-04 | 02-03 | Pre-execution auto-fix loop with max 3 retries | SATISFIED | `_run_nlos_autofix_loop` confirmed; wired into run_experiment between physics gate and execution |
| LINT-01 | 02-04 | Physics-informed hypothesis generation with NLOS context | SATISFIED | `format_nlos_physics_context` + `nlos_physics_context` param; runner injects when domain detected |
| LINT-02 | 02-04 | Physics-aware result analysis with NLOS validation criteria | SATISFIED | `format_nlos_analysis_context` + `nlos_analysis_context` param; analyst receives NLOS criteria |
| PGND-01 | 02-03 | 3 NLOS benchmark scenes with expected transient profiles | SATISFIED | 3 scenes in `nlos_benchmarks.py`; peak timing computed from physics; all pass run_nlos_checks |
| PGND-02 | 02-03 | Reconstruction sanity checks bounded by visibility cone and speed-of-light timing | SATISFIED | `check_reconstruction_sanity` confirmed; checks side, lateral cone, max depth from timing |

**All 11 required IDs accounted for. No orphaned requirements.**

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `nlos_geometry.py` line 453 | `pass` in side_dot < 0 branch with misleading inline comment | Info | Logic comment says "no: normal points toward sensor" — the logic is correct (negative dot = hidden side = correct), the long comment is confusing but code behaves correctly; tests verify this path |
| None | No TODO/FIXME/PLACEHOLDER found | — | Clean |
| None | No return null/return {} stubs found | — | Clean |
| None | No hardcoded empty data arrays as final state | — | Clean |

No blockers. One informational note about a confusing comment in `check_reconstruction_sanity`.

---

### Human Verification Required

None — all critical behaviors verified programmatically. The following are noted as design-time awareness:

1. **Auto-fix loop with live LLM calls** — The `_run_nlos_autofix_loop` calls `consult_physics_advisor` and `_run_scene_phase` with real LLM agents when geometry checks fail. Integration behavior with actual API calls cannot be verified without running a full experiment. Unit tests mock this path correctly.

2. **NLOS context quality in LLM responses** — Whether the hypothesis agent actually generates better NLOS hypotheses when given the domain context (vs. without) requires a human evaluation of LLM outputs. The injection mechanism is verified; the quality improvement is a behavioral/qualitative judgment.

---

### Gaps Summary

No gaps. All 11 requirements satisfied. All 81 unit tests pass. All key links wired. Data flows from YAML through typed models to agent prompts and geometry validators. The phase goal is achieved.

---

_Verified: 2026-04-07T07:30:00Z_
_Verifier: Claude (gsd-verifier)_
