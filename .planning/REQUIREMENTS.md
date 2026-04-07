# Requirements: AgentSim Physics-Aware Enhancement

**Defined:** 2026-04-06
**Core Value:** Simulations must be physically correct and scientifically credible -- not just numerically successful.

## v1 Requirements

### Physics Foundation

- [x] **PHYS-01**: Physics advisor agent exists as a dedicated, consultable agent that other agents can query during their phases
- [x] **PHYS-02**: Curated physical constants registry provides deterministic lookups for common physical constants (SI units, material properties, dimensionless group thresholds)
- [x] **PHYS-03**: Every physics advisor consultation is logged with full context (query, response, domain detected, confidence) for reproducibility

### Deterministic Validation

- [x] **DVAL-01**: AST-based code analysis extracts physical parameters, geometry definitions, solver configuration, and boundary conditions from generated Python simulation code
- [x] **DVAL-02**: Symbolic equation tracing via SymPy traces dimensional units through computations in generated code and flags dimensionally inconsistent expressions
- [x] **DVAL-03**: Dimensional analysis via Pint validates unit consistency on all physical parameters extracted from generated code
- [x] **DVAL-04**: Parameter range plausibility checker cross-references extracted parameters against constants registry and flags values outside physically meaningful ranges
- [x] **DVAL-05**: CFL / numerical stability checker computes Courant number from actual mesh spacing, timestep, and velocity, and flags violations for explicit solvers
- [x] **DVAL-06**: Mesh quality validation via trimesh/open3d computes aspect ratio, skewness, and watertightness for meshes referenced in generated code, and flags scale inconsistencies

### Computational Imaging Domain Knowledge

- [x] **CIDK-01**: NLOS domain knowledge YAML with governing equations (transient transport, RTE), geometry constraints (three-bounce path validity, relay wall visibility), SPAD sensor parameters, and reconstruction algorithm requirements (LCT, f-k migration, phasor fields)
- [x] **CIDK-02**: Extensible domain knowledge architecture — YAML schema and loader that activates domain-specific checks when computational imaging / NLOS is detected from hypothesis context
- [x] **CIDK-03**: Published codebase parameter index — curated reference of parameter constraints, valid ranges, and geometry requirements extracted from key NLOS papers (O'Toole 2018, Lindell 2019, Liu 2019, Nam 2021)

### NLOS Scene Validation

- [ ] **NLOS-01**: Three-bounce geometry validator confirms sensor can see relay wall, relay wall can illuminate hidden scene, and return path is unoccluded — flags invalid configurations before execution
- [ ] **NLOS-02**: Sensor FOV checker validates that the SPAD sensor's field of view covers the relay wall scan area given sensor position, look-at direction, and relay wall dimensions
- [ ] **NLOS-03**: Temporal resolution validator checks that time-bin width is sufficient to resolve the hidden scene geometry given relay wall-to-object distances and speed of light
- [ ] **NLOS-04**: Pre-execution scene validation with auto-fix loop — deterministic NLOS geometry checks run first, then physics advisor interprets failures; scene agent rewrites with physics constraints as feedback (max 3 retries)

### LLM Physics Integration

- [ ] **LINT-01**: Physics-informed hypothesis generation: physics advisor provides governing equations, dimensionless groups, and domain-specific parameter spaces (NLOS transient imaging context) to the hypothesis agent
- [ ] **LINT-02**: Physics-aware result analysis: analyst agent consults physics advisor to check transient imaging results against expected behavior (inverse-square falloff, temporal peak locations, reconstruction resolution limits)

### Physics Grounding

- [ ] **PGND-01**: NLOS benchmark scenes — at least 3 known-configuration test cases (confocal, non-confocal, retroreflective) with expected transient profiles that verify simulation setup before running new experiments
- [ ] **PGND-02**: Reconstruction sanity checks — post-execution validation that reconstructed hidden geometry is physically plausible (bounded by relay wall visibility cone, respects speed-of-light timing)

### Paradigm-Agnostic Domain Architecture

- [ ] **PA-01**: detect_paradigm(hypothesis) returns matching paradigm(s) from YAML files — not hardcoded to relay-wall NLOS
- [ ] **PA-02**: Scene agent receives paradigm-specific physics constraints (geometry, sensor parameters, published baselines) in its prompt before generating simulation code
- [ ] **PA-03**: Post-hoc validators dispatch based on paradigm declarations in YAML, not hardcoded check functions — adding a new paradigm requires only a YAML file
- [x] **PA-04**: Named sensor profiles (at least 3: SwissSPAD2, LinoSPAD2, streak camera) loadable from YAML with hardware-specific timing parameters (resolution, jitter, dead time, array size)
- [ ] **PA-05**: Existing relay-wall NLOS checks still pass — no regressions from the refactor
- [x] **PA-06**: At least 2 paradigms fully defined (relay wall + one other) with paradigm-specific validation rules

### Smart Experimental Design

- [ ] **SEXP-01**: Automatic DoE strategy selection analyzes parameter space dimensionality and simulation cost to choose optimal sampling strategy (LHS, Sobol, factorial, Bayesian)
- [ ] **SEXP-02**: Sensitivity analysis via SALib computes Sobol indices or Morris screening to identify which parameters significantly affect outputs
- [ ] **SEXP-03**: LHS parameter sampling via SciPy QMC generates space-filling experimental designs for parameter sweeps

### Reproducibility

- [ ] **REPR-01**: Reproducibility package generator produces Dockerfile, pinned dependency file, run scripts, and structured report for any completed experiment
- [ ] **REPR-02**: Structured experiment metadata captures environment fingerprint, git hash, timestamps, full parameter history, and physics validation results in machine-readable format

## v2 Requirements

### Domain Extensibility

- **DEXT-01**: Domain knowledge file format (YAML) allows researchers to define new physics domains with parameter ranges, governing equations, regime maps, and scaling laws
- **DEXT-02**: Community contribution system with quality vetting for researcher-contributed domain knowledge files
- **DEXT-03**: Domain auto-detection uses multi-label classification to activate relevant domain modules from hypothesis and literature context

### Advanced Physics

- **APHYS-01**: V&V-aligned validation reports follow ASME V&V conceptual framework with verification evidence, validation evidence, and uncertainty quantification
- **APHYS-02**: Grid/mesh convergence studies via Richardson extrapolation and Grid Convergence Index (GCI) run automatically when single-resolution results are detected
- **APHYS-03**: Bayesian optimization via BoTorch for expensive simulations with few allowed evaluations

### Additional CI Domains

- **ADOM-01**: Ptychography domain module (overlap constraints, probe sampling, phase retrieval convergence)
- **ADOM-02**: Lensless imaging domain module (PSF calibration, Wiener deconvolution bounds, sensor-mask distance)
- **ADOM-03**: Coded aperture domain module (mask transmission, multiplexing gain, deconvolution SNR)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full PDE solver / physics engine | AgentSim provides knowledge, not computation -- uses existing solvers |
| PINN training | Specific ML technique, not general validation tool |
| Automated paper writing | Support paper writing with reports, don't write papers |
| Multi-physics coupling orchestration | Premature complexity for v1 |
| Experimental data ingestion from databases | Accept user-provided reference data only |
| Web UI / dashboard | CLI-first research tool |
| Cloud/HPC execution | Local execution only |
| Runtime competitor comparison | Design-time awareness, not runtime logging |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PHYS-01 | Phase 1 | Complete |
| PHYS-02 | Phase 1 | Complete |
| PHYS-03 | Phase 1 | Complete |
| DVAL-01 | Phase 1 | Complete |
| DVAL-02 | Phase 1 | Complete |
| DVAL-03 | Phase 1 | Complete |
| DVAL-04 | Phase 1 | Complete |
| DVAL-05 | Phase 1 | Complete |
| DVAL-06 | Phase 1 | Complete |
| CIDK-01 | Phase 2 | Complete |
| CIDK-02 | Phase 2 | Complete |
| CIDK-03 | Phase 2 | Complete |
| NLOS-01 | Phase 2 | Pending |
| NLOS-02 | Phase 2 | Pending |
| NLOS-03 | Phase 2 | Pending |
| NLOS-04 | Phase 2 | Pending |
| LINT-01 | Phase 2 | Pending |
| LINT-02 | Phase 2 | Pending |
| PGND-01 | Phase 2 | Pending |
| PGND-02 | Phase 2 | Pending |
| PA-01 | Phase 02.1 | Pending |
| PA-02 | Phase 02.1 | Pending |
| PA-03 | Phase 02.1 | Pending |
| PA-04 | Phase 02.1 | Complete |
| PA-05 | Phase 02.1 | Pending |
| PA-06 | Phase 02.1 | Complete |
| SEXP-01 | Phase 3 | Pending |
| SEXP-02 | Phase 3 | Pending |
| SEXP-03 | Phase 3 | Pending |
| REPR-01 | Phase 4 | Pending |
| REPR-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0

---
*Requirements defined: 2026-04-06*
*Last updated: 2026-04-07 after Phase 02.1 planning -- added PA-01 through PA-06*
