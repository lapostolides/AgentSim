# Benchmark Scenes

> Canonical NLOS scene configurations with known expected outputs for verifying simulation solvers.

## Files

### __init__.py
Empty package init.

### nlos_benchmarks.py
Defines three benchmark NLOS scenes as frozen Pydantic models (`NLOSBenchmarkScene`). Each scene specifies complete geometry (relay wall, sensor, hidden objects, occluder), acquisition parameters (scanning mode, resolution, temporal bins), and expected output characteristics (peak timing, peak count).

**Benchmark scenes:**

1. **CONFOCAL_POINT_REFLECTOR** -- Single sphere behind relay wall with confocal scanning. Expected: one transient peak at `t = 2*(d_sensor_to_wall + d_wall_to_object)/c`.

2. **NON_CONFOCAL_TWO_OBJECTS** -- Two spheres at different depths with non-confocal scanning. Expected: two separable transient peaks separated by round-trip path difference.

3. **RETROREFLECTIVE_CORNER** -- Corner reflector geometry (two perpendicular planes). Expected: enhanced retroreflective return signal.

**Public API:**
- `list_benchmarks()` -- Returns tuple of benchmark names.
- `get_benchmark_scene(name)` -- Looks up a benchmark by name, returns `NLOSBenchmarkScene` or None.

## Key Patterns

- **Known-good references**: Each benchmark has physically computed expected outputs (peak timing derived from speed of light and geometry).
- **Immutable scenes**: All benchmarks are frozen Pydantic models defined as module-level constants.
- **Registry pattern**: `_BENCHMARKS` dict maps names to scene instances.

## Dependencies

- **Depends on**: `pydantic`.
- **Depended on by**: Test suites and validation workflows that need reference scenes with known correct answers.
