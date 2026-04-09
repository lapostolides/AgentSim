"""Unified CRB dispatch -- selects analytical or numerical computation (CRB-03).

CRITICAL: This function NEVER raises for unsupported families (per D-07).
It returns CRBResult with confidence=UNKNOWN and bound_value=inf.
Phase 9 feasibility engine iterates all sensors and must handle this
gracefully (Pitfall 5 from RESEARCH.md).
"""

from __future__ import annotations

import structlog

from agentsim.knowledge_graph.crb.analytical import (
    ANALYTICAL_FAMILIES,
    compute_analytical_crb,
)
from agentsim.knowledge_graph.crb.models import CRBResult
from agentsim.knowledge_graph.crb.numerical import (
    NUMERICAL_FAMILIES,
    compute_numerical_crb,
    jax_available,
)
from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorNode

logger = structlog.get_logger()

SUPPORTED_FAMILIES = ANALYTICAL_FAMILIES | NUMERICAL_FAMILIES


def compute_crb(
    sensor: SensorNode,
    estimation_task: str = "",
    *,
    snr: float = 100.0,
    target_depth_m: float = 5.0,
    n_photons: int = 10000,
    regularization_alpha: float = 1e-6,
) -> CRBResult:
    """Compute CRB for any sensor family, routing to the correct backend.

    Three dispatch branches (never raises):
    1. Analytical families -> compute_analytical_crb
    2. Numerical families -> compute_numerical_crb (or UNKNOWN if no JAX)
    3. Unsupported families -> CRBResult with confidence=UNKNOWN, bound_value=inf

    Args:
        sensor: A validated SensorNode instance.
        estimation_task: Override estimation task label.
        snr: Signal-to-noise ratio (linear).
        target_depth_m: Target depth in meters.
        n_photons: Photon count for counting families.
        regularization_alpha: Tikhonov regularization for numerical CRB.

    Returns:
        A frozen CRBResult. Never raises for any SensorFamily value.
    """
    family = sensor.family

    # Branch 1: analytical families
    if family in ANALYTICAL_FAMILIES:
        return compute_analytical_crb(
            sensor,
            estimation_task,
            snr=snr,
            target_depth_m=target_depth_m,
            n_photons=n_photons,
        )

    # Branch 2: numerical families
    if family in NUMERICAL_FAMILIES:
        if jax_available():
            return compute_numerical_crb(
                sensor,
                estimation_task,
                snr=snr,
                regularization_alpha=regularization_alpha,
            )
        logger.warning(
            "jax_unavailable_for_numerical_crb",
            sensor=sensor.name,
            family=family.value,
        )
        return CRBResult(
            sensor_family=family,
            estimation_task=estimation_task or "unknown",
            bound_value=float("inf"),
            bound_unit="unknown",
            bound_type="numerical",
            confidence=ConfidenceQualifier.UNKNOWN,
            model_assumptions=("JAX unavailable -- numerical CRB not computed",),
            sensor_name=sensor.name,
        )

    # Branch 3: unsupported families (RGB, LIDAR_MECHANICAL, LIDAR_SOLID_STATE)
    logger.info(
        "no_crb_model",
        sensor=sensor.name,
        family=family.value,
    )
    return CRBResult(
        sensor_family=family,
        estimation_task=estimation_task or "unknown",
        bound_value=float("inf"),
        bound_unit="unknown",
        bound_type="none",
        confidence=ConfidenceQualifier.UNKNOWN,
        model_assumptions=(f"No CRB model available for {family.value}",),
        sensor_name=sensor.name,
    )
