"""Tests for format_reference_code_context in agentsim.physics.context.

Verifies that the reference implementation guide formatter produces
useful, non-empty output from real YAML data and handles missing
fields gracefully.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentsim.physics.context import format_reference_code_context
from agentsim.physics.domains.schema import (
    AlgorithmKnowledge,
    ParadigmKnowledge,
    SensorClass,
    SpatialParameters,
    TimingParameters,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DOMAINS_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agentsim"
    / "physics"
    / "domains"
    / "nlos_transient_imaging"
)


# ---------------------------------------------------------------------------
# Fixtures — load real YAML data
# ---------------------------------------------------------------------------


@pytest.fixture()
def lct_algorithm() -> AlgorithmKnowledge:
    """Load LCT algorithm from YAML."""
    with open(_DOMAINS_DIR / "algorithms" / "lct.yaml") as f:
        data = yaml.safe_load(f)
    return AlgorithmKnowledge(**data)


@pytest.fixture()
def spad_array_sensor() -> SensorClass:
    """Load SPAD array sensor class from YAML."""
    with open(_DOMAINS_DIR / "sensors" / "spad_array.yaml") as f:
        data = yaml.safe_load(f)
    return SensorClass(**data)


@pytest.fixture()
def relay_wall_paradigm() -> ParadigmKnowledge:
    """Load relay_wall paradigm from YAML."""
    with open(_DOMAINS_DIR / "paradigms" / "relay_wall.yaml") as f:
        data = yaml.safe_load(f)
    return ParadigmKnowledge(**data)


# ---------------------------------------------------------------------------
# Tests: non-empty output with real YAML data
# ---------------------------------------------------------------------------


class TestReferenceContextWithRealData:
    """Tests using real NLOS domain YAML files."""

    def test_produces_nonempty_output(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Reference context with both sensor and algorithm is non-empty."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert result
        assert len(result) > 50

    def test_contains_algorithm_reference(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes the algorithm reference citation."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "O'Toole et al. 2018" in result

    def test_contains_parameter_ranges(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes parameter ranges from algorithm YAML."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "wall_sampling_points" in result
        assert "temporal_bins" in result
        assert "min=" in result
        assert "max=" in result
        assert "typical=" in result

    def test_contains_input_requirements(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes input requirements from algorithm YAML."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "confocal_scanning" in result

    def test_contains_output_characteristics(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes output characteristics from algorithm YAML."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "Lambertian" in result or "depth resolution" in result.lower()

    def test_contains_sensor_timing(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes sensor timing ranges."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "Temporal resolution" in result
        assert "ps" in result

    def test_contains_sensor_tradeoffs(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output includes sensor tradeoff information."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "Tradeoffs" in result

    def test_with_paradigm_adds_usage_note(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
        relay_wall_paradigm: ParadigmKnowledge,
    ) -> None:
        """Including a paradigm adds a usage guidance note."""
        result = format_reference_code_context(
            spad_array_sensor, lct_algorithm, relay_wall_paradigm,
        )
        assert "relay_wall" in result
        assert "paradigm" in result.lower()

    def test_contains_section_header(
        self,
        spad_array_sensor: SensorClass,
        lct_algorithm: AlgorithmKnowledge,
    ) -> None:
        """Output starts with the Reference Implementation Guide header."""
        result = format_reference_code_context(spad_array_sensor, lct_algorithm)
        assert "### Reference Implementation Guide" in result


# ---------------------------------------------------------------------------
# Tests: missing / partial fields
# ---------------------------------------------------------------------------


class TestReferenceContextMissingFields:
    """Tests for graceful handling of missing or partial data."""

    def test_both_none_returns_empty(self) -> None:
        """Both sensor and algorithm None returns empty string."""
        assert format_reference_code_context(None, None) == ""

    def test_algorithm_only(self, lct_algorithm: AlgorithmKnowledge) -> None:
        """Algorithm without sensor produces non-empty output."""
        result = format_reference_code_context(None, lct_algorithm)
        assert result
        assert "Light Cone Transform" in result

    def test_sensor_only(self, spad_array_sensor: SensorClass) -> None:
        """Sensor without algorithm produces non-empty output."""
        result = format_reference_code_context(spad_array_sensor, None)
        assert result
        assert "SPAD" in result

    def test_minimal_algorithm(self) -> None:
        """Algorithm with only name field still produces output."""
        minimal = AlgorithmKnowledge(name="TestAlgo")
        result = format_reference_code_context(None, minimal)
        assert "TestAlgo" in result
        assert "### Reference Implementation Guide" in result

    def test_minimal_sensor(self) -> None:
        """Sensor with only required fields still produces output."""
        minimal = SensorClass(
            name="test_sensor",
            timing_range=TimingParameters(),
            spatial_range=SpatialParameters(array_size=(32, 32), pixel_pitch_um=10.0),
        )
        result = format_reference_code_context(minimal, None)
        assert "test_sensor" in result

    def test_algorithm_no_parameters(self) -> None:
        """Algorithm with no parameters dict doesn't crash."""
        algo = AlgorithmKnowledge(
            name="NoParams",
            reference="Smith 2024",
            description="An algorithm with no parameter ranges defined.",
        )
        result = format_reference_code_context(None, algo)
        assert "Smith 2024" in result
        assert "Parameter ranges" not in result

    def test_sensor_no_timing(self) -> None:
        """Sensor with no timing_range produces output without timing section."""
        sensor = SensorClass(name="bare_sensor")
        result = format_reference_code_context(sensor, None)
        assert "bare_sensor" in result
        assert "Timing parameters" not in result

    def test_paradigm_ignored_when_both_missing(self) -> None:
        """Paradigm alone with no sensor/algorithm returns empty."""
        paradigm = ParadigmKnowledge(paradigm="test_paradigm", domain="test")
        assert format_reference_code_context(None, None, paradigm) == ""
