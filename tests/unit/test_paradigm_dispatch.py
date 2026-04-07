"""Tests for paradigm-dispatched validation in checker.py.

Verifies that run_paradigm_checks dispatches python_check and range_check
rules from paradigm YAML declarations, and that run_deterministic_checks
backward compatibility is preserved.
"""

from __future__ import annotations

from unittest.mock import patch

from agentsim.physics.domains import load_paradigm
from agentsim.physics.models import Severity, ValidationReport


# ---------------------------------------------------------------------------
# Valid scene params for relay_wall paradigm python_checks
# ---------------------------------------------------------------------------

VALID_RELAY_WALL_PARAMS: dict = {
    "sensor_pos": (0, -1.5, 0),
    "sensor_look_at": (0, 0, 0),
    "relay_wall_pos": (0, 0, 0),
    "relay_wall_normal": (0, -1, 0),
    "relay_wall_size": 2.0,
    "hidden_objects": ((0, 1, 0),),
    "sensor_fov_deg": 20.0,
}

VALID_PENUMBRA_PARAMS: dict = {
    "aperture_width": 0.05,
    "occluder_to_wall_distance": 0.5,
    "scene_to_occluder_distance": 1.0,
}

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


class TestRunParadigmChecks:
    """Test run_paradigm_checks dispatches validation rules from paradigm YAML."""

    def test_relay_wall_valid_scene_passes(self) -> None:
        """Test 1: run_paradigm_checks with relay_wall and valid params passes."""
        from agentsim.physics.checker import run_paradigm_checks

        paradigm = load_paradigm("relay_wall")
        assert paradigm is not None
        report = run_paradigm_checks(paradigm, VALID_RELAY_WALL_PARAMS)
        assert isinstance(report, ValidationReport)
        assert report.passed is True

    def test_relay_wall_dispatches_three_bounce(self) -> None:
        """Test 2: run_paradigm_checks dispatches check_three_bounce_geometry."""
        from agentsim.physics.checker import run_paradigm_checks

        paradigm = load_paradigm("relay_wall")
        assert paradigm is not None
        report = run_paradigm_checks(paradigm, VALID_RELAY_WALL_PARAMS)
        checks_present = {r.check for r in report.results}
        assert "nlos_three_bounce" in checks_present

    def test_range_check_wall_size_too_large(self) -> None:
        """Test 3: range_check triggers error for wall_size=15 (max=10)."""
        from agentsim.physics.checker import run_paradigm_checks

        paradigm = load_paradigm("relay_wall")
        assert paradigm is not None
        oversized_params = {**VALID_RELAY_WALL_PARAMS, "relay_wall_size": 15.0}
        report = run_paradigm_checks(paradigm, oversized_params)
        # Should have a range_check error for wall_size_range rule
        range_errors = [
            r for r in report.results
            if r.check == "wall_size_range" and r.severity == Severity.ERROR
        ]
        assert len(range_errors) > 0

    def test_penumbra_valid_params_passes(self) -> None:
        """Test 4: run_paradigm_checks with penumbra and valid params passes."""
        from agentsim.physics.checker import run_paradigm_checks

        paradigm = load_paradigm("penumbra")
        assert paradigm is not None
        report = run_paradigm_checks(paradigm, VALID_PENUMBRA_PARAMS)
        assert isinstance(report, ValidationReport)
        assert report.passed is True

    def test_unknown_module_logs_warning_no_crash(self) -> None:
        """Test 5: python_check with unknown module logs warning, continues."""
        from agentsim.physics.checker import run_paradigm_checks
        from agentsim.physics.domains.schema import ParadigmKnowledge, ValidationRule

        bad_rule = ValidationRule(
            name="bad_check",
            type="python_check",
            module="nonexistent.module",
            function="check_something",
        )
        fake_paradigm = ParadigmKnowledge(
            paradigm="test_paradigm",
            domain="test_domain",
            validation_rules=(bad_rule,),
        )
        # Should not raise, should log warning and continue
        report = run_paradigm_checks(fake_paradigm, {})
        assert isinstance(report, ValidationReport)
        # The bad check should produce a warning result
        warning_results = [
            r for r in report.results if r.severity == Severity.WARNING
        ]
        assert len(warning_results) > 0


class TestDeterministicChecksBackwardCompat:
    """Test run_deterministic_checks backward compatibility."""

    def test_paradigm_knowledge_dispatches_paradigm_checks(self) -> None:
        """Test 6: paradigm_knowledge param dispatches run_paradigm_checks."""
        from agentsim.physics.checker import run_deterministic_checks

        paradigm = load_paradigm("relay_wall")
        report = run_deterministic_checks(
            code=VALID_CODE,
            parameters=VALID_PARAMS,
            paradigm_knowledge=paradigm,
            nlos_scene_params=VALID_RELAY_WALL_PARAMS,
        )
        assert isinstance(report, ValidationReport)
        # Should contain paradigm-dispatched checks
        checks_present = {r.check for r in report.results}
        assert "nlos_three_bounce" in checks_present

    def test_backward_compat_nlos_scene_params(self) -> None:
        """Test 7: nlos_scene_params still works when paradigm_knowledge is None."""
        from agentsim.physics.checker import run_deterministic_checks

        report = run_deterministic_checks(
            code=VALID_CODE,
            parameters=VALID_PARAMS,
            domain="nlos_transient_imaging",
            nlos_scene_params=VALID_RELAY_WALL_PARAMS,
        )
        assert isinstance(report, ValidationReport)
        nlos_checks = {r.check for r in report.results if r.check.startswith("nlos_")}
        assert len(nlos_checks) > 0

    def test_existing_checker_pipeline_regression(self) -> None:
        """Test 8: Existing pipeline without paradigm_knowledge still passes."""
        from agentsim.physics.checker import run_deterministic_checks

        report = run_deterministic_checks(
            code=VALID_CODE,
            parameters=VALID_PARAMS,
        )
        assert isinstance(report, ValidationReport)
        assert report.passed is True
