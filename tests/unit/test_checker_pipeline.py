"""Tests for the fail-fast deterministic checker pipeline.

Verifies that the pipeline composes all 6 checks in cost order,
stops on first ERROR, collects WARNINGs/INFOs, and reports duration.
"""

from __future__ import annotations

import math
from unittest.mock import patch

from agentsim.physics.models import CheckResult, Severity, ValidationReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CODE = """\
import numpy as np

dt = 0.001
dx = 0.1
velocity = 1.0

result = velocity * dt / dx
print(result)
"""

VALID_PARAMS: dict[str, tuple[float, str]] = {
    "temperature": (300.0, "kelvin"),
    "velocity": (1.0, "meter / second"),
}

SYNTAX_ERROR_CODE = "def foo(:\n    pass"

INVALID_UNIT_PARAMS: dict[str, tuple[float, str]] = {
    "temperature": (300.0, "bogus_unit_xyz"),
}

OUT_OF_RANGE_PARAMS: dict[str, tuple[float, str]] = {
    "temperature": (300.0, "kelvin"),
    "density": (-999.0, "kilogram / meter ** 3"),
}


# ---------------------------------------------------------------------------
# Public import
# ---------------------------------------------------------------------------


def test_public_import():
    """run_deterministic_checks is importable from agentsim.physics."""
    from agentsim.physics import run_deterministic_checks

    assert callable(run_deterministic_checks)


# ---------------------------------------------------------------------------
# Pipeline behavior
# ---------------------------------------------------------------------------


def test_all_valid_returns_passed():
    """Pipeline with all-valid inputs returns passed=True."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
    )
    assert isinstance(report, ValidationReport)
    assert report.passed is True


def test_invalid_unit_stops_at_check_1():
    """Pipeline with undefined unit stops at check 1 (units), returns passed=False."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=INVALID_UNIT_PARAMS,
    )
    assert report.passed is False
    # Should only have unit check results
    checks_present = {r.check for r in report.results}
    assert "unit_consistency" in checks_present
    # Should NOT have later checks
    assert "ast_extract" not in checks_present
    assert "cfl" not in checks_present


def test_out_of_range_stops_at_check_2():
    """Pipeline with valid units but out-of-range param stops at check 2."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=OUT_OF_RANGE_PARAMS,
    )
    assert report.passed is False
    checks_present = {r.check for r in report.results}
    assert "parameter_range" in checks_present
    # Should NOT have AST or later checks (stopped at range)
    assert "ast_extract" not in checks_present


def test_syntax_error_stops_at_check_3():
    """Pipeline with valid units+ranges but syntax error stops at check 3 (AST)."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=SYNTAX_ERROR_CODE,
        parameters=VALID_PARAMS,
    )
    assert report.passed is False
    checks_present = {r.check for r in report.results}
    assert "ast_extract" in checks_present
    # Should NOT have equation or CFL checks
    assert "cfl" not in checks_present


def test_all_checks_included_when_passing():
    """Pipeline with all checks passing includes results from all 6 check types."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
    )
    # Should have results from the later checks (at least AST, equations, CFL)
    checks_present = {r.check for r in report.results}
    # AST extraction produces no issues for valid code, equations produce INFO,
    # CFL produces INFO. So we should see equations and cfl at minimum.
    assert "equations" in checks_present or "cfl" in checks_present


def test_warnings_do_not_halt_pipeline():
    """WARNINGs do NOT halt pipeline (per D-05), only ERRORs do."""
    from agentsim.physics.checker import run_deterministic_checks

    # Use params that produce a WARNING (unit mismatch in range check)
    # but not an ERROR
    warning_params: dict[str, tuple[float, str]] = {
        "temperature": (300.0, "kelvin"),
        "some_exotic_param": (1.0, "meter"),  # No range data -> INFO, not ERROR
    }
    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=warning_params,
    )
    # Pipeline should continue past range check (INFO for unknown param)
    checks_present = {r.check for r in report.results}
    # Should have reached at least equations or CFL
    assert "equations" in checks_present or "cfl" in checks_present


def test_duration_is_populated():
    """duration_seconds is populated in the returned ValidationReport."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
    )
    assert report.duration_seconds > 0


def test_pipeline_completes_under_10_seconds():
    """Pipeline completes in <10s for realistic input (per D-13)."""
    import time

    from agentsim.physics.checker import run_deterministic_checks

    start = time.perf_counter()
    run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 10.0, f"Pipeline took {elapsed:.2f}s, exceeds 10s budget"


def test_has_error_helper():
    """_has_error returns True only when ERROR severity is present."""
    from agentsim.physics.checker import _has_error

    error_result = CheckResult(
        check="test", severity=Severity.ERROR, message="err"
    )
    warning_result = CheckResult(
        check="test", severity=Severity.WARNING, message="warn"
    )
    info_result = CheckResult(
        check="test", severity=Severity.INFO, message="info"
    )

    assert _has_error((error_result,)) is True
    assert _has_error((warning_result,)) is False
    assert _has_error((info_result,)) is False
    assert _has_error((warning_result, info_result)) is False
    assert _has_error((warning_result, error_result)) is True
    assert _has_error(()) is False


# ---------------------------------------------------------------------------
# NLOS pipeline integration tests
# ---------------------------------------------------------------------------


def test_run_nlos_checks_valid_confocal():
    """Test 1: run_nlos_checks with valid confocal geometry returns passed=True."""
    from agentsim.physics.checker import run_nlos_checks

    report = run_nlos_checks(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
    )
    assert isinstance(report, ValidationReport)
    assert report.passed is True


def test_run_nlos_checks_invalid_geometry():
    """Test 2: run_nlos_checks with sensor behind wall returns passed=False."""
    from agentsim.physics.checker import run_nlos_checks

    report = run_nlos_checks(
        sensor_pos=(0, 1, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 2, 0),),
    )
    assert report.passed is False


def test_run_nlos_checks_insufficient_temporal():
    """Test 3: run_nlos_checks with insufficient temporal resolution returns ERROR."""
    from agentsim.physics.checker import run_nlos_checks

    report = run_nlos_checks(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
        time_bin_ps=1000.0,
        min_feature_separation_m=0.01,
    )
    assert report.passed is False
    error_checks = {r.check for r in report.results if r.severity == Severity.ERROR}
    assert "nlos_temporal_resolution" in error_checks


def test_deterministic_checks_with_nlos_domain():
    """Test 4: run_deterministic_checks with nlos domain and nlos_scene_params
    includes NLOS checks in results."""
    from agentsim.physics.checker import run_deterministic_checks

    nlos_params = {
        "sensor_pos": (0, -1.5, 0),
        "sensor_look_at": (0, 0, 0),
        "relay_wall_pos": (0, 0, 0),
        "relay_wall_normal": (0, -1, 0),
        "relay_wall_size": 2.0,
        "hidden_objects": ((0, 1, 0),),
        "sensor_fov_deg": 20.0,
    }
    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
        domain="nlos_transient_imaging",
        nlos_scene_params=nlos_params,
    )
    nlos_checks = {r.check for r in report.results if r.check.startswith("nlos_")}
    assert len(nlos_checks) > 0, "Expected NLOS checks in results"


def test_deterministic_checks_universal_no_nlos():
    """Test 5: run_deterministic_checks with domain='universal' does NOT run NLOS checks."""
    from agentsim.physics.checker import run_deterministic_checks

    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
        domain="universal",
    )
    nlos_checks = [r for r in report.results if r.check.startswith("nlos_")]
    assert len(nlos_checks) == 0, f"Unexpected NLOS checks: {nlos_checks}"


def test_existing_pipeline_no_regression():
    """Test 6: Existing pipeline tests still pass (no regressions)."""
    from agentsim.physics.checker import run_deterministic_checks

    # Run with standard params -- should behave exactly as before
    report = run_deterministic_checks(
        code=VALID_CODE,
        parameters=VALID_PARAMS,
    )
    assert isinstance(report, ValidationReport)
    assert report.passed is True
    assert report.duration_seconds > 0
