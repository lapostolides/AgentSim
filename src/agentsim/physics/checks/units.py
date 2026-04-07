"""Pint-based unit consistency validation.

Checks that all physical parameters have valid SI-compatible units
and finite magnitudes. Uses the single shared UnitRegistry from
agentsim.physics.models to avoid multi-registry pitfalls.
"""

from __future__ import annotations

import math

import pint

from agentsim.physics.models import CheckResult, Severity, _ureg


def check_unit_consistency(
    params: dict[str, tuple[float, str]],
) -> tuple[CheckResult, ...]:
    """Validate unit strings and magnitudes for a set of physical parameters.

    For each parameter, checks that:
    - The unit string is recognized by Pint
    - The magnitude is not NaN
    - The magnitude is not infinite

    Args:
        params: Mapping of parameter name to (magnitude, unit_string).

    Returns:
        Tuple of CheckResult for each invalid parameter (empty if all valid).
    """
    results: list[CheckResult] = []

    for name, (magnitude, unit_str) in params.items():
        # Check NaN before Pint (NaN is technically valid for Pint)
        if math.isnan(magnitude):
            results.append(
                CheckResult(
                    check="unit_consistency",
                    severity=Severity.ERROR,
                    message=f"Parameter '{name}' has NaN magnitude",
                    parameter=name,
                )
            )
            continue

        # Check infinity
        if math.isinf(magnitude):
            results.append(
                CheckResult(
                    check="unit_consistency",
                    severity=Severity.ERROR,
                    message=f"Parameter '{name}' has infinite magnitude",
                    parameter=name,
                )
            )
            continue

        # Check unit validity
        try:
            _ureg.Quantity(magnitude, unit_str)
        except pint.errors.UndefinedUnitError:
            results.append(
                CheckResult(
                    check="unit_consistency",
                    severity=Severity.ERROR,
                    message=f"Unknown unit '{unit_str}' for parameter '{name}'",
                    parameter=name,
                    details=f"Unit '{unit_str}' is not recognized by Pint",
                )
            )
        except pint.errors.DimensionalityError as exc:
            results.append(
                CheckResult(
                    check="unit_consistency",
                    severity=Severity.ERROR,
                    message=f"Dimensionality error for parameter '{name}': {exc}",
                    parameter=name,
                    details=str(exc),
                )
            )

    return tuple(results)
