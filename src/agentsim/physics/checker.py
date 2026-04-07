"""Fail-fast deterministic validation pipeline.

Composes all 6 physics checks in cost order per D-04:
1. Pint unit consistency (<1ms)
2. Parameter range plausibility (<10ms)
3. AST parameter extraction (<100ms)
4. SymPy equation tracing (<1s)
5. CFL numerical stability (<100ms)
6. Mesh quality (<5s)

Plus paradigm-dispatched checks (Step 7) when paradigm knowledge is provided.

Stops at first ERROR-level finding. WARNINGs and INFOs are collected.
"""

from __future__ import annotations

import importlib
import inspect
import time

import structlog

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

logger = structlog.get_logger()


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


def run_paradigm_checks(
    paradigm: "ParadigmKnowledge",
    scene_params: dict,
) -> ValidationReport:
    """Run validation checks declared in a paradigm YAML file.

    Dispatches two rule types:
    - ``python_check``: imports a module + function via importlib, maps
      matching scene_params to function parameters via inspect.signature.
    - ``range_check``: compares a scene parameter value against declared
      min/max bounds.

    Unknown modules or missing functions log a warning and produce a
    WARNING-level CheckResult rather than crashing the pipeline.

    Args:
        paradigm: ParadigmKnowledge loaded from a paradigm YAML file.
        scene_params: Dict of scene parameters to validate.

    Returns:
        ValidationReport with all findings from paradigm validation rules.
    """
    from agentsim.physics.domains.schema import ParadigmKnowledge  # noqa: F811

    start = time.perf_counter()
    all_results: list[CheckResult] = []

    for rule in paradigm.validation_rules:
        if rule.type == "python_check":
            _dispatch_python_check(rule, scene_params, all_results)
        elif rule.type in ("range_check", "threshold_check"):
            _dispatch_range_check(rule, scene_params, all_results)
        else:
            logger.warning(
                "unknown_validation_rule_type",
                rule_name=rule.name,
                rule_type=rule.type,
            )

    return _make_report(all_results, start)


def _dispatch_python_check(
    rule: "ValidationRule",
    scene_params: dict,
    results: list[CheckResult],
) -> None:
    """Import and call a python_check validation function.

    Uses inspect.signature to extract only matching parameters from
    scene_params. Errors during import or execution are caught and
    converted to WARNING-level results.

    Args:
        rule: The ValidationRule with module and function fields.
        scene_params: Dict of scene parameters.
        results: Mutable list to append CheckResult findings to.
    """
    try:
        mod = importlib.import_module(rule.module)
        fn = getattr(mod, rule.function)
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "python_check_import_error",
            rule_name=rule.name,
            module=rule.module,
            function=rule.function,
            error=str(exc),
        )
        results.append(CheckResult(
            check=rule.name,
            severity=Severity.WARNING,
            message=f"Could not load check {rule.module}.{rule.function}: {exc}",
        ))
        return

    try:
        sig = inspect.signature(fn)
        kwargs = {
            name: scene_params[name]
            for name in sig.parameters
            if name in scene_params
        }
        check_results = fn(**kwargs)
        if isinstance(check_results, tuple):
            results.extend(check_results)
        else:
            results.append(check_results)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "python_check_execution_error",
            rule_name=rule.name,
            error=str(exc),
        )
        results.append(CheckResult(
            check=rule.name,
            severity=Severity.WARNING,
            message=f"Check {rule.name} failed with error: {exc}",
        ))


def _dispatch_range_check(
    rule: "ValidationRule",
    scene_params: dict,
    results: list[CheckResult],
) -> None:
    """Evaluate a declarative range_check or threshold_check rule.

    Compares the scene parameter value against the rule's min/max bounds.
    Missing parameters are silently skipped (they may not be applicable).

    Args:
        rule: The ValidationRule with parameter, min, max fields.
        scene_params: Dict of scene parameters.
        results: Mutable list to append CheckResult findings to.
    """
    value = scene_params.get(rule.parameter)
    if value is None:
        return

    severity = Severity.ERROR if rule.severity == "error" else Severity.WARNING

    if rule.min is not None and value < rule.min:
        results.append(CheckResult(
            check=rule.name,
            severity=severity,
            message=rule.message or f"{rule.parameter}={value} below minimum {rule.min}",
        ))
    elif rule.max is not None and value > rule.max:
        results.append(CheckResult(
            check=rule.name,
            severity=severity,
            message=rule.message or f"{rule.parameter}={value} above maximum {rule.max}",
        ))


def run_deterministic_checks(
    code: str,
    parameters: dict[str, tuple[float, str]],
    mesh_paths: tuple[str, ...] = (),
    domain: str = "universal",
    nlos_scene_params: dict | None = None,
    paradigm_knowledge: "ParadigmKnowledge | None" = None,
) -> ValidationReport:
    """Run all 6 deterministic physics checks in cost order.

    Stops at the first check that produces an ERROR-level result.
    WARNINGs and INFOs are accumulated but do not halt the pipeline.

    When ``paradigm_knowledge`` is provided, Step 7 dispatches validation
    rules from the paradigm YAML instead of hardcoded NLOS checks.
    When ``paradigm_knowledge`` is None, falls back to the legacy
    hardcoded NLOS check path for backward compatibility.

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
        paradigm_knowledge: Optional ParadigmKnowledge for paradigm-dispatched
            validation. When provided, replaces hardcoded NLOS checks.

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

    # Step 7: Paradigm-specific checks (if applicable)
    if paradigm_knowledge is not None:
        paradigm_report = run_paradigm_checks(
            paradigm_knowledge, nlos_scene_params or {},
        )
        all_results.extend(paradigm_report.results)
    elif (
        domain == "nlos_transient_imaging" or nlos_scene_params is not None
    ) and nlos_scene_params:
        # Backward compat: hardcoded NLOS checks when no paradigm provided
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
