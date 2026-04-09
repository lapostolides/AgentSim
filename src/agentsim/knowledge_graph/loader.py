"""YAML-based sensor loader for the knowledge graph.

Scans the ``sensors/`` directory for ``*.yaml`` files, parses each into
validated SensorNode instances and SensorFamilyRanges objects. All numeric
values are coerced to float to satisfy Pydantic frozen model constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from agentsim.knowledge_graph.models import (
    FAMILY_SCHEMAS,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorFamily,
    SensorNode,
    TemporalProps,
)
from agentsim.knowledge_graph.ranges import ParameterRange, SensorFamilyRanges

logger = structlog.get_logger()

_SENSORS_DIR = Path(__file__).parent / "sensors"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_numeric_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with all int values cast to float.

    Pydantic frozen models with ``float`` fields reject raw ``int`` from
    YAML ``safe_load``. This coerces numeric values without mutating the
    original dict.
    """
    return {
        k: float(v) if isinstance(v, int) else v
        for k, v in data.items()
    }


def _coerce_family_specs(
    specs: dict[str, Any],
    family: SensorFamily,
) -> dict[str, float | str]:
    """Return a new dict with family_specs values coerced per FAMILY_SCHEMAS.

    If the schema expects ``float`` and YAML gave ``int``, cast to ``float``.
    If the schema expects ``(int, float)`` tuple type, leave numeric as-is
    but still ensure it is at least a float for consistency.
    String values pass through unchanged.
    """
    schema = FAMILY_SCHEMAS.get(family, {})
    result: dict[str, float | str] = {}
    for key, value in specs.items():
        expected = schema.get(key)
        if expected is not None and isinstance(value, (int, float)) and not isinstance(value, str):
            # Always coerce numerics to float for family_specs
            result[key] = float(value)
        elif isinstance(value, int):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _parse_sensor_node(data: dict[str, Any], family: SensorFamily) -> SensorNode:
    """Parse a single sensor entry dict into a validated SensorNode.

    Args:
        data: A sensor entry from the YAML ``sensors`` list.
        family: The SensorFamily enum for this YAML file.

    Returns:
        A frozen SensorNode instance.
    """
    geometric_data = _coerce_numeric_fields(data.get("geometric", {}))
    temporal_data = _coerce_numeric_fields(data.get("temporal", {}))
    radiometric_data = _coerce_numeric_fields(data.get("radiometric", {}))

    operational_raw = data.get("operational")
    operational = (
        OperationalProps(**_coerce_numeric_fields(operational_raw))
        if operational_raw is not None
        else None
    )

    family_specs = _coerce_family_specs(
        data.get("family_specs", {}),
        family,
    )

    return SensorNode(
        name=data["name"],
        family=family,
        description=data.get("description", ""),
        geometric=GeometricProps(**geometric_data),
        temporal=TemporalProps(**temporal_data),
        radiometric=RadiometricProps(**radiometric_data),
        operational=operational,
        family_specs=family_specs,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_sensors(
    families: tuple[SensorFamily, ...] | None = None,
) -> tuple[SensorNode, ...]:
    """Load sensor nodes from YAML files in the sensors directory.

    Args:
        families: Optional filter -- only load sensors belonging to these
            families. ``None`` means load all.

    Returns:
        Immutable tuple of validated SensorNode instances.
    """
    if not _SENSORS_DIR.exists():
        logger.warning("sensors_dir_missing", path=str(_SENSORS_DIR))
        return ()

    results: list[SensorNode] = []

    for yaml_path in sorted(_SENSORS_DIR.glob("*.yaml")):
        with open(yaml_path, "r") as fh:
            doc = yaml.safe_load(fh)

        if doc is None:
            continue

        family_str = doc.get("family")
        if family_str is None:
            logger.warning("yaml_missing_family", path=str(yaml_path))
            continue

        try:
            family = SensorFamily(family_str)
        except ValueError:
            logger.warning("yaml_unknown_family", path=str(yaml_path), family=family_str)
            continue

        if families is not None and family not in families:
            continue

        for entry in doc.get("sensors", []):
            node = _parse_sensor_node(entry, family)
            results.append(node)

    return tuple(results)


def load_family_ranges(
    families: tuple[SensorFamily, ...] | None = None,
) -> dict[SensorFamily, SensorFamilyRanges]:
    """Load family-level parameter ranges from YAML files.

    Args:
        families: Optional filter -- only load ranges for these families.
            ``None`` means load all.

    Returns:
        Dict mapping SensorFamily enum to SensorFamilyRanges.
    """
    if not _SENSORS_DIR.exists():
        logger.warning("sensors_dir_missing", path=str(_SENSORS_DIR))
        return {}

    result: dict[SensorFamily, SensorFamilyRanges] = {}

    for yaml_path in sorted(_SENSORS_DIR.glob("*.yaml")):
        with open(yaml_path, "r") as fh:
            doc = yaml.safe_load(fh)

        if doc is None:
            continue

        family_str = doc.get("family")
        if family_str is None:
            continue

        try:
            family = SensorFamily(family_str)
        except ValueError:
            continue

        if families is not None and family not in families:
            continue

        raw_ranges = doc.get("ranges", {})
        parsed_ranges: dict[str, ParameterRange] = {}
        for param_name, param_data in raw_ranges.items():
            coerced = _coerce_numeric_fields(param_data) if isinstance(param_data, dict) else {}
            parsed_ranges[param_name] = ParameterRange(**coerced)

        result[family] = SensorFamilyRanges(
            family=family,
            display_name=doc.get("display_name", ""),
            description=doc.get("description", ""),
            ranges=parsed_ranges,
        )

    return result
