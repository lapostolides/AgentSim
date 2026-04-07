"""Tests for domain knowledge Pydantic schema and NLOS YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentsim.physics.domains.schema import (
    DimensionlessGroup,
    DomainKnowledge,
    GeometryConstraint,
    GoverningEquation,
    PublishedParameterSet,
    ReconstructionAlgorithm,
    SensorParameters,
)

_NLOS_YAML = Path(__file__).resolve().parents[2] / "src" / "agentsim" / "physics" / "domains" / "nlos.yaml"


def _load_nlos() -> DomainKnowledge:
    """Load NLOS YAML and validate into DomainKnowledge."""
    with open(_NLOS_YAML) as f:
        raw = yaml.safe_load(f)
    return DomainKnowledge.model_validate(raw)


class TestSchemaModels:
    """Test individual Pydantic schema models."""

    def test_domain_knowledge_minimal(self) -> None:
        """Test 1: DomainKnowledge.model_validate on minimal dict."""
        data = {"domain": "test_domain", "version": "1.0", "description": "A test domain"}
        dk = DomainKnowledge.model_validate(data)
        assert dk.domain == "test_domain"
        assert dk.version == "1.0"
        assert dk.description == "A test domain"

    def test_governing_equation_validates(self) -> None:
        """Test 2: GoverningEquation model validates with required fields."""
        eq = GoverningEquation.model_validate({
            "name": "navier_stokes",
            "latex": "\\nabla \\cdot v = 0",
            "description": "Incompressible continuity",
            "variables": {"v": "velocity field"},
        })
        assert eq.name == "navier_stokes"
        assert eq.variables["v"] == "velocity field"

    def test_reconstruction_algorithm_validates(self) -> None:
        """Test 3: ReconstructionAlgorithm model validates."""
        alg = ReconstructionAlgorithm.model_validate({
            "name": "Light Cone Transform",
            "reference": "O'Toole et al. 2018",
            "requires_confocal": True,
            "parameters": {},
        })
        assert alg.name == "Light Cone Transform"
        assert alg.requires_confocal is True

    def test_published_parameter_set_validates(self) -> None:
        """Test 4: PublishedParameterSet model validates."""
        pps = PublishedParameterSet.model_validate({
            "paper": "Confocal NLOS via LCT",
            "venue": "Nature 2018",
            "wall_size_m": 2.0,
            "scan_resolution": "512x512",
            "temporal_bins": 2048,
            "temporal_resolution_ps": 32.0,
        })
        assert pps.paper == "Confocal NLOS via LCT"
        assert pps.wall_size_m == 2.0
        assert pps.temporal_bins == 2048


class TestNLOSYaml:
    """Test NLOS YAML content loaded into typed models."""

    def test_full_yaml_loads(self) -> None:
        """Test 5: Full NLOS YAML loads without errors."""
        dk = _load_nlos()
        assert dk.domain == "nlos_transient_imaging"
        assert dk.version == "1.0"

    def test_published_parameter_index_has_four_papers(self) -> None:
        """Test 6: Published parameter index has >= 4 entries."""
        dk = _load_nlos()
        expected_keys = {"otoole_2018", "lindell_2019", "liu_2019", "nam_2021"}
        assert expected_keys.issubset(set(dk.published_parameter_index.keys()))
        assert len(dk.published_parameter_index) >= 4

    def test_governing_equations_has_transient_transport(self) -> None:
        """Test 7: Governing equations contains transient_transport."""
        dk = _load_nlos()
        eq_names = {eq.name for eq in dk.governing_equations}
        assert "transient_transport" in eq_names

    def test_reconstruction_algorithms_present(self) -> None:
        """Test 8: Reconstruction algorithms include lct, fk_migration, phasor_fields."""
        dk = _load_nlos()
        assert "lct" in dk.reconstruction_algorithms
        assert "fk_migration" in dk.reconstruction_algorithms
        assert "phasor_fields" in dk.reconstruction_algorithms

    def test_spad_sensor_parameters(self) -> None:
        """Test 9: SPAD sensor parameters present with required fields."""
        dk = _load_nlos()
        assert dk.sensor_parameters is not None
        spad = dk.sensor_parameters.spad
        assert spad is not None
        assert spad.temporal_resolution_ps is not None
        assert spad.jitter_ps is not None
        assert spad.dead_time_ns is not None
        assert spad.fov_degrees is not None
        assert spad.scan_points is not None

    def test_geometry_constraints_present(self) -> None:
        """Test 10: Geometry constraints have three_bounce_path and relay_wall."""
        dk = _load_nlos()
        gc = dk.geometry_constraints
        assert gc is not None
        assert gc.three_bounce_path is not None
        assert len(gc.three_bounce_path.requirements) >= 4
        assert gc.relay_wall is not None
