"""Parameter range plausibility checking.

Cross-references parameter values against the curated constants registry
to flag physically implausible values. Uses Pint for unit conversion
before comparison.
"""

from __future__ import annotations

import pint

from agentsim.physics.constants import get_parameter_range
from agentsim.physics.models import CheckResult, Severity, _ureg


def check_parameter_ranges(
    params: dict[str, tuple[float, str]],
    domain: str = "universal",
) -> tuple[CheckResult, ...]:
    """Check parameter values against known plausible ranges.

    For each parameter, looks up the expected range from the constants
    registry, converts units if needed, and flags values outside bounds.

    Args:
        params: Mapping of parameter name to (magnitude, unit_string).
        domain: Domain to check ranges against (default "universal").

    Returns:
        Tuple of CheckResult for each issue found (empty if all in range).
    """
    results: list[CheckResult] = []

    for name, (magnitude, unit_str) in params.items():
        range_data = get_parameter_range(name, domain)

        if range_data is None:
            results.append(
                CheckResult(
                    check="parameter_range",
                    severity=Severity.INFO,
                    message=f"No range data for parameter '{name}'",
                    parameter=name,
                )
            )
            continue

        min_val, max_val, range_unit = range_data

        # Convert parameter to range units for comparison
        try:
            param_q = _ureg.Quantity(magnitude, unit_str).to(range_unit)
        except pint.errors.DimensionalityError:
            results.append(
                CheckResult(
                    check="parameter_range",
                    severity=Severity.WARNING,
                    message=(
                        f"Cannot compare '{name}' units: "
                        f"'{unit_str}' is not convertible to '{range_unit}'"
                    ),
                    parameter=name,
                )
            )
            continue

        converted_magnitude = float(param_q.magnitude)

        if converted_magnitude < min_val:
            results.append(
                CheckResult(
                    check="parameter_range",
                    severity=Severity.ERROR,
                    message=(
                        f"Parameter '{name}' value {converted_magnitude} "
                        f"below minimum {min_val} {range_unit}"
                    ),
                    parameter=name,
                    details=f"Range: [{min_val}, {max_val}] {range_unit}",
                )
            )

        if converted_magnitude > max_val:
            results.append(
                CheckResult(
                    check="parameter_range",
                    severity=Severity.ERROR,
                    message=(
                        f"Parameter '{name}' value {converted_magnitude} "
                        f"above maximum {max_val} {range_unit}"
                    ),
                    parameter=name,
                    details=f"Range: [{min_val}, {max_val}] {range_unit}",
                )
            )

    return tuple(results)
