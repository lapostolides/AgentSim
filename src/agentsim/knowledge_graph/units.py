"""Pint-based unit validation helpers for knowledge graph models.

Provides canonical unit mappings and validation functions that ensure
property values use dimensionally correct units. Used by all property
group models at construction time.
"""

from __future__ import annotations

import pint

# Single Pint UnitRegistry for the knowledge_graph package (same pattern as physics/models.py).
_ureg = pint.UnitRegistry()

# Canonical unit strings -- all defaults and validations use these exact strings.
CANONICAL_UNITS: dict[str, str] = {
    "time": "picosecond",
    "angle": "degree",
    "length": "meter",
    "frequency": "hertz",
    "ratio": "dimensionless",
    "power": "watt",
    "mass": "gram",
    "currency": "USD",
    "temperature": "kelvin",
    "voltage": "volt",
}

# Reference units per category -- used to derive expected dimensionality at runtime.
# Comparing Pint dimensionality objects (not strings) avoids ordering inconsistencies.
_REFERENCE_UNITS: dict[str, str] = {
    "time": "second",
    "length": "meter",
    "frequency": "hertz",
    "power": "watt",
    "mass": "gram",
    "temperature": "kelvin",
    "voltage": "volt",
}

# Known angle units -- handles the special case where Pint treats angles as dimensionless.
_KNOWN_ANGLE_UNITS: frozenset[str] = frozenset(
    {"degree", "radian", "arcminute", "arcsecond"}
)


def validate_unit(unit_str: str, quantity_category: str) -> None:
    """Validate that a unit string is dimensionally correct for its category.

    Args:
        unit_str: The unit string to validate (e.g., "degree", "picosecond").
        quantity_category: The expected category (e.g., "angle", "time").

    Returns:
        None on success.

    Raises:
        ValueError: If the unit is unknown or incompatible with the expected category.
    """
    if quantity_category in ("currency", "ratio"):
        return None

    if quantity_category == "angle":
        if unit_str in _KNOWN_ANGLE_UNITS:
            return None
        # Try Pint parse -- if it succeeds but isn't a known angle, reject it
        try:
            parsed = _ureg.parse_units(unit_str)
        except pint.UndefinedUnitError as exc:
            raise ValueError(
                f"Unknown unit '{unit_str}' for {quantity_category}"
            ) from exc
        raise ValueError(
            f"Unit '{unit_str}' has dimensionality {parsed.dimensionality}, "
            f"expected angle unit for {quantity_category}"
        )

    ref_unit_str = _REFERENCE_UNITS.get(quantity_category)
    if ref_unit_str is None:
        return None

    try:
        actual_dim = _ureg.parse_units(unit_str).dimensionality
    except pint.UndefinedUnitError as exc:
        raise ValueError(
            f"Unknown unit '{unit_str}' for {quantity_category}"
        ) from exc

    expected_dim = _ureg.parse_units(ref_unit_str).dimensionality
    if actual_dim != expected_dim:
        raise ValueError(
            f"Unit '{unit_str}' has dimensionality {actual_dim}, "
            f"expected {expected_dim} for {quantity_category}"
        )

    return None
