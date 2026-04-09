# AgentSim — Computational Imaging Knowledge Graph (v2.0)

## What This Is

AgentSim is a multi-agent autonomous hypothesis-driven simulation system for computational science research. v2.0 adds a computational imaging knowledge graph: a Neo4j-backed queryable database of sensors, algorithms, physics relationships, and information-theoretic bounds (CRB) that prunes the sensor configuration solution space before expensive simulation. A researcher describes a task and environment constraints, and the system returns feasible sensor+algorithm combinations with theoretical performance bounds — cutting the simulation search space by orders of magnitude.

## Core Value

The system must **prune the sensor configuration space using physics and information theory** before any simulation runs. A user states a task ("map cave at 1cm resolution in darkness") and receives ranked feasible sensor configurations with theoretical guarantees, not a brute-force sweep of 10,000 simulations.

## Current Milestone: v2.0 Computational Imaging Knowledge Graph

**Goal:** Build a queryable knowledge graph of computational imaging sensors, algorithms, and physics relationships that prunes the sensor configuration solution space via information-theoretic bounds (CRB) before expensive simulation.

**Target features:**
- Neo4j graph database (local service) with sensor, algorithm, environment, and task nodes
- Comprehensive shared physics foundation:
  - Geometric/spatial: FOV, spatial resolution (pixel pitch, diffraction limit, PSF), depth of field, working distance, aperture geometry
  - Temporal: exposure/integration time, temporal resolution, readout mode (global/rolling/event-driven)
  - Radiometric: photon statistics (Poisson, shot noise, dark current), dynamic range, spectral sensitivity, quantum efficiency
  - Information-theoretic: CRB/Fisher information, SNR vs radiance, spatial-temporal-spectral bandwidth
- Exhaustive sensor taxonomy: SPAD, ToF (CW + pulsed), event cameras, coded aperture, light field, LiDAR, lensless, RGB, structured light, polarimetric, spectral/hyperspectral
- Rich sensor nodes: physics specs + operational metadata (cost, power, weight) + compatible algorithms
- Hybrid CRB layer: analytical closed-form for known sensors, JAX/autograd numerical Fisher information for exotic sensors
- Natural language feasibility query engine: task + environment constraints -> ranked feasible sensor configs
- AgentSim pipeline integration: hypothesis agent queries graph before proposing experiments

## Requirements

### Validated (from v1.0)

- 8-agent pipeline (scout, auditor, hypothesis, scene, executor, evaluator, analyst, validator) -- v1.0
- Physics advisor agent with curated constants registry and consultation logging -- Phase 1
- Deterministic physics validation (AST, units, ranges, CFL, mesh) -- Phase 1
- NLOS domain knowledge with paradigm-agnostic YAML architecture -- Phase 02.1
- Sensor/algorithm advisor with transfer function reasoning -- Phase 02.2
- Hypothesis quality optimization with 6-dimension scoring -- v1.0
- Human-in-the-loop intervention gates (5 checkpoints) -- v1.0
- Immutable functional state management -- v1.0
- Mitsuba 3 transient rendering integration with NLOS templates -- Phase 5

### Active

See REQUIREMENTS.md for v2.0 scoped requirements.

### Out of Scope

- Production ML training infrastructure (distributed training, hyperparameter search platforms)
- Real-time inference serving -- offline evaluation only
- Custom hardware-specific optimizations (TensorRT, ONNX export)
- Cloud-hosted graph database -- local Neo4j only for v2.0
- Automated sensor procurement / vendor integration

## Context

- **v1.0 foundation**: Physics-aware pipeline complete with NLOS domain intelligence, paradigm-agnostic architecture, physics-space reasoning, and Mitsuba 3 transient rendering. The system validates physics correctness before execution.
- **Existing domain models**: YAML-based paradigm definitions, sensor profiles, transfer function matrices already exist for NLOS. The knowledge graph extends this to ALL computational imaging modalities.
- **Textbook reference**: Bhandari, Kadambi, Raskar -- Computational Imaging (MIT Press, 2022). Structure maps to sensor families: spatially coded (Ch 4), temporally coded (Ch 5), light field (Ch 6), polarimetric (Ch 7), spectral (Ch 8), programmable illumination (Ch 9), light transport (Ch 10).
- **Shared physics insight**: All sensor families share underlying physics (photon statistics, exposure/integration time, noise models, FOV, resolution limits) with different downstream effects. The knowledge graph is organized around these shared physical principles, with CRB providing fundamental performance bounds.
- **v1.0 phases 3-4 deferred**: Smart Experimental Design (DoE) and Reproducibility phases are deprioritized. Phase 03-01 (DoE models) was completed; 03-02, 03-03, and all of Phase 4 are paused.

## Constraints

- **Tech stack**: Python, Claude Agent SDK, Pydantic frozen models, Neo4j (Docker), JAX (CRB numerics) -- extends existing patterns
- **New dependencies**: neo4j (Python driver), Docker (Neo4j container), JAX/jaxlib (differentiable Fisher information), optionally neomodel or py2neo
- **Immutability**: All state transitions return new objects -- graph query results, feasibility scores tracked immutably
- **Performance**: Graph queries must return feasibility results in <5 seconds for interactive use
- **Neo4j runtime**: Docker container running alongside experiments, agents query via Cypher

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Neo4j over NetworkX/embedded | Real graph queries (Cypher), scales to thousands of sensor configs, persistent across sessions | Confirmed |
| Hybrid CRB (analytical + JAX) | Analytical for known sensors (fast, publishable), numerical fallback for exotic sensors | Confirmed |
| Exhaustive sensor taxonomy from start | Broad coverage enables cross-domain feasibility queries -- the core differentiator | Confirmed |
| Local Docker service (not cloud) | Privacy, no latency, works offline, simpler for research use | Confirmed |
| Shared physics as graph edges | Sensors connected by common physics properties, not just categories -- enables novel sensor combinations | Confirmed |
| FOV + resolution + temporal + radiometric foundation | Four physics domains cover the shared properties that connect all sensor families | Confirmed |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check -- still the right priority?
3. Audit Out of Scope -- reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after Phase 10 (Pipeline Integration) complete — KG deeply integrated across all agents, feasibility-gated iteration enabled*
