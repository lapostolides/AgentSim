"""Tests for generic context formatters in agentsim.physics.context.

Verifies that formatters render any domain/paradigm/sensor combination
into prompt text without paradigm-specific code paths.
"""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from agentsim.physics.domains.schema import (
    DomainKnowledge,
    ParadigmKnowledge,
    SensorCatalog,
)
from agentsim.physics.context import (
    format_analysis_context,
    format_hypothesis_context,
    format_physics_context,
    format_scene_context,
)


# ---------------------------------------------------------------------------
# Fixtures — load real YAML data
# ---------------------------------------------------------------------------

_DOMAINS_DIR = Path(__file__).resolve().parents[2] / "src" / "agentsim" / "physics" / "domains"


@pytest.fixture()
def nlos_domain() -> DomainKnowledge:
    """Load NLOS domain knowledge from YAML."""
    with open(_DOMAINS_DIR / "nlos.yaml") as f:
        data = yaml.safe_load(f)
    return DomainKnowledge(**data)


@pytest.fixture()
def relay_wall_paradigm() -> ParadigmKnowledge:
    """Load relay_wall paradigm from YAML."""
    with open(_DOMAINS_DIR / "paradigms" / "relay_wall.yaml") as f:
        data = yaml.safe_load(f)
    return ParadigmKnowledge(**data)


@pytest.fixture()
def penumbra_paradigm() -> ParadigmKnowledge:
    """Load penumbra paradigm from YAML."""
    with open(_DOMAINS_DIR / "paradigms" / "penumbra.yaml") as f:
        data = yaml.safe_load(f)
    return ParadigmKnowledge(**data)


@pytest.fixture()
def sensor_catalog() -> SensorCatalog:
    """Load sensor catalog from YAML."""
    with open(_DOMAINS_DIR / "sensors.yaml") as f:
        data = yaml.safe_load(f)
    return SensorCatalog(**data)


# ---------------------------------------------------------------------------
# Test 1: format_physics_context with domain only
# ---------------------------------------------------------------------------


class TestFormatPhysicsContext:
    """Tests for the base format_physics_context formatter."""

    def test_domain_only_contains_equations(
        self, nlos_domain: DomainKnowledge
    ) -> None:
        """Test 1: domain-only output contains governing equation names."""
        result = format_physics_context(nlos_domain)
        assert "transient_transport" in result or "Transient" in result.title()
        assert "nlos_transient_imaging" in result

    def test_with_paradigm_includes_geometry(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
    ) -> None:
        """Test 2: paradigm adds geometry constraints."""
        result = format_physics_context(nlos_domain, paradigm=relay_wall_paradigm)
        assert "geometry" in result.lower()
        assert "relay_wall" in result.lower() or "Relay" in result

    def test_with_sensor_catalog_includes_sensors(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
        sensor_catalog: SensorCatalog,
    ) -> None:
        """Test 3: sensor catalog adds sensor parameters."""
        result = format_physics_context(
            nlos_domain, paradigm=relay_wall_paradigm, sensor_catalog=sensor_catalog
        )
        assert "sensor" in result.lower()
        assert "SwissSPAD2" in result or "swissspad2" in result.lower()

    def test_with_paradigm_includes_transfer_functions(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
    ) -> None:
        """Test 11: paradigm output includes transfer functions section."""
        result = format_physics_context(nlos_domain, paradigm=relay_wall_paradigm)
        assert "transfer" in result.lower()
        assert "temporal_resolution_ps" in result or "spatial_resolution_m" in result

    def test_returns_empty_for_none_domain(self) -> None:
        """format_physics_context returns empty string for None domain."""
        result = format_physics_context(None)
        assert result == ""


# ---------------------------------------------------------------------------
# Test 4-5: format_hypothesis_context
# ---------------------------------------------------------------------------


class TestFormatHypothesisContext:
    """Tests for the hypothesis-specific formatter."""

    def test_relay_wall_includes_physics(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
    ) -> None:
        """Test 4: hypothesis context includes equations, dimensionless groups,
        geometry constraints, and reconstruction algorithms."""
        result = format_hypothesis_context(nlos_domain, paradigm=relay_wall_paradigm)
        assert "Hypothesis" in result
        assert "governing" in result.lower() or "equation" in result.lower()
        assert "dimensionless" in result.lower() or "Nyquist" in result
        assert "geometry" in result.lower()
        assert "reconstruction" in result.lower() or "algorithm" in result.lower()

    def test_penumbra_also_works(
        self,
        nlos_domain: DomainKnowledge,
        penumbra_paradigm: ParadigmKnowledge,
    ) -> None:
        """Test 5: hypothesis context works for penumbra paradigm too."""
        result = format_hypothesis_context(nlos_domain, paradigm=penumbra_paradigm)
        assert "Hypothesis" in result
        assert "penumbra" in result.lower()
        # Should still have domain-level equations
        assert "transient_transport" in result or "transport" in result.lower()


# ---------------------------------------------------------------------------
# Test 6-7: format_analysis_context
# ---------------------------------------------------------------------------


class TestFormatAnalysisContext:
    """Tests for the analysis-specific formatter."""

    def test_with_paradigm_includes_validation(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
    ) -> None:
        """Test 6: analysis context includes signal physics and reconstruction
        quality checks."""
        result = format_analysis_context(nlos_domain, paradigm=relay_wall_paradigm)
        assert "Analysis" in result
        assert "signal" in result.lower() or "falloff" in result.lower()
        assert "reconstruction" in result.lower() or "algorithm" in result.lower()

    def test_without_paradigm_still_useful(
        self, nlos_domain: DomainKnowledge
    ) -> None:
        """Test 7: analysis context without paradigm still produces useful output."""
        result = format_analysis_context(nlos_domain)
        assert "Analysis" in result
        assert len(result) > 100  # Non-trivial output


# ---------------------------------------------------------------------------
# Test 8-9: format_scene_context
# ---------------------------------------------------------------------------


class TestFormatSceneContext:
    """Tests for the scene-specific formatter (D-06 compliance)."""

    def test_includes_all_d06_sections(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
        sensor_catalog: SensorCatalog,
    ) -> None:
        """Test 8: scene context includes geometry, sensors, baselines,
        reconstruction, transfer functions per D-06."""
        result = format_scene_context(
            nlos_domain, paradigm=relay_wall_paradigm, sensor_catalog=sensor_catalog
        )
        assert "Scene" in result
        assert "geometry" in result.lower()
        assert "sensor" in result.lower()
        assert "baseline" in result.lower() or "published" in result.lower()
        assert "reconstruction" in result.lower() or "algorithm" in result.lower()
        assert "transfer" in result.lower()

    def test_returns_empty_for_none_domain(self) -> None:
        """Test 9: scene context returns empty for None domain."""
        result = format_scene_context(None)
        assert result == ""


# ---------------------------------------------------------------------------
# Test 10: All formatters produce pure strings
# ---------------------------------------------------------------------------


class TestPurity:
    """Verify formatters produce pure strings with no side effects."""

    def test_all_return_strings(
        self,
        nlos_domain: DomainKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
        sensor_catalog: SensorCatalog,
    ) -> None:
        """Test 10: every formatter returns str."""
        results = [
            format_physics_context(nlos_domain),
            format_physics_context(
                nlos_domain,
                paradigm=relay_wall_paradigm,
                sensor_catalog=sensor_catalog,
            ),
            format_hypothesis_context(nlos_domain, paradigm=relay_wall_paradigm),
            format_analysis_context(nlos_domain, paradigm=relay_wall_paradigm),
            format_scene_context(
                nlos_domain,
                paradigm=relay_wall_paradigm,
                sensor_catalog=sensor_catalog,
            ),
        ]
        for r in results:
            assert isinstance(r, str)
            assert len(r) > 0
