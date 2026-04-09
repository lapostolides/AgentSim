"""Validation tests for batch 1 sensor family YAML files (07-02).

Tests that all 7 families (CW ToF, Pulsed dToF, Event Camera, Coded Aperture,
Light Field, Lensless, RGB) load into validated SensorNode objects with correct
family_specs, ranges, and source citations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentsim.knowledge_graph.loader import load_family_ranges, load_sensors
from agentsim.knowledge_graph.models import FAMILY_SCHEMAS, SensorFamily, SensorNode
from agentsim.knowledge_graph.ranges import SensorFamilyRanges

_SENSORS_DIR = Path(__file__).resolve().parents[2] / "src" / "agentsim" / "knowledge_graph" / "sensors"

# ---------------------------------------------------------------------------
# Families covered in batch 1
# ---------------------------------------------------------------------------

BATCH1_FAMILIES = (
    SensorFamily.CW_TOF,
    SensorFamily.PULSED_DTOF,
    SensorFamily.EVENT_CAMERA,
    SensorFamily.CODED_APERTURE,
    SensorFamily.LIGHT_FIELD,
    SensorFamily.LENSLESS,
    SensorFamily.RGB,
)

BATCH1_YAML_FILES = {
    SensorFamily.CW_TOF: "cw_tof.yaml",
    SensorFamily.PULSED_DTOF: "pulsed_dtof.yaml",
    SensorFamily.EVENT_CAMERA: "event_camera.yaml",
    SensorFamily.CODED_APERTURE: "coded_aperture.yaml",
    SensorFamily.LIGHT_FIELD: "light_field.yaml",
    SensorFamily.LENSLESS: "lensless.yaml",
    SensorFamily.RGB: "rgb.yaml",
}


# ---------------------------------------------------------------------------
# Parametrized tests per family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", BATCH1_FAMILIES, ids=lambda f: f.value)
class TestBatch1FamilyLoads:
    """Each batch 1 family loads without errors and returns >= 2 sensors."""

    def test_loads_without_errors(self, family: SensorFamily) -> None:
        nodes = load_sensors(families=(family,))
        assert isinstance(nodes, tuple)
        assert len(nodes) >= 2, f"{family.value}: expected >= 2 sensors, got {len(nodes)}"

    def test_all_are_sensor_nodes(self, family: SensorFamily) -> None:
        nodes = load_sensors(families=(family,))
        for node in nodes:
            assert isinstance(node, SensorNode)
            assert node.family == family


@pytest.mark.parametrize("family", BATCH1_FAMILIES, ids=lambda f: f.value)
class TestBatch1Sources:
    """Each sensor in every batch 1 YAML has a source field (D-06)."""

    def test_all_have_source(self, family: SensorFamily) -> None:
        yaml_file = _SENSORS_DIR / BATCH1_YAML_FILES[family]
        with open(yaml_file, "r") as fh:
            doc = yaml.safe_load(fh)
        for entry in doc.get("sensors", []):
            assert "source" in entry, (
                f"{family.value} sensor '{entry.get('name', '?')}' missing 'source' field"
            )
            assert entry["source"], (
                f"{family.value} sensor '{entry.get('name', '?')}' has empty 'source'"
            )


@pytest.mark.parametrize("family", BATCH1_FAMILIES, ids=lambda f: f.value)
class TestBatch1Ranges:
    """Each batch 1 family has a non-empty ranges section."""

    def test_ranges_present(self, family: SensorFamily) -> None:
        result = load_family_ranges(families=(family,))
        assert family in result, f"{family.value} not found in load_family_ranges()"
        ranges_obj = result[family]
        assert isinstance(ranges_obj, SensorFamilyRanges)
        assert len(ranges_obj.ranges) > 0, f"{family.value} has empty ranges"


@pytest.mark.parametrize("family", BATCH1_FAMILIES, ids=lambda f: f.value)
class TestBatch1FamilySpecsComplete:
    """Each sensor has all required FAMILY_SCHEMAS keys in family_specs."""

    def test_family_specs_complete(self, family: SensorFamily) -> None:
        schema = FAMILY_SCHEMAS[family]
        nodes = load_sensors(families=(family,))
        for node in nodes:
            for key in schema:
                assert key in node.family_specs, (
                    f"{node.name} missing family_specs key '{key}'"
                )


# ---------------------------------------------------------------------------
# Special assertions
# ---------------------------------------------------------------------------


class TestRGBHasRealSenseD435i:
    """RGB family must include Intel RealSense D435i per D-08."""

    def test_rgb_has_realsense_d435i(self) -> None:
        sensors = load_sensors(families=(SensorFamily.RGB,))
        names = [s.name for s in sensors]
        matching = [n for n in names if "RealSense D435i" in n]
        assert len(matching) >= 1, (
            f"RGB family missing RealSense D435i; got names: {names}"
        )


class TestAllBatch1SensorsCount:
    """Total sensor count across batch 1 must be >= 14 (7 families x 2 min)."""

    def test_all_batch1_sensors_count(self) -> None:
        all_nodes = load_sensors(families=BATCH1_FAMILIES)
        assert len(all_nodes) >= 14, (
            f"Expected >= 14 batch 1 sensors, got {len(all_nodes)}"
        )
