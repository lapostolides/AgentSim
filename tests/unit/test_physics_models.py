"""Tests for physics data models, state extensions, and transitions.

Verifies that all physics models are frozen Pydantic models,
ExperimentState has physics fields, and transitions work correctly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pint
import pytest

from agentsim.physics.models import (
    ASTExtractionResult,
    CheckResult,
    ConsultationLogEntry,
    ExtractedParameter,
    ExtractedSimulationParams,
    PhysicalConstant,
    PhysicalParameter,
    PhysicsConsultationSummary,
    PhysicsGuidance,
    PhysicsQuery,
    PhysicsValidation,
    Severity,
    ValidationReport,
    _ureg,
)
from agentsim.orchestrator.gates import ALL_CHECKPOINTS, GateCheckpoint
from agentsim.state.models import ExperimentState, ExperimentStatus
from agentsim.state.transitions import (
    add_physics_validation,
    set_consultation_summary,
)


# -- Severity enum --

class TestSeverity:
    def test_severity_values(self) -> None:
        assert Severity.ERROR == "error"
        assert Severity.WARNING == "warning"
        assert Severity.INFO == "info"


# -- CheckResult --

class TestCheckResult:
    def test_frozen_and_serializable(self) -> None:
        result = CheckResult(
            check="unit_check",
            severity=Severity.ERROR,
            message="Bad unit",
            parameter="velocity",
            details="Expected m/s",
        )
        assert result.severity == Severity.ERROR
        d = result.model_dump()
        assert d["check"] == "unit_check"
        assert d["severity"] == "error"

        with pytest.raises(Exception):
            result.check = "something_else"  # type: ignore[misc]


# -- PhysicalConstant --

class TestPhysicalConstant:
    def test_magnitude_and_unit_separate_fields(self) -> None:
        c = PhysicalConstant(
            name="speed_of_light",
            symbol="c",
            magnitude=299792458.0,
            unit="meter / second",
        )
        assert c.magnitude == 299792458.0
        assert c.unit == "meter / second"
        assert c.domain == "universal"

    def test_frozen(self) -> None:
        c = PhysicalConstant(
            name="test", symbol="t", magnitude=1.0, unit="meter"
        )
        with pytest.raises(Exception):
            c.name = "changed"  # type: ignore[misc]


# -- PhysicalParameter --

class TestPhysicalParameter:
    def test_to_quantity_returns_pint(self) -> None:
        p = PhysicalParameter(name="speed", magnitude=10.0, unit="meter / second")
        q = p.to_quantity()
        assert isinstance(q, pint.Quantity)
        assert q.magnitude == 10.0
        assert str(q.units) == "meter / second"

    def test_from_quantity_roundtrip(self) -> None:
        q = _ureg.Quantity(3.14, "kilogram")
        p = PhysicalParameter.from_quantity("mass", q, description="test mass")
        assert p.name == "mass"
        assert p.magnitude == pytest.approx(3.14)
        assert p.unit == "kilogram"
        assert p.description == "test mass"

        # Round-trip
        q2 = p.to_quantity()
        assert q2.magnitude == pytest.approx(q.magnitude)


# -- ValidationReport --

class TestValidationReport:
    def test_failed_report_contains_errors(self) -> None:
        results = (
            CheckResult(check="a", severity=Severity.ERROR, message="bad"),
            CheckResult(check="b", severity=Severity.INFO, message="ok"),
        )
        report = ValidationReport(results=results, passed=False, duration_seconds=0.1)
        assert not report.passed
        assert len(report.results) == 2
        assert report.results[0].severity == Severity.ERROR


# -- PhysicsValidation --

class TestPhysicsValidation:
    def test_references_scene_id(self) -> None:
        report = ValidationReport(results=(), passed=True)
        pv = PhysicsValidation(scene_id="scene_001", report=report)
        assert pv.scene_id == "scene_001"
        assert pv.report.passed
        assert isinstance(pv.timestamp, datetime)


# -- PhysicsConsultationSummary --

class TestPhysicsConsultationSummary:
    def test_tracks_counts(self) -> None:
        s = PhysicsConsultationSummary(
            total_consultations=5,
            domains_consulted=("fluids", "optics"),
            total_errors=2,
            total_warnings=1,
        )
        assert s.total_consultations == 5
        assert len(s.domains_consulted) == 2
        assert s.total_errors == 2


# -- ExtractedParameter and related --

class TestExtractedModels:
    def test_extracted_parameter_frozen(self) -> None:
        ep = ExtractedParameter(name="dt", value=0.001, line=42, unit_hint="second")
        assert ep.name == "dt"
        with pytest.raises(Exception):
            ep.value = 0.002  # type: ignore[misc]

    def test_extracted_simulation_params_frozen(self) -> None:
        esp = ExtractedSimulationParams(
            parameters=(
                ExtractedParameter(name="dt", value=0.001, line=1),
            ),
            solver_type="euler",
            velocity=10.0,
            timestep=0.001,
        )
        assert esp.solver_type == "euler"
        assert len(esp.parameters) == 1
        with pytest.raises(Exception):
            esp.solver_type = "rk4"  # type: ignore[misc]

    def test_ast_extraction_result_frozen(self) -> None:
        params = ExtractedSimulationParams()
        ast_result = ASTExtractionResult(params=params)
        assert len(ast_result.issues) == 0
        with pytest.raises(Exception):
            ast_result.params = params  # type: ignore[misc]


# -- PhysicsQuery and PhysicsGuidance --

class TestQueryGuidance:
    def test_physics_query_frozen(self) -> None:
        q = PhysicsQuery(query_type="domain_check", context="fluids sim")
        assert q.query_type == "domain_check"

    def test_physics_guidance_frozen(self) -> None:
        g = PhysicsGuidance(
            domain_detected="fluids",
            confidence=0.9,
            recommendations=("Use k-epsilon",),
            warnings=("High Re",),
        )
        assert g.confidence == 0.9

    def test_consultation_log_entry_frozen(self) -> None:
        q = PhysicsQuery(query_type="check", context="test")
        g = PhysicsGuidance()
        entry = ConsultationLogEntry(query=q, response=g, domain="fluids")
        assert entry.domain == "fluids"
        assert isinstance(entry.timestamp, datetime)


# -- ExperimentState extensions --

class TestExperimentStateExtensions:
    def test_has_physics_validations_field(self) -> None:
        state = ExperimentState(raw_hypothesis="test")
        assert state.physics_validations == ()

    def test_has_consultation_summary_field(self) -> None:
        state = ExperimentState(raw_hypothesis="test")
        assert state.consultation_summary is None

    def test_physics_validated_status_exists(self) -> None:
        assert hasattr(ExperimentStatus, "PHYSICS_VALIDATED")
        assert ExperimentStatus.PHYSICS_VALIDATED == "physics_validated"

    def test_physics_validated_between_scenes_ready_and_executed(self) -> None:
        values = [e.value for e in ExperimentStatus]
        scenes_idx = values.index("scenes_ready")
        physics_idx = values.index("physics_validated")
        executed_idx = values.index("executed")
        assert scenes_idx < physics_idx < executed_idx


# -- GateCheckpoint extension --

class TestGateCheckpointExtension:
    def test_post_physics_validation_exists(self) -> None:
        assert hasattr(GateCheckpoint, "POST_PHYSICS_VALIDATION")
        assert GateCheckpoint.POST_PHYSICS_VALIDATION == "post_physics_validation"

    def test_all_checkpoints_includes_physics(self) -> None:
        assert "post_physics_validation" in ALL_CHECKPOINTS


# -- Transitions --

class TestPhysicsTransitions:
    def test_add_physics_validation(self) -> None:
        state = ExperimentState(raw_hypothesis="test")
        report = ValidationReport(results=(), passed=True)
        validation = PhysicsValidation(scene_id="s1", report=report)

        new_state = add_physics_validation(state, validation)

        assert new_state is not state
        assert len(new_state.physics_validations) == 1
        assert new_state.physics_validations[0].scene_id == "s1"
        assert new_state.status == ExperimentStatus.PHYSICS_VALIDATED

    def test_add_physics_validation_appends(self) -> None:
        state = ExperimentState(raw_hypothesis="test")
        report = ValidationReport(results=(), passed=True)

        state2 = add_physics_validation(
            state, PhysicsValidation(scene_id="s1", report=report)
        )
        state3 = add_physics_validation(
            state2, PhysicsValidation(scene_id="s2", report=report)
        )

        assert len(state3.physics_validations) == 2
        assert state3.physics_validations[0].scene_id == "s1"
        assert state3.physics_validations[1].scene_id == "s2"

    def test_set_consultation_summary(self) -> None:
        state = ExperimentState(raw_hypothesis="test")
        summary = PhysicsConsultationSummary(
            total_consultations=3,
            domains_consulted=("fluids",),
            total_errors=1,
        )

        new_state = set_consultation_summary(state, summary)

        assert new_state is not state
        assert new_state.consultation_summary is not None
        assert new_state.consultation_summary.total_consultations == 3
        # Should not change status
        assert new_state.status == state.status
