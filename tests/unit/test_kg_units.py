"""Tests for knowledge graph unit validation helpers."""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.units import CANONICAL_UNITS, validate_unit


class TestValidateUnitAngle:
    """Tests for angle category validation."""

    def test_validate_unit_angle_correct_degree(self) -> None:
        assert validate_unit("degree", "angle") is None

    def test_validate_unit_angle_correct_radian(self) -> None:
        assert validate_unit("radian", "angle") is None

    def test_validate_unit_angle_wrong_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensionality"):
            validate_unit("meter", "angle")


class TestValidateUnitTime:
    """Tests for time category validation."""

    def test_validate_unit_time_picosecond(self) -> None:
        assert validate_unit("picosecond", "time") is None

    def test_validate_unit_time_wrong_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensionality"):
            validate_unit("meter", "time")


class TestValidateUnitLength:
    """Tests for length category validation."""

    def test_validate_unit_length_meter(self) -> None:
        assert validate_unit("meter", "length") is None


class TestValidateUnitFrequency:
    """Tests for frequency category validation."""

    def test_validate_unit_frequency_hertz(self) -> None:
        assert validate_unit("hertz", "frequency") is None

    def test_validate_unit_frequency_wrong_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensionality"):
            validate_unit("degree", "frequency")


class TestValidateUnitPower:
    """Tests for power category validation."""

    def test_validate_unit_power_watt(self) -> None:
        assert validate_unit("watt", "power") is None


class TestValidateUnitTemperature:
    """Tests for temperature category validation."""

    def test_validate_unit_temperature_kelvin(self) -> None:
        assert validate_unit("kelvin", "temperature") is None


class TestValidateUnitSkipCategories:
    """Tests for categories that skip Pint validation."""

    def test_validate_unit_currency_skips(self) -> None:
        assert validate_unit("USD", "currency") is None

    def test_validate_unit_ratio_skips(self) -> None:
        assert validate_unit("dimensionless", "ratio") is None


class TestValidateUnitUnknown:
    """Tests for unknown unit strings."""

    def test_validate_unit_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown unit"):
            validate_unit("nonsense_unit", "time")


class TestValidateUnitWrongDimension:
    """Combined wrong-dimension tests."""

    def test_validate_unit_wrong_dimension_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_unit("meter", "angle")


class TestCanonicalUnits:
    """Tests for the CANONICAL_UNITS mapping."""

    def test_canonical_units_keys(self) -> None:
        expected_keys = {
            "time", "angle", "length", "frequency", "ratio",
            "power", "mass", "currency", "temperature", "voltage",
        }
        assert set(CANONICAL_UNITS.keys()) == expected_keys

    def test_canonical_units_time(self) -> None:
        assert CANONICAL_UNITS["time"] == "picosecond"

    def test_canonical_units_angle(self) -> None:
        assert CANONICAL_UNITS["angle"] == "degree"

    def test_canonical_units_length(self) -> None:
        assert CANONICAL_UNITS["length"] == "meter"
