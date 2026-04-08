# Deterministic Validation Checks

> Pure functions that validate simulation code and parameters against physical laws -- no LLM calls, no side effects.

## Files

### __init__.py
Package docstring only. Each check module is imported directly by `checker.py`.

### units.py
**Pint-based unit consistency validation.** Checks that every parameter has a valid SI-compatible unit string and a finite, non-NaN magnitude. Uses the shared `_ureg` from `physics.models`.

- `check_unit_consistency(params)` -- Takes `dict[str, tuple[float, str]]`, returns `tuple[CheckResult, ...]`.
- Severity: ERROR for unknown units, NaN, infinity, or dimensionality errors.

### ranges.py
**Parameter range plausibility checking.** Cross-references values against the curated `PARAMETER_RANGES` in `constants.py`. Converts units via Pint before comparison.

- `check_parameter_ranges(params, domain)` -- Returns ERROR when value falls outside `[min, max]` for the domain. Returns INFO when no range data exists for a parameter.

### ast_extract.py
**AST-based parameter extraction from Python simulation code.** Parses source code to find:

- Variable assignments (simple, subscript, dict literal, keyword arguments).
- Solver type detection (implicit vs explicit from method names like `BDF`, `RK45`).
- Mesh file paths from load calls (`trimesh.load`, etc.).
- Known physics parameters mapped to typed fields (`velocity`, `timestep`, `mesh_spacing`).

Key types:
- `PhysicsParameterVisitor` -- AST visitor class that walks the tree.
- `extract_physics_from_ast(code)` -- Returns `ASTExtractionResult` with extracted params and any syntax error issues.

### equations.py
**SymPy dimensional equation tracing.** Uses SymPy's SI dimensional analysis to check dimensional consistency of expressions.

- `check_expression_dimensions(lhs_dim, rhs_dim)` -- Compares two SymPy Dimensions.
- `check_equation_dimensions(equations)` -- Batch checks a tuple of (lhs, rhs, description) triples.
- `trace_dimensions_from_ast(extracted)` -- Bridge from AST extraction. Phase 1 is conservative: only reports when parameters with unit hints are found; full expression tracing deferred to Phase 2.

### stability.py
**CFL numerical stability checking.** Computes the Courant-Friedrichs-Lewy number: `CFL = |v| * dt / dx`.

- `check_cfl_stability(params)` -- Takes `ExtractedSimulationParams`.
- Implicit solvers: INFO (unconditionally stable).
- Explicit solvers: ERROR if CFL > 1.0, WARNING if CFL > 0.8.
- Unknown solver: downgrades severity (WARNING instead of ERROR for CFL > 1.0).
- Returns INFO when insufficient parameters are available to compute CFL.

### mesh_quality.py
**Mesh quality validation via trimesh.** Checks three quality metrics for each referenced mesh file:

1. **Watertightness** -- WARNING if mesh is not watertight.
2. **Aspect ratio** -- ERROR if max > 100, WARNING if max > 10 (ratio of longest to shortest edge per triangle).
3. **Skewness** -- WARNING if max > 0.9 (deviation from equilateral, where 0 = perfect and 1 = degenerate).

Gracefully handles: trimesh not installed (INFO), file not found (INFO, may be runtime-generated), non-triangle meshes (WARNING).

### nlos_geometry.py
**NLOS transient imaging geometry validation.** Domain-specific checks for non-line-of-sight experiments:

- `check_three_bounce_geometry()` -- Validates: sensor can see relay wall (within FOV cone), wall normal faces sensor, hidden objects are behind the wall, occluder blocks line of sight correctly.
- `check_sensor_fov()` -- Validates FOV covers the relay wall (ERROR if coverage ratio < 5%).
- `check_temporal_resolution()` -- Validates time-bin width resolves features using round-trip formula `c * dt / 2` (not one-way).
- `check_reconstruction_sanity()` -- Validates reconstructed object is on the hidden side, within the visibility cone, and within max resolvable depth.

Uses `SPEED_OF_LIGHT` from the constants registry and numpy for 3D geometry math.

## Check Pipeline

The checks are composed by `checker.py` in cost order. Each check returns `tuple[CheckResult, ...]`. The pipeline accumulates results and stops at the first ERROR.

```
1. units.py         (< 1ms)   -- Unit string validity, NaN/Inf
2. ranges.py        (< 10ms)  -- Plausibility bounds
3. ast_extract.py   (< 100ms) -- Code parsing
4. equations.py     (< 1s)    -- Dimensional analysis
5. stability.py     (< 100ms) -- CFL number
6. mesh_quality.py  (< 5s)    -- Triangle quality metrics
7. nlos_geometry.py (varies)   -- Domain-specific (NLOS or paradigm-dispatched)
```

## Severity Levels

- **ERROR** -- Simulation will produce physically incorrect results. Pipeline halts.
- **WARNING** -- Potential issue that may affect accuracy. Pipeline continues.
- **INFO** -- Informational finding (e.g., "no range data", "implicit solver detected"). Pipeline continues.

## Key Patterns

- **Pure functions**: Every check takes parameters and returns `tuple[CheckResult, ...]`. No mutation, no side effects.
- **Graceful degradation**: Missing dependencies (trimesh), missing files, or insufficient parameters produce INFO/WARNING rather than crashing.
- **Constants from registry**: Checks use `lookup_constant()` and `get_parameter_range()` rather than hardcoded values.

## Dependencies

- **Depends on**: `physics.models` (all check result types), `physics.constants` (ranges, constants), `pint`, `sympy`, `numpy`, `trimesh` (optional).
- **Depended on by**: `physics.checker` (composes all checks into the pipeline).
