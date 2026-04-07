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


def run_deterministic_checks(
    code: str,
    parameters: dict[str, tuple[float, str]],
    mesh_paths: tuple[str, ...] = (),
    domain: str = "universal",
) -> ValidationReport:
    """Run all 6 deterministic physics checks in cost order.

    Stops at the first check that produces an ERROR-level result.
    WARNINGs and INFOs are accumulated but do not halt the pipeline.

    Args:
        code: Python source code of the simulation to analyze.
        parameters: Mapping of parameter name to (magnitude, unit_string).
        mesh_paths: Tuple of file paths to mesh files for quality checking.
        domain: Physics domain for range checking (default "universal").

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

    return _make_report(all_results, start)
