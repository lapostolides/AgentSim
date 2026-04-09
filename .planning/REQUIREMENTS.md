# Requirements: AgentSim v2.0 — Computational Imaging Knowledge Graph

**Defined:** 2026-04-08
**Core Value:** Prune the sensor configuration space using physics and information theory before any simulation runs. A user states a task and receives ranked feasible sensor configurations with theoretical guarantees.

## v2.0 Requirements

Requirements for the computational imaging knowledge graph milestone. Each maps to roadmap phases.

### Graph Infrastructure

- [x] **GRAPH-01**: Neo4j graph database runs as a local Docker container with programmatic lifecycle management (start, stop, status, health check)
- [x] **GRAPH-02**: Graph schema defines node types (Sensor, SensorFamily, Algorithm, PhysicsProperty, Task, Environment) and relationship types (HAS_PROPERTY, COMPATIBLE_WITH, ENABLES, REQUIRES, SHARES_PHYSICS) with typed properties
- [x] **GRAPH-03**: Graph client provides a Python API for CRUD operations on sensors, algorithms, and relationships, returning frozen Pydantic models
- [x] **GRAPH-04**: Seed pipeline populates the graph from structured YAML/JSON sensor definition files, including migration of existing NLOS sensor profiles
- [x] **GRAPH-05**: CLI commands (`agentsim graph start|stop|seed|status`) manage the Neo4j container and data lifecycle
- [x] **GRAPH-06**: Pipeline degrades gracefully when Neo4j is unavailable — existing experiment workflow continues unchanged with a warning

### Sensor Taxonomy

- [x] **SENS-01**: Graph contains SPAD sensor family with physics specs (timing resolution, dead time, dark count rate, PDE, pixel count, FOV, gate width)
- [x] **SENS-02**: Graph contains ToF sensor families — both continuous-wave (modulation frequency, dealiasing range, integration time) and pulsed (pulse width, repetition rate, range resolution)
- [x] **SENS-03**: Graph contains event camera family with specs (temporal resolution, contrast threshold, dynamic range, bandwidth, pixel count)
- [x] **SENS-04**: Graph contains coded aperture camera family with specs (mask pattern, mask transmittance, PSF characterization, condition number)
- [x] **SENS-05**: Graph contains light field camera family with specs (angular resolution, spatial resolution, baseline, disparity range, microlens pitch)
- [x] **SENS-06**: Graph contains LiDAR families — mechanical (scan rate, angular resolution, range), solid-state (flash FOV, point density), and FMCW (chirp bandwidth, coherence length)
- [x] **SENS-07**: Graph contains lensless camera family with specs (mask type, diffraction pattern, reconstruction condition number, working distance)
- [x] **SENS-08**: Graph contains RGB camera family with specs (pixel pitch, well depth, read noise, quantum efficiency, dynamic range, frame rate, FOV)
- [x] **SENS-09**: Graph contains structured light family with specs (pattern type, projector resolution, baseline, triangulation angle, ambient light rejection)
- [x] **SENS-10**: Graph contains polarimetric camera family with specs (Stokes parameters measured, extinction ratio, micropolarizer pitch, DoLP accuracy)
- [x] **SENS-11**: Graph contains spectral/hyperspectral camera family with specs (spectral range, spectral resolution, spatial resolution, number of bands)

### Shared Physics Foundation

- [x] **PHYS-01**: Each sensor node has geometric/spatial properties: FOV (degrees), spatial resolution (pixels or lp/mm), depth of field (m), working distance range (m), aperture geometry
- [x] **PHYS-02**: Each sensor node has temporal properties: exposure/integration time (s), temporal resolution (s), readout mode (global/rolling/event-driven), frame rate (Hz)
- [x] **PHYS-03**: Each sensor node has radiometric properties: quantum efficiency (ratio), dynamic range (dB), noise floor (e-/photon equivalent), spectral sensitivity curve, dark current
- [x] **PHYS-04**: SHARES_PHYSICS edges connect sensor families that share underlying physical principles (e.g., SPAD and CCD both governed by photon arrival statistics but with different downstream effects)
- [x] **PHYS-05**: Each sensor node has operational metadata: cost range (USD), power consumption (W), weight (g), form factor, typical operating environment
- [x] **PHYS-06**: All physics properties use canonical SI units with Pint-compatible unit annotations to prevent unit inconsistency across sensor families

### CRB / Information-Theoretic Bounds

- [x] **CRB-01**: Analytical CRB module computes closed-form Cramér-Rao bounds for sensor families with known formulations (SPAD depth, CW-ToF range, pulsed dToF range, FMCW range, polarimetric Stokes, hyperspectral unmixing, structured light triangulation)
- [x] **CRB-02**: Numerical CRB module uses JAX autodiff to compute Fisher information matrices for sensor families without analytical forms (coded aperture, lensless, event camera, light field)
- [x] **CRB-03**: CRB dispatch function selects analytical or numerical computation based on sensor family and estimation task, with explicit confidence qualifiers (analytical/numerical/empirical/unknown)
- [x] **CRB-04**: CRB results include bound type, confidence qualifier, model assumptions, and condition number to prevent misinterpretation of theoretical bounds as achievable performance
- [x] **CRB-05**: Sensitivity analysis module quantifies how CRB changes with perturbations to sensor parameters (e.g., how depth precision degrades as ambient light increases), enabling parameter importance ranking
- [x] **CRB-06**: Numerical CRB computation includes explicit stability guards: condition number checks, positive-variance assertions, Tikhonov regularization for near-singular Fisher matrices

### Feasibility Query Engine

- [x] **QUERY-01**: Given a task description and environment constraints, the query engine returns a ranked list of feasible sensor configurations with CRB-backed theoretical performance bounds
- [x] **QUERY-02**: Cross-family feasibility comparison ranks sensors from different families on the same task (e.g., SPAD vs ToF vs LiDAR for depth at 10m range)
- [x] **QUERY-03**: Constraint conflict detection identifies when task requirements are physically impossible for any known sensor (e.g., 1mm depth at 100m range in daylight)
- [x] **QUERY-04**: FeasibilityResult frozen Pydantic model captures ranked configurations, CRB bounds, confidence qualifiers, and constraint satisfaction details

### Pipeline Integration

- [x] **PIPE-01**: Orchestrator runner includes a feasibility phase between environment discovery and hypothesis generation that queries the knowledge graph
- [x] **PIPE-02**: Hypothesis agent receives feasibility context in its prompt, constraining proposals to physically viable sensor configurations — and can propose novel experiments by identifying gaps in the sensor-task landscape
- [x] **PIPE-03**: ExperimentState includes an optional `feasibility_result: FeasibilityResult | None` field tracking the graph query results for the current experiment
- [x] **PIPE-04**: Pipeline skips the feasibility phase gracefully when knowledge graph is disabled or Neo4j is unavailable
- [x] **PIPE-05**: Evaluator agent compares experimental results against CRB floor and reports efficiency ratio (actual_error / crb_bound), framing whether the bottleneck is the algorithm or the physics
- [x] **PIPE-06**: Scene agent uses Morris sensitivity analysis (mu_star rankings) to generate diverse scenes that probe the most important parameters rather than uniform sweeps
- [ ] **PIPE-07**: Analyst agent performs feasibility-gated iteration — when results identify a bottleneck parameter, re-queries the KG with tighter constraints and recommends sensor/config changes for the next iteration
- [ ] **PIPE-08**: Cross-experiment reasoning — after multiple runs, analyst identifies patterns across experiments and suggests SHARES_PHYSICS-based algorithm transfer when applicable

## Future Requirements (deferred)

- [ ] Natural language constraint parsing from free-text hypothesis (NLP -> structured Cypher)
- [ ] Empirical validation feedback loop: simulation results update sensor performance data in the graph
- [ ] Multi-sensor fusion configurations (combining sensors for complementary coverage)
- [ ] Misspecified CRB (MCRB) for robustness analysis when forward model is approximate
- [ ] Graph-based experimental design: use graph structure to suggest novel sensor combinations
- [ ] Web UI for browsing sensor taxonomy and feasibility results

## Out of Scope

- Cloud-hosted graph database — local Neo4j only for v2.0
- Real-time streaming sensor data — offline analysis only
- Automated sensor procurement / vendor integration
- Custom hardware design optimization
- Production-grade NLP query interface (using structured Python API for v2.0)

## Traceability

| Requirement | Phase | Plan | Status |
|-------------|-------|------|--------|
| GRAPH-01 | Phase 9 | — | Pending |
| GRAPH-02 | Phase 6 | — | Pending |
| GRAPH-03 | Phase 9 | — | Pending |
| GRAPH-04 | Phase 9 | — | Pending |
| GRAPH-05 | Phase 9 | — | Pending |
| GRAPH-06 | Phase 9 | — | Pending |
| SENS-01 | Phase 7 | — | Pending |
| SENS-02 | Phase 7 | — | Pending |
| SENS-03 | Phase 7 | — | Pending |
| SENS-04 | Phase 7 | — | Pending |
| SENS-05 | Phase 7 | — | Pending |
| SENS-06 | Phase 7 | — | Pending |
| SENS-07 | Phase 7 | — | Pending |
| SENS-08 | Phase 7 | — | Pending |
| SENS-09 | Phase 7 | — | Pending |
| SENS-10 | Phase 7 | — | Pending |
| SENS-11 | Phase 7 | — | Pending |
| PHYS-01 | Phase 6 | — | Pending |
| PHYS-02 | Phase 6 | — | Pending |
| PHYS-03 | Phase 6 | — | Pending |
| PHYS-04 | Phase 6 | — | Pending |
| PHYS-05 | Phase 6 | — | Pending |
| PHYS-06 | Phase 6 | — | Pending |
| CRB-01 | Phase 8 | — | Pending |
| CRB-02 | Phase 8 | — | Pending |
| CRB-03 | Phase 8 | — | Pending |
| CRB-04 | Phase 8 | — | Pending |
| CRB-05 | Phase 8 | — | Pending |
| CRB-06 | Phase 8 | — | Pending |
| QUERY-01 | Phase 9 | — | Pending |
| QUERY-02 | Phase 9 | — | Pending |
| QUERY-03 | Phase 9 | — | Pending |
| QUERY-04 | Phase 6 | — | Pending |
| PIPE-01 | Phase 10 | — | Pending |
| PIPE-02 | Phase 10 | — | Pending |
| PIPE-03 | Phase 10 | — | Pending |
| PIPE-04 | Phase 10 | — | Pending |
| PIPE-05 | Phase 10 | — | Pending |
| PIPE-06 | Phase 10 | — | Pending |
| PIPE-07 | Phase 10 | — | Pending |
| PIPE-08 | Phase 10 | — | Pending |
