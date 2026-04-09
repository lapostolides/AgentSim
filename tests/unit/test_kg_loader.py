"""Tests for knowledge graph sensor loader and ranges models.

Covers YAML loading, type coercion, family filtering, ranges model
construction, and immutability guarantees.
"""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.models import SensorFamily, SensorNode
from agentsim.knowledge_graph.ranges import ParameterRange, SensorFamilyRanges
from agentsim.knowledge_graph.loader import load_family_ranges, load_sensors


# ---------------------------------------------------------------------------
# ParameterRange model
# ---------------------------------------------------------------------------


class TestParameterRange:
    def test_construction(self) -> None:
        pr = ParameterRange(min=10.0, max=100.0, typical=20.0, description="TDC res")
        assert pr.min == 10.0
        assert pr.max == 100.0
        assert pr.typical == 20.0
        assert pr.description == "TDC res"

    def test_defaults(self) -> None:
        pr = ParameterRange()
        assert pr.min is None
        assert pr.max is None
        assert pr.typical is None
        assert pr.unit == ""
        assert pr.description == ""

    def test_frozen(self) -> None:
        pr = ParameterRange(min=1.0)
        with pytest.raises(Exception):
            pr.min = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SensorFamilyRanges model
# ---------------------------------------------------------------------------


class TestSensorFamilyRanges:
    def test_construction(self) -> None:
        sfr = SensorFamilyRanges(
            family=SensorFamily.SPAD,
            display_name="SPAD",
            description="Single-photon detectors",
            ranges={"pde": ParameterRange(min=0.15, max=0.50)},
        )
        assert sfr.family == SensorFamily.SPAD
        assert sfr.display_name == "SPAD"
        assert "pde" in sfr.ranges

    def test_frozen(self) -> None:
        sfr = SensorFamilyRanges(family=SensorFamily.SPAD)
        with pytest.raises(Exception):
            sfr.family = SensorFamily.RGB  # type: ignore[misc]


# ---------------------------------------------------------------------------
# load_sensors()
# ---------------------------------------------------------------------------


class TestLoadSensors:
    def test_returns_tuple(self) -> None:
        result = load_sensors()
        assert isinstance(result, tuple)

    def test_at_least_three_spad_sensors(self) -> None:
        result = load_sensors()
        assert len(result) >= 3

    def test_all_are_sensor_nodes(self) -> None:
        for node in load_sensors():
            assert isinstance(node, SensorNode)

    def test_spad_filter_returns_only_spad(self) -> None:
        result = load_sensors(families=(SensorFamily.SPAD,))
        for node in result:
            assert node.family == SensorFamily.SPAD
        assert len(result) >= 3

    def test_family_filter_returns_only_matching(self) -> None:
        result = load_sensors(families=(SensorFamily.LIDAR_FMCW,))
        assert len(result) >= 2
        for node in result:
            assert node.family == SensorFamily.LIDAR_FMCW

    def test_spad_names_contain_expected(self) -> None:
        sensors = load_sensors(families=(SensorFamily.SPAD,))
        names = {s.name for s in sensors}
        assert "TMF8828" in names
        assert "VL53L8" in names
        assert "MPD PDM Series" in names

    def test_coercion_yaml_int_to_float(self) -> None:
        """Loader must coerce YAML int values to float for family_specs."""
        sensors = load_sensors(families=(SensorFamily.SPAD,))
        for sensor in sensors:
            for key, value in sensor.family_specs.items():
                if isinstance(value, (int, float)) and not isinstance(value, str):
                    assert isinstance(value, float), (
                        f"{sensor.name}.family_specs['{key}'] is {type(value).__name__}, "
                        f"expected float"
                    )

    def test_operational_props_present(self) -> None:
        """All SPAD sensors in YAML have operational section."""
        sensors = load_sensors(families=(SensorFamily.SPAD,))
        for sensor in sensors:
            assert sensor.operational is not None, f"{sensor.name} missing operational"

    def test_geometric_numeric_fields_are_float(self) -> None:
        """Loader coerces numeric property group fields to float."""
        sensors = load_sensors(families=(SensorFamily.SPAD,))
        for sensor in sensors:
            assert isinstance(sensor.geometric.fov, float)
            if sensor.geometric.spatial_resolution is not None:
                assert isinstance(sensor.geometric.spatial_resolution, float)


# ---------------------------------------------------------------------------
# load_family_ranges()
# ---------------------------------------------------------------------------


class TestLoadFamilyRanges:
    def test_returns_dict(self) -> None:
        result = load_family_ranges()
        assert isinstance(result, dict)

    def test_spad_in_result(self) -> None:
        result = load_family_ranges()
        assert SensorFamily.SPAD in result

    def test_spad_ranges_have_expected_keys(self) -> None:
        result = load_family_ranges()
        spad_ranges = result[SensorFamily.SPAD]
        assert isinstance(spad_ranges, SensorFamilyRanges)
        assert "pde" in spad_ranges.ranges
        assert "dead_time_ns" in spad_ranges.ranges
        assert "fov_deg" in spad_ranges.ranges

    def test_filter_by_family(self) -> None:
        result = load_family_ranges(families=(SensorFamily.SPAD,))
        assert SensorFamily.SPAD in result

    def test_filter_returns_only_matching(self) -> None:
        result = load_family_ranges(families=(SensorFamily.LIDAR_FMCW,))
        assert SensorFamily.LIDAR_FMCW in result
        assert len(result) == 1

    def test_parameter_range_values(self) -> None:
        result = load_family_ranges()
        pde_range = result[SensorFamily.SPAD].ranges["pde"]
        assert pde_range.min is not None
        assert pde_range.max is not None
        assert pde_range.typical is not None
        assert pde_range.min < pde_range.max
