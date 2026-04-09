"""Numerical CRB via JAX autodiff for exotic sensor families (CRB-02, D-03).

JAX is optional. When absent, compute_numerical_crb raises ImportError.
The dispatch module (Plan 03) handles graceful degradation.

Forward models are simplified but JAX-differentiable representations of
each sensor family's measurement process, sufficient for Fisher information
matrix computation.
"""

from __future__ import annotations

import math

import numpy as np
import structlog
from numpy.typing import NDArray

from agentsim.knowledge_graph.crb.models import CRBResult
from agentsim.knowledge_graph.crb.stability import (
    CONDITION_THRESHOLD,
    assert_positive_variance,
    check_condition_number,
    regularize_fisher,
)
from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    SensorFamily,
    SensorNode,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# JAX availability check (lazy import pattern per D-04)
# ---------------------------------------------------------------------------


def jax_available() -> bool:
    """Check if JAX is importable at runtime."""
    try:
        import jax  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Supported families
# ---------------------------------------------------------------------------

NUMERICAL_FAMILIES: frozenset[SensorFamily] = frozenset({
    SensorFamily.CODED_APERTURE,
    SensorFamily.LENSLESS,
    SensorFamily.EVENT_CAMERA,
    SensorFamily.LIGHT_FIELD,
})


# ---------------------------------------------------------------------------
# Fisher information computation (JAX)
# ---------------------------------------------------------------------------


def _compute_fisher_matrix(
    neg_log_likelihood_fn: object,
    params_init: object,
) -> NDArray[np.floating]:
    """Compute Fisher information matrix via JAX jacfwd(jacrev(f)).

    Args:
        neg_log_likelihood_fn: Scalar function theta -> -log p(y|theta).
        params_init: Initial parameter vector (JAX array).

    Returns:
        Fisher information matrix as numpy array.
    """
    import jax

    hessian_fn = jax.jacfwd(jax.jacrev(neg_log_likelihood_fn))
    fisher_jax = hessian_fn(params_init)
    return np.array(fisher_jax)


# ---------------------------------------------------------------------------
# Forward models (private, one per family)
# ---------------------------------------------------------------------------


def _coded_aperture_neg_log_likelihood(
    sensor_specs: dict[str, float | str],
    snr: float,
    n_samples: int,
) -> tuple[object, object]:
    """Build neg-log-likelihood and initial params for coded aperture.

    Linear forward model: y = H @ x + noise.
    H derived from mask_transmittance and psf_condition_number.

    Returns:
        (neg_log_likelihood_fn, params_init) for Fisher computation.
    """
    import jax.numpy as jnp

    transmittance = float(sensor_specs["mask_transmittance"])
    psf_cond = float(sensor_specs["psf_condition_number"])

    # 2-parameter scene model: [intensity, depth_proxy]
    dim = 2
    # System matrix H: diagonal with transmittance scaling, conditioned by psf_cond
    h_diag = jnp.array([transmittance, transmittance / psf_cond])

    # Simulated measurement
    params_init = jnp.ones(dim)
    y_observed = h_diag * params_init + 0.01 * jnp.ones(dim)

    def neg_log_likelihood(params: object) -> object:
        residual = y_observed - h_diag * params
        return 0.5 * snr * jnp.sum(residual**2)

    return neg_log_likelihood, params_init


def _lensless_neg_log_likelihood(
    sensor_specs: dict[str, float | str],
    snr: float,
    n_samples: int,
) -> tuple[object, object]:
    """Build neg-log-likelihood for lensless camera.

    Convolutional model: y = PSF * x + noise.
    PSF condition from mask_sensor_distance_mm and psf_condition_number.

    Returns:
        (neg_log_likelihood_fn, params_init) for Fisher computation.
    """
    import jax.numpy as jnp

    distance_mm = float(sensor_specs["mask_sensor_distance_mm"])
    psf_cond = float(sensor_specs["psf_condition_number"])

    # 2-parameter model: [scene_intensity, scene_depth]
    dim = 2
    # PSF kernel approximated as scaled diagonal (simplified from full convolution)
    # Distance affects PSF spread, condition number affects invertibility
    scale = 1.0 / (1.0 + distance_mm * 0.1)
    psf_diag = jnp.array([scale, scale / psf_cond])

    params_init = jnp.ones(dim)
    y_observed = psf_diag * params_init + 0.01 * jnp.ones(dim)

    def neg_log_likelihood(params: object) -> object:
        residual = y_observed - psf_diag * params
        return 0.5 * snr * jnp.sum(residual**2)

    return neg_log_likelihood, params_init


def _event_camera_neg_log_likelihood(
    sensor_specs: dict[str, float | str],
    snr: float,
    n_samples: int,
) -> tuple[object, object]:
    """Build neg-log-likelihood for event camera.

    Event generation from log-intensity contrast exceeding contrast_threshold.

    Returns:
        (neg_log_likelihood_fn, params_init) for Fisher computation.
    """
    import jax.numpy as jnp

    contrast_threshold = float(sensor_specs["contrast_threshold"])
    refractory_us = float(sensor_specs["refractory_period_us"])

    # Single-parameter model: scene radiance change
    dim = 1
    params_init = jnp.array([1.0])

    # Event probability depends on log-intensity exceeding threshold
    # Temporal bandwidth limit from refractory period
    temporal_scale = 1.0 / (1.0 + refractory_us * 1e-3)

    def neg_log_likelihood(params: object) -> object:
        # Log-intensity change model
        log_intensity = jnp.log(jnp.abs(params[0]) + 1e-10)
        # Event probability (sigmoid of contrast vs threshold)
        event_prob = 1.0 / (1.0 + jnp.exp(-(log_intensity - contrast_threshold) * 10.0))
        # Bernoulli-like neg-log-likelihood scaled by temporal bandwidth
        nll = -(
            snr * temporal_scale * (
                event_prob * jnp.log(event_prob + 1e-10)
                + (1.0 - event_prob) * jnp.log(1.0 - event_prob + 1e-10)
            )
        )
        return nll

    return neg_log_likelihood, params_init


def _light_field_neg_log_likelihood(
    sensor_specs: dict[str, float | str],
    snr: float,
    n_samples: int,
) -> tuple[object, object]:
    """Build neg-log-likelihood for light field camera.

    Disparity estimation from sub-aperture images parameterized by
    angular_samples and baseline_mm.

    Returns:
        (neg_log_likelihood_fn, params_init) for Fisher computation.
    """
    import jax.numpy as jnp

    angular_samples = float(sensor_specs["angular_samples"])
    baseline_mm = float(sensor_specs["baseline_mm"])

    # Single depth parameter
    dim = 1
    params_init = jnp.array([2.0])  # 2 meters depth

    # Disparity is inversely proportional to depth: d = f*B/Z
    effective_baseline = baseline_mm * 1e-3  # mm -> m
    focal_proxy = angular_samples  # angular samples as focal length proxy

    def neg_log_likelihood(params: object) -> object:
        depth = params[0]
        # Disparity model: d = f*B/Z for each angular view
        disparity = focal_proxy * effective_baseline / (depth + 1e-6)
        # Observed disparity with noise
        d_observed = focal_proxy * effective_baseline / 2.0  # at reference depth
        # Sum over angular views (more views = more information)
        residual = d_observed - disparity
        return 0.5 * snr * angular_samples * residual**2

    return neg_log_likelihood, params_init


# ---------------------------------------------------------------------------
# Family dispatch for forward models
# ---------------------------------------------------------------------------

_FAMILY_FORWARD_MODELS = {
    SensorFamily.CODED_APERTURE: _coded_aperture_neg_log_likelihood,
    SensorFamily.LENSLESS: _lensless_neg_log_likelihood,
    SensorFamily.EVENT_CAMERA: _event_camera_neg_log_likelihood,
    SensorFamily.LIGHT_FIELD: _light_field_neg_log_likelihood,
}

_FAMILY_ASSUMPTIONS: dict[SensorFamily, tuple[str, ...]] = {
    SensorFamily.CODED_APERTURE: (
        "Linear forward model H @ x",
        "Known PSF/mask pattern",
        "Gaussian noise",
    ),
    SensorFamily.LENSLESS: (
        "Convolutional forward model",
        "Known diffraction PSF",
        "Gaussian noise",
    ),
    SensorFamily.EVENT_CAMERA: (
        "Log-intensity contrast model",
        "Independent pixel events",
        "Known contrast threshold",
    ),
    SensorFamily.LIGHT_FIELD: (
        "Plenoptic 1.0 model",
        "Known microlens geometry",
        "Gaussian noise per sub-aperture",
    ),
}

_FAMILY_TASKS: dict[SensorFamily, str] = {
    SensorFamily.CODED_APERTURE: "scene_reconstruction",
    SensorFamily.LENSLESS: "scene_reconstruction",
    SensorFamily.EVENT_CAMERA: "radiance_change",
    SensorFamily.LIGHT_FIELD: "depth",
}

_FAMILY_UNITS: dict[SensorFamily, str] = {
    SensorFamily.CODED_APERTURE: "dimensionless",
    SensorFamily.LENSLESS: "dimensionless",
    SensorFamily.EVENT_CAMERA: "dimensionless",
    SensorFamily.LIGHT_FIELD: "meter",
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_numerical_crb(
    sensor: SensorNode,
    estimation_task: str = "",
    *,
    snr: float = 100.0,
    n_samples: int = 1000,
    regularization_alpha: float = 1e-6,
) -> CRBResult:
    """Compute numerical CRB via JAX autodiff for exotic sensor families.

    Uses jax.jacfwd(jax.jacrev(f)) to compute the Fisher information matrix
    from a family-specific forward model log-likelihood, then inverts it
    with stability guards (condition number check + Tikhonov regularization).

    Args:
        sensor: Sensor node with family and family_specs.
        estimation_task: Override for the estimation task label.
        snr: Signal-to-noise ratio for the noise model.
        n_samples: Number of simulated samples (affects Fisher scaling).
        regularization_alpha: Tikhonov regularization strength for
            ill-conditioned Fisher matrices.

    Returns:
        CRBResult with confidence=NUMERICAL and populated condition_number.

    Raises:
        ImportError: If JAX is not installed.
        ValueError: If sensor.family is not in NUMERICAL_FAMILIES.
    """
    if not jax_available():
        raise ImportError(
            "JAX is required for numerical CRB computation. "
            "Install with: pip install jax jaxlib"
        )

    if sensor.family not in NUMERICAL_FAMILIES:
        raise ValueError(
            f"Family {sensor.family} not supported for numerical CRB. "
            f"Supported: {sorted(f.value for f in NUMERICAL_FAMILIES)}"
        )

    # Lazy JAX import inside function (D-04)
    import jax

    jax.config.update("jax_enable_x64", True)  # float64 precision (Pitfall 3)

    # Build forward model and initial params
    forward_fn = _FAMILY_FORWARD_MODELS[sensor.family]
    neg_log_likelihood_fn, params_init = forward_fn(
        sensor.family_specs, snr, n_samples
    )

    # Compute Fisher information matrix
    fisher = _compute_fisher_matrix(neg_log_likelihood_fn, params_init)

    # Stability guards (CRB-06)
    cond = check_condition_number(fisher)

    if cond > CONDITION_THRESHOLD:
        logger.warning(
            "ill_conditioned_fisher",
            sensor=sensor.name,
            family=sensor.family.value,
            condition_number=cond,
            threshold=CONDITION_THRESHOLD,
        )
        fisher = regularize_fisher(fisher, alpha=regularization_alpha)
        cond = check_condition_number(fisher)

    # Invert Fisher matrix
    inv_fisher = np.linalg.inv(fisher)
    assert_positive_variance(inv_fisher)

    # Extract bound from diagonal (max variance = worst-case parameter)
    variances = np.diag(inv_fisher)
    max_variance = float(np.max(variances))
    bound_value = math.sqrt(max_variance)

    task = estimation_task or _FAMILY_TASKS.get(sensor.family, "estimation")

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task=task,
        bound_value=bound_value,
        bound_unit=_FAMILY_UNITS.get(sensor.family, "dimensionless"),
        bound_type="numerical",
        confidence=ConfidenceQualifier.NUMERICAL,
        condition_number=cond,
        model_assumptions=_FAMILY_ASSUMPTIONS.get(sensor.family, ()),
        sensor_name=sensor.name,
    )
