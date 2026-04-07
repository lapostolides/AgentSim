---
phase: 02-computational-imaging-domain-intelligence
plan: 01
subsystem: physics
tags: [pydantic, yaml, nlos, domain-knowledge, pyyaml, frozen-models]

requires:
  - phase: 01-physics-foundation
    provides: "Frozen Pydantic model patterns, physics module structure, constants registry"
provides:
  - "DomainKnowledge Pydantic schema for YAML domain files"
  - "NLOS transient imaging YAML with governing equations, geometry, sensors, algorithms, published parameters"
  - "Cached domain loader with keyword-based auto-detection"
  - "Extensible architecture: new domains need only a YAML file"
affects: [02-02, 02-03, 02-04, physics-advisor, hypothesis-agent, analyst-agent]

tech-stack:
  added: [pyyaml]
  patterns: [yaml-domain-knowledge, domain-file-map, keyword-auto-detection, lazy-cached-loader]

key-files:
  created:
    - src/agentsim/physics/domains/schema.py
    - src/agentsim/physics/domains/nlos.yaml
    - src/agentsim/physics/domains/__init__.py
    - tests/unit/test_domain_schema.py
    - tests/unit/test_domain_loader.py
  modified:
    - pyproject.toml

key-decisions:
  - "YAML filename 'nlos.yaml' with _DOMAIN_FILE_MAP lookup for 'nlos_transient_imaging' domain name"
  - "Keyword threshold of 2+ for domain auto-detection (avoids false positives from single keyword matches)"
  - "Module-level cache dict for lazy loading (no import-time YAML parsing)"

patterns-established:
  - "Domain knowledge as YAML data files, not Python code -- adding a new domain requires only a YAML file and optional file-map entry"
  - "Frozen Pydantic models for all domain schema types (ParameterRange, GoverningEquation, etc.)"
  - "Keyword-based domain detection with configurable threshold"

requirements-completed: [CIDK-01, CIDK-02, CIDK-03]

duration: 3min
completed: 2026-04-07
---

# Phase 2 Plan 1: Domain Knowledge Architecture Summary

**NLOS domain knowledge YAML with governing equations, SPAD parameters, 4 published paper indices, and cached loader with keyword auto-detection**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-07T06:45:03Z
- **Completed:** 2026-04-07T06:48:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Extensible domain knowledge architecture: Pydantic schema models for YAML domain files with 10 frozen model classes
- NLOS transient imaging YAML with transient transport equation, three-bounce geometry constraints, SPAD sensor parameters, 3 reconstruction algorithms (LCT, f-k migration, phasor fields), and published parameter index from 4 key papers
- Cached domain loader with keyword-based auto-detection (14 NLOS keywords, threshold 2+)
- PyYAML added as explicit dependency in pyproject.toml

## Task Commits

Each task was committed atomically:

1. **Task 1: Domain knowledge Pydantic schema and NLOS YAML** - `1d85494` (feat)
2. **Task 2: Domain loader with caching and auto-detection** - `902575d` (feat)

## Files Created/Modified
- `src/agentsim/physics/domains/schema.py` - 10 frozen Pydantic models for domain knowledge YAML schema
- `src/agentsim/physics/domains/nlos.yaml` - Full NLOS transient imaging domain knowledge
- `src/agentsim/physics/domains/__init__.py` - Domain loader with caching, auto-detection, NLOS_KEYWORDS
- `tests/unit/test_domain_schema.py` - 10 tests for schema models and NLOS YAML loading
- `tests/unit/test_domain_loader.py` - 10 tests for loader, caching, and auto-detection
- `pyproject.toml` - Added pyyaml>=6.0 dependency

## Decisions Made
- Used `nlos.yaml` as filename with `_DOMAIN_FILE_MAP` for domain-name-to-filename translation, keeping filenames short while domain identifiers descriptive
- Set keyword detection threshold at 2+ to avoid false positives from single keyword matches in unrelated hypotheses
- Used module-level `_CACHE` dict for lazy loading rather than import-time parsing, per Pitfall 6 in research

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Domain knowledge foundation is complete and ready for NLOS geometry validators (Plan 02)
- `load_domain("nlos_transient_imaging")` provides typed access to all NLOS constraints
- `detect_domain()` enables automatic domain-specific check activation
- Schema is extensible for future CI subdomains (ptychography, lensless, coded aperture)

## Self-Check: PASSED

All 5 created files verified on disk. Both commit hashes (1d85494, 902575d) verified in git log.

---
*Phase: 02-computational-imaging-domain-intelligence*
*Completed: 2026-04-07*
