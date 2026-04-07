---
phase: 02-computational-imaging-domain-intelligence
plan: 04
subsystem: agents
tags: [nlos, llm-integration, hypothesis-agent, analyst-agent, physics-advisor, domain-context]

requires:
  - phase: 02-computational-imaging-domain-intelligence
    plan: 01
    provides: "DomainKnowledge schema, NLOS YAML, load_domain, detect_domain"
provides:
  - "format_nlos_physics_context for hypothesis agent (equations, dimensionless groups, geometry, algorithms)"
  - "format_nlos_advisor_context for physics advisor (equations, SPAD params, published data)"
  - "format_nlos_analysis_context for analyst agent (signal physics, reconstruction quality, failure modes)"
  - "NLOS context injection in create_hypothesis_agent, create_physics_advisor_agent, create_analyst_agent"
  - "Domain-aware agent registry with nlos_context parameter"
  - "Runner auto-detects NLOS domain from hypothesis text and injects context into all agents"
affects: [orchestrator-runner, agent-registry, hypothesis-phase, analyst-phase]

tech-stack:
  added: []
  patterns: [context-injection, domain-aware-prompts, backward-compatible-defaults]

key-files:
  created:
    - tests/unit/test_nlos_llm_integration.py
  modified:
    - src/agentsim/agents/hypothesis.py
    - src/agentsim/agents/analyst.py
    - src/agentsim/agents/physics_advisor.py
    - src/agentsim/orchestrator/runner.py
    - src/agentsim/orchestrator/agent_registry.py

self-check:
  result: PASSED
  tests-run: 15
  tests-passed: 15
  coverage-note: "9 format/prompt tests + 6 agent registry/analyst integration tests"
---

## What was built

NLOS-specific physics context injection into three LLM agents:

1. **Hypothesis agent** — `format_nlos_physics_context()` extracts governing equations (transient transport), dimensionless groups (spatial/temporal Nyquist, virtual aperture ratio), geometry constraints (three-bounce requirements), and reconstruction algorithms (LCT, F-K migration, phasor fields) from DomainKnowledge. Injected via `nlos_physics_context` parameter in `create_hypothesis_agent`.

2. **Physics advisor** — `format_nlos_advisor_context()` formats governing equations, SPAD sensor typical parameters (temporal resolution, FOV ranges), and published experiment parameters from 4 papers. Injected via `nlos_domain_knowledge` parameter in `create_physics_advisor_agent`.

3. **Analyst agent** — `format_nlos_analysis_context()` provides NLOS-specific validation criteria: inverse-square signal falloff, temporal peak locations matching round-trip paths, reconstruction resolution bounds, and common failure modes. Injected via `nlos_analysis_context` parameter in `create_analyst_agent`.

## Runner wiring

- `run_experiment()` calls `detect_domain(hypothesis_text)` after environment discovery
- When NLOS detected, loads domain knowledge and formats all three context strings
- Passes `nlos_context` dict to `build_agent_registry()` which distributes to agent factories
- Non-NLOS experiments get standard agents (backward compatible — all params default to `""`)

## Deviations

None. Implementation matches plan exactly.

## Tests

- 15 tests in `test_nlos_llm_integration.py` covering format functions, prompt injection, agent registry integration, and backward compatibility
- All existing agent registry and physics advisor tests still pass
