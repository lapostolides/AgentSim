"""Fail-fast deterministic validation pipeline.

Composes all 6 physics checks in cost order per D-04:
1. Pint unit consistency (<1ms)
2. Parameter range plausibility (<10ms)
3. AST parameter extraction (<100ms)
4. SymPy equation tracing (<1s)
5. CFL numerical stability (<100ms)
6. Mesh quality (<5s)

Stops at first ERROR-level finding. WARNINGs and INFOs are collected.
"""

from __future__ import annotations

import time

from agentsim.physics.checks.ast_extract import extract_physics_from_ast
from agentsim.physics.checks.equations import trace_dimensions_from_ast
from agentsim.physics.checks.mesh_quality import check_mesh_quality
from agentsim.physics.checks.nlos_geometry import (
    check_sensor_fov,
    check_temporal_resolution,
    check_three_bounce_geometry,
)
from agentsim.physics.checks.ranges import check_parameter_ranges
from agentsim.physics.checks.stability import check_cfl_stability
from agentsim.physics.checks.units import check_unit_consistency
from agentsim.physics.models import CheckResult, Severity, ValidationReport


def _has_error(results: tuple[CheckResult, ...]) -> bool:
    """Return True if any result has ERROR severity."""
    return any(r.severity == Severity.ERROR for r in results)


def _make_report(
    all_results: list[CheckResult],
    start: float,
) -> ValidationReport:
    """Build a ValidationReport from accumulated results and start time."""
    duration = time.perf_counter() - start
    results_tuple = tuple(all_results)
    return ValidationReport(
        results=results_tuple,
        passed=not _has_error(results_tuple),
        duration_seconds=duration,
    )


def run_nlos_checks(
    sensor_pos: tuple[float, float, float],
    sensor_look_at: tuple[float, float, float],
    relay_wall_pos: tuple[float, float, float],
    relay_wall_normal: tuple[float, float, float],
    relay_wall_size: float,
    hidden_objects: tuple[tuple[float, float, float], ...],
    sensor_fov_deg: float = 20.0,
    time_bin_ps: float | None = None,
    min_feature_separation_m: float | None = None,
    occluder_pos: tuple[float, float, float] | None = None,
    occluder_size: tuple[float, float, float] | None = None,
) -> ValidationReport:
    """Run all NLOS geometry validation checks.

    Combines three-bounce geometry, sensor FOV, and temporal resolution
    checks into a single ValidationReport.

    Args:
        sensor_pos: Sensor position in 3D.
        sensor_look_at: Point the sensor is looking at.
        relay_wall_pos: Center of the relay wall.
        relay_wall_normal: Outward normal of relay wall (toward sensor).
        relay_wall_size: Side length of the relay wall (square).
        hidden_objects: Positions of hidden objects behind the wall.
        sensor_fov_deg: Sensor field of view in degrees.
        time_bin_ps: Time-bin width in picoseconds (optional).
        min_feature_separation_m: Minimum feature separation in meters (optional).
        occluder_pos: Center of the occluder (optional).
        occluder_size: Dimensions of the occluder (optional).

    Returns:
        ValidationReport with all NLOS check findings.
    """
    start = time.perf_counter()
    all_results: list[CheckResult] = []

    # Three-bounce geometry
    geometry_results = check_three_bounce_geometry(
        sensor_pos=sensor_pos,
        sensor_look_at=sensor_look_at,
        relay_wall_pos=relay_wall_pos,
        relay_wall_normal=relay_wall_normal,
        relay_wall_size=relay_wall_size,
        hidden_objects=hidden_objects,
        occluder_pos=occluder_pos,
        occluder_size=occluder_size,
        sensor_fov_deg=sensor_fov_deg,
    )
    all_results.extend(geometry_results)

    # Sensor FOV
    fov_results = check_sensor_fov(
        sensor_pos=sensor_pos,
        sensor_look_at=sensor_look_at,
        sensor_fov_deg=sensor_fov_deg,
        relay_wall_pos=relay_wall_pos,
        relay_wall_size=relay_wall_size,
    )
    all_results.extend(fov_results)

    # Temporal resolution (only if parameters provided)
    if time_bin_ps is not None and min_feature_separation_m is not None:
        temporal_results = check_temporal_resolution(
            time_bin_ps=time_bin_ps,
            min_feature_separation_m=min_feature_separation_m,
        )
        all_results.extend(temporal_results)

    return _make_report(all_results, start)


def run_deterministic_checks(
    code: str,
    parameters: dict[str, tuple[float, str]],
    mesh_paths: tuple[str, ...] = (),
    domain: str = "universal",
    nlos_scene_params: dict | None = None,
) -> ValidationReport:
    """Run all 6 deterministic physics checks in cost order.

    Stops at the first check that produces an ERROR-level result.
    WARNINGs and INFOs are accumulated but do not halt the pipeline.

    Args:
        code: Python source code of the simulation to analyze.
        parameters: Mapping of parameter name to (magnitude, unit_string).
        mesh_paths: Tuple of file paths to mesh files for quality checking.
        domain: Physics domain for range checking (default "universal").
        nlos_scene_params: Optional dict with NLOS geometry parameters for
            domain-specific checks. Expected keys: sensor_pos, sensor_look_at,
            relay_wall_pos, relay_wall_normal, relay_wall_size, hidden_objects,
            sensor_fov_deg. Optional: time_bin_ps, min_feature_separation_m,
            occluder_pos, occluder_size.

    Returns:
        ValidationReport with all findings and pass/fail status.
    """
    start = time.perf_counter()
    all_results: list[CheckResult] = []

    # Step 1: Unit consistency (<1ms)
    unit_results = check_unit_consistency(parameters)
    all_results.extend(unit_results)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 2: Parameter range plausibility (<10ms)
    range_results = check_parameter_ranges(parameters, domain)
    all_results.extend(range_results)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 3: AST parameter extraction (<100ms)
    ast_result = extract_physics_from_ast(code)
    all_results.extend(ast_result.issues)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 4: SymPy equation tracing (<1s)
    eq_results = trace_dimensions_from_ast(ast_result)
    all_results.extend(eq_results)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 5: CFL numerical stability (<100ms)
    cfl_results = check_cfl_stability(ast_result.params)
    all_results.extend(cfl_results)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 6: Mesh quality (<5s)
    mesh_results = check_mesh_quality(mesh_paths)
    all_results.extend(mesh_results)
    if _has_error(tuple(all_results)):
        return _make_report(all_results, start)

    # Step 7: NLOS domain-specific checks (if applicable)
    if (domain == "nlos_transient_imaging" or nlos_scene_params is not None) and nlos_scene_params:
        nlos_report = run_nlos_checks(
            sensor_pos=nlos_scene_params["sensor_pos"],
            sensor_look_at=nlos_scene_params["sensor_look_at"],
            relay_wall_pos=nlos_scene_params["relay_wall_pos"],
            relay_wall_normal=nlos_scene_params["relay_wall_normal"],
            relay_wall_size=nlos_scene_params["relay_wall_size"],
            hidden_objects=nlos_scene_params["hidden_objects"],
            sensor_fov_deg=nlos_scene_params.get("sensor_fov_deg", 20.0),
            time_bin_ps=nlos_scene_params.get("time_bin_ps"),
            min_feature_separation_m=nlos_scene_params.get("min_feature_separation_m"),
            occluder_pos=nlos_scene_params.get("occluder_pos"),
            occluder_size=nlos_scene_params.get("occluder_size"),
        )
        all_results.extend(nlos_report.results)

    return _make_report(all_results, start)
