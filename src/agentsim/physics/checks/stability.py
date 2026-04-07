"""CFL numerical stability checking for simulation validation.

Computes the Courant-Friedrichs-Lewy (CFL) number from velocity,
timestep, and mesh spacing, and flags instability for explicit solvers.
Purely deterministic, no LLM calls.
"""

from __future__ import annotations

from agentsim.physics.models import (
    CheckResult,
    ExtractedSimulationParams,
    Severity,
)

# CFL thresholds
_CFL_UNSTABLE = 1.0
_CFL_WARNING = 0.8


def check_cfl_stability(
    params: ExtractedSimulationParams,
) -> tuple[CheckResult, ...]:
    """Check CFL stability condition for a simulation.

    Args:
        params: Extracted simulation parameters including velocity,
            timestep, mesh_spacing, and solver_type.

    Returns:
        Tuple with a single CheckResult indicating CFL status.
    """
    # Implicit solvers are unconditionally stable for CFL
    if params.solver_type == "implicit":
        return (
            CheckResult(
                check="cfl",
                severity=Severity.INFO,
                message="Implicit solver detected -- CFL condition not applicable",
            ),
        )

    # Check for sufficient parameters
    if params.velocity is None or params.timestep is None or params.mesh_spacing is None:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.INFO,
                message="Insufficient parameters to compute CFL number",
            ),
        )

    # Guard against zero mesh spacing
    if params.mesh_spacing == 0.0:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.ERROR,
                message="Mesh spacing is zero -- cannot compute CFL",
            ),
        )

    cfl = abs(params.velocity) * params.timestep / params.mesh_spacing
    details = f"velocity={params.velocity}, dt={params.timestep}, dx={params.mesh_spacing}"

    if params.solver_type == "unknown":
        return _check_cfl_unknown_solver(cfl, details)

    return _check_cfl_explicit_solver(cfl, details)


def _check_cfl_explicit_solver(
    cfl: float,
    details: str,
) -> tuple[CheckResult, ...]:
    """CFL assessment for explicit solvers.

    Args:
        cfl: Computed CFL number.
        details: Parameter details string.

    Returns:
        Tuple with a single CheckResult.
    """
    if cfl > _CFL_UNSTABLE:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.ERROR,
                message=(
                    f"CFL number {cfl:.3f} > 1.0 -- "
                    "simulation will be numerically unstable"
                ),
                details=details,
            ),
        )
    if cfl > _CFL_WARNING:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.WARNING,
                message=f"CFL number {cfl:.3f} is close to stability limit",
                details=details,
            ),
        )
    return (
        CheckResult(
            check="cfl",
            severity=Severity.INFO,
            message=f"CFL number {cfl:.3f} is within stable range",
            details=details,
        ),
    )


def _check_cfl_unknown_solver(
    cfl: float,
    details: str,
) -> tuple[CheckResult, ...]:
    """CFL assessment when solver type is unknown.

    Downgrades severity since we cannot be sure the solver is explicit.

    Args:
        cfl: Computed CFL number.
        details: Parameter details string.

    Returns:
        Tuple with a single CheckResult.
    """
    if cfl > _CFL_UNSTABLE:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.WARNING,
                message=(
                    f"CFL number {cfl:.3f} > 1.0 -- "
                    "may be unstable (solver type unknown)"
                ),
                details=details,
            ),
        )
    if cfl > _CFL_WARNING:
        return (
            CheckResult(
                check="cfl",
                severity=Severity.INFO,
                message=(
                    f"CFL number {cfl:.3f} approaching stability limit "
                    "(solver type unknown)"
                ),
                details=details,
            ),
        )
    return (
        CheckResult(
            check="cfl",
            severity=Severity.INFO,
            message=f"CFL number {cfl:.3f} is within stable range",
            details=details,
        ),
    )
