"""Validation tests for batch 2 sensor YAML families.

Covers LiDAR (mechanical, solid-state, FMCW), structured light,
polarimetric, and spectral families. Validates loading, source citations,
ranges, and family_specs completeness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentsim.knowledge_graph.loader import load_family_ranges, load_sensors
from agentsim.knowledge_graph.models import FAMILY_SCHEMAS, SensorFamily, SensorNode


_SENSORS_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "agentsim" / "knowledge_graph" / "sensors"

BATCH2_FAMILIES = (
    SensorFamily.LIDAR_MECHANICAL,
    SensorFamily.LIDAR_SOLID_STATE,
    SensorFamily.LIDAR_FMCW,
    SensorFamily.STRUCTURED_LIGHT,
    SensorFamily.POLARIMETRIC,
    SensorFamily.SPECTRAL,
)

_FAMILY_YAML_FILES: dict[SensorFamily, str] = {
    SensorFamily.LIDAR_MECHANICAL: "lidar_mechanical.yaml",
    SensorFamily.LIDAR_SOLID_STATE: "lidar_solid_state.yaml",
    SensorFamily.LIDAR_FMCW: "lidar_fmcw.yaml",
    SensorFamily.STRUCTURED_LIGHT: "structured_light.yaml",
    SensorFamily.POLARIMETRIC: "polarimetric.yaml",
    SensorFamily.SPECTRAL: "spectral.yaml",
}


# ---------------------------------------------------------------------------
# Per-family loading tests (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", BATCH2_FAMILIES, ids=lambda f: f.value)
class TestBatch2FamilyLoading:
    """Verify each batch 2 family loads into validated SensorNode objects."""

    def test_loads_without_errors(self, family: SensorFamily) -> None:
        nodes = load_sensors(families=(family,))
        assert isinstance(nodes, tuple)
        assert len(nodes) >= 2, f"{family.value}: expected >=2 sensors, got {len(nodes)}"

    def test_all_are_sensor_nodes(self, family: SensorFamily) -> None:
        for node in load_sensors(families=(family,)):
            assert isinstance(node, SensorNode)
            assert node.family == family


# Aliases for individual family test names (plan acceptance criteria)
def test_lidar_mechanical_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.LIDAR_MECHANICAL,))
    assert len(nodes) >= 2


def test_lidar_solid_state_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.LIDAR_SOLID_STATE,))
    assert len(nodes) >= 2


def test_lidar_fmcw_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.LIDAR_FMCW,))
    assert len(nodes) >= 2


def test_structured_light_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.STRUCTURED_LIGHT,))
    assert len(nodes) >= 2


def test_polarimetric_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.POLARIMETRIC,))
    assert len(nodes) >= 2


def test_spectral_loads_without_errors() -> None:
    nodes = load_sensors(families=(SensorFamily.SPECTRAL,))
    assert len(nodes) >= 2


# ---------------------------------------------------------------------------
# Source citation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", BATCH2_FAMILIES, ids=lambda f: f.value)
def test_all_have_source(family: SensorFamily) -> None:
    """Each sensor entry in the YAML must have a non-empty source field."""
    yaml_file = _SENSORS_DIR / _FAMILY_YAML_FILES[family]
    with open(yaml_file, "r") as fh:
        doc = yaml.safe_load(fh)
    for entry in doc["sensors"]:
        assert "source" in entry, f"{entry['name']} missing source"
        assert entry["source"].strip(), f"{entry['name']} has empty source"


# ---------------------------------------------------------------------------
# Ranges tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", BATCH2_FAMILIES, ids=lambda f: f.value)
def test_ranges_present(family: SensorFamily) -> None:
    """Each family must have a non-empty ranges section."""
    result = load_family_ranges(families=(family,))
    assert family in result, f"{family.value} not in load_family_ranges result"
    assert len(result[family].ranges) > 0, f"{family.value} has empty ranges"


# ---------------------------------------------------------------------------
# Family specs completeness tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", BATCH2_FAMILIES, ids=lambda f: f.value)
def test_family_specs_complete(family: SensorFamily) -> None:
    """Every SensorNode must have all FAMILY_SCHEMAS keys in family_specs."""
    schema = FAMILY_SCHEMAS[family]
    for node in load_sensors(families=(family,)):
        for key in schema:
            assert key in node.family_specs, (
                f"{node.name} missing family_specs key '{key}'"
            )


# ---------------------------------------------------------------------------
# Aggregate tests
# ---------------------------------------------------------------------------


def test_all_batch2_sensors_count() -> None:
    """Batch 2 should have at least 12 sensors (6 families x 2 minimum)."""
    total = 0
    for family in BATCH2_FAMILIES:
        total += len(load_sensors(families=(family,)))
    assert total >= 12, f"Expected >=12 batch 2 sensors, got {total}"


def test_all_14_families_covered() -> None:
    """All 14 SensorFamily enum members must have at least 1 sensor YAML."""
    all_sensors = load_sensors()
    covered: dict[SensorFamily, int] = {}
    for node in all_sensors:
        covered[node.family] = covered.get(node.family, 0) + 1

    for family in SensorFamily:
        assert family in covered, (
            f"SensorFamily.{family.name} ({family.value}) has no YAML coverage"
        )
        assert covered[family] >= 1, (
            f"SensorFamily.{family.name} has 0 sensors loaded"
        )
