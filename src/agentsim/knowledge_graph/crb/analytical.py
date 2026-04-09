"""Analytical (closed-form) CRB computation for 7 sensor families.

Implements the exact formulas from estimation theory (Kay 1993, Van Trees 2001)
for sensor families with known Fisher information expressions. Each function
maps sensor YAML parameters to physical quantities using explicit unit
conversion constants.

All computations use the ``math`` stdlib -- no numpy needed for scalar CRB.
"""

from __future__ import annotations

import math

import structlog

from agentsim.knowledge_graph.crb.models import CRBResult
from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily, SensorNode

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Unit conversion constants (SI base units)
# ---------------------------------------------------------------------------

_C: float = 299_792_458.0  # speed of light, m/s
_MHZ_TO_HZ: float = 1e6  # MHz -> Hz
_PS_TO_S: float = 1e-12  # picosecond -> second
_NS_TO_S: float = 1e-9  # nanosecond -> second
_GHZ_TO_HZ: float = 1e9  # GHz -> Hz
_MM_TO_M: float = 1e-3  # millimeter -> meter

# ---------------------------------------------------------------------------
# Supported families
# ---------------------------------------------------------------------------

ANALYTICAL_FAMILIES: frozenset[SensorFamily] = frozenset({
    SensorFamily.SPAD,
    SensorFamily.CW_TOF,
    SensorFamily.PULSED_DTOF,
    SensorFamily.LIDAR_FMCW,
    SensorFamily.POLARIMETRIC,
    SensorFamily.SPECTRAL,
    SensorFamily.STRUCTURED_LIGHT,
})

# Default estimation tasks per family
_DEFAULT_TASKS: dict[SensorFamily, str] = {
    SensorFamily.SPAD: "depth",
    SensorFamily.CW_TOF: "range",
    SensorFamily.PULSED_DTOF: "range",
    SensorFamily.LIDAR_FMCW: "range",
    SensorFamily.POLARIMETRIC: "dolp",
    SensorFamily.SPECTRAL: "abundance",
    SensorFamily.STRUCTURED_LIGHT: "depth",
}


# ---------------------------------------------------------------------------
# Projector resolution parser (structured light)
# ---------------------------------------------------------------------------


def _parse_projector_resolution(resolution_str: str) -> int:
    """Parse projector resolution string like ``'1280x720'`` into pixel count.

    Takes the maximum of width and height as the effective focal length
    proxy in pixels.

    Args:
        resolution_str: Resolution string in ``'WxH'`` format.

    Returns:
        Maximum dimension in pixels, or 1280 as fallback.
    """
    try:
        parts = resolution_str.lower().split("x")
        dims = [int(p.strip()) for p in parts]
        return max(dims)
    except (ValueError, AttributeError):
        logger.warning(
            "projector_resolution_parse_failed",
            resolution_str=resolution_str,
            fallback=1280,
        )
        return 1280


# ---------------------------------------------------------------------------
# Private CRB functions (one per family)
# ---------------------------------------------------------------------------


def _spad_depth_crb(
    sensor: SensorNode,
    n_photons: int,
    target_depth_m: float,
) -> CRBResult:
    """SPAD depth CRB from Poisson photon-counting estimation theory.

    Formula: var(depth) >= c^2 / (8 * N_eff * B_eff^2)
    Reference: Kay, Ch. 3; Heide et al., Scientific Reports 2018
    """
    pde = float(sensor.family_specs["pde"])
    fill_factor = float(sensor.family_specs["fill_factor"])
    timing_ps = sensor.temporal.temporal_resolution  # picoseconds
    if timing_ps is None:
        raise ValueError(
            f"Sensor '{sensor.name}' missing temporal_resolution for SPAD CRB"
        )

    n_eff = n_photons * pde * fill_factor
    b_eff = 1.0 / (timing_ps * _PS_TO_S)  # ps -> s -> Hz

    variance = _C**2 / (8.0 * n_eff * b_eff**2)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="depth",
        bound_value=bound,
        bound_unit="meter",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Poisson photon statistics",
            "Single-bounce direct ToF",
            "Negligible background",
        ),
        sensor_name=sensor.name,
    )


def _cw_tof_range_crb(
    sensor: SensorNode,
    snr: float,
) -> CRBResult:
    """CW-ToF range CRB from sinusoidal phase estimation.

    Formula: var(range) >= c^2 / (32 * pi^2 * f_mod^2 * SNR)
    Reference: Kay, Ch. 7; Lange 2004
    """
    f_mod = float(sensor.family_specs["modulation_frequency_mhz"]) * _MHZ_TO_HZ

    variance = _C**2 / (32.0 * math.pi**2 * f_mod**2 * snr)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="range",
        bound_value=bound,
        bound_unit="meter",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Sinusoidal modulation",
            "AWGN phase noise",
            "No multipath",
        ),
        sensor_name=sensor.name,
    )


def _pulsed_dtof_range_crb(
    sensor: SensorNode,
    snr: float,
) -> CRBResult:
    """Pulsed dToF range CRB from time-of-arrival estimation.

    Formula: var(range) >= c^2 * tau_p^2 / (8 * SNR)
    Reference: Stein, IEEE TASSP 1981
    """
    tau_p = float(sensor.family_specs["pulse_width_ns"]) * _NS_TO_S

    variance = _C**2 * tau_p**2 / (8.0 * snr)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="range",
        bound_value=bound,
        bound_unit="meter",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Gaussian pulse shape",
            "Single return",
            "AWGN",
        ),
        sensor_name=sensor.name,
    )


def _fmcw_range_crb(
    sensor: SensorNode,
    snr: float,
) -> CRBResult:
    """FMCW range CRB from beat-frequency estimation.

    Formula: var(range) >= c^2 / (8 * pi^2 * B_chirp^2 * SNR)
    Reference: Van Trees, Part III, 2001
    """
    b_chirp = float(sensor.family_specs["chirp_bandwidth_ghz"]) * _GHZ_TO_HZ

    variance = _C**2 / (8.0 * math.pi**2 * b_chirp**2 * snr)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="range",
        bound_value=bound,
        bound_unit="meter",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Linear chirp",
            "Single target",
            "Matched filter processing",
        ),
        sensor_name=sensor.name,
    )


def _polarimetric_stokes_crb(
    sensor: SensorNode,
    n_photons: int,
) -> CRBResult:
    """Polarimetric DoLP CRB from Stokes vector estimation.

    Formula: var(DoLP) >= 1 / (N_eff * K_ext^2)
    Reference: Tyo et al., Applied Optics 2006; Goudail & Beniere, JOSA A 2010
    """
    qe = sensor.radiometric.quantum_efficiency
    qe_val = qe if qe is not None else 1.0
    n_eff = n_photons * qe_val
    k_ext = float(sensor.family_specs["extinction_ratio"])

    variance = 1.0 / (n_eff * k_ext**2)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="dolp",
        bound_value=bound,
        bound_unit="dimensionless",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Uniform Stokes vector",
            "Shot noise limited",
            "Ideal polarizer model",
        ),
        sensor_name=sensor.name,
    )


def _spectral_unmixing_crb(
    sensor: SensorNode,
    snr: float,
) -> CRBResult:
    """Hyperspectral abundance CRB from linear mixing model.

    Formula: var(abundance) >= band_count / (SNR^2 * spectral_resolution_ratio)
    Reference: Chang, "Hyperspectral Data Processing," 2013
    """
    band_count = float(sensor.family_specs["band_count"])
    range_min = float(sensor.family_specs["spectral_range_nm_min"])
    range_max = float(sensor.family_specs["spectral_range_nm_max"])
    resolution = float(sensor.family_specs["spectral_resolution_nm"])

    spectral_range = range_max - range_min
    spectral_resolution_ratio = spectral_range / resolution

    variance = band_count / (snr**2 * spectral_resolution_ratio)
    bound = math.sqrt(variance)

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="abundance",
        bound_value=bound,
        bound_unit="dimensionless",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=(
            "Linear mixing model",
            "Known endmember spectra",
            "Gaussian noise",
            "Simplified Fisher information",
        ),
        sensor_name=sensor.name,
    )


def _structured_light_depth_crb(
    sensor: SensorNode,
    target_depth_m: float,
    snr: float,
) -> CRBResult:
    """Structured light depth CRB from triangulation geometry.

    Formula: var(depth) >= (depth^2 * sigma_px^2) / (baseline^2 * f_proj^2)
    Reference: Scharstein & Szeliski, IJCV 2002
    """
    baseline = float(sensor.family_specs["baseline_mm"]) * _MM_TO_M
    resolution_str = str(sensor.family_specs["projector_resolution"])
    f_proj = float(_parse_projector_resolution(resolution_str))

    sigma_px = 1.0 / math.sqrt(snr)

    variance = (target_depth_m**2 * sigma_px**2) / (baseline**2 * f_proj**2)
    bound = math.sqrt(variance)

    assumptions = [
        "Single-shot structured pattern",
        "Known correspondence",
        "Lambertian surface",
    ]
    # Note if resolution was parsed from string
    if f_proj == 1280.0 and resolution_str != "1280x720":
        assumptions.append(f"Projector resolution fallback (could not parse '{resolution_str}')")

    return CRBResult(
        sensor_family=sensor.family,
        estimation_task="depth",
        bound_value=bound,
        bound_unit="meter",
        bound_type="analytical",
        confidence=ConfidenceQualifier.ANALYTICAL,
        condition_number=None,
        model_assumptions=tuple(assumptions),
        sensor_name=sensor.name,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[SensorFamily, str] = {
    SensorFamily.SPAD: "_spad_depth_crb",
    SensorFamily.CW_TOF: "_cw_tof_range_crb",
    SensorFamily.PULSED_DTOF: "_pulsed_dtof_range_crb",
    SensorFamily.LIDAR_FMCW: "_fmcw_range_crb",
    SensorFamily.POLARIMETRIC: "_polarimetric_stokes_crb",
    SensorFamily.SPECTRAL: "_spectral_unmixing_crb",
    SensorFamily.STRUCTURED_LIGHT: "_structured_light_depth_crb",
}


# ---------------------------------------------------------------------------
# Public dispatch function
# ---------------------------------------------------------------------------


def compute_analytical_crb(
    sensor: SensorNode,
    estimation_task: str = "",
    *,
    snr: float = 100.0,
    target_depth_m: float = 5.0,
    n_photons: int = 10000,
) -> CRBResult:
    """Compute closed-form CRB for a sensor using analytical formulas.

    Dispatches to a family-specific private function based on
    ``sensor.family``. Raises ``ValueError`` if the family is not in
    :data:`ANALYTICAL_FAMILIES`.

    Args:
        sensor: A validated SensorNode instance.
        estimation_task: Override the default estimation task for this family.
            If empty, the default task is inferred from the sensor family.
        snr: Signal-to-noise ratio (linear, not dB). Default 100.
        target_depth_m: Target depth in meters (for depth-based families).
        n_photons: Number of detected photons (for photon-counting families).

    Returns:
        A frozen CRBResult with ``confidence=ANALYTICAL``.

    Raises:
        ValueError: If the sensor family is not supported for analytical CRB.
    """
    if sensor.family not in ANALYTICAL_FAMILIES:
        raise ValueError(
            f"Analytical CRB not supported for family '{sensor.family.value}'. "
            f"Supported: {sorted(f.value for f in ANALYTICAL_FAMILIES)}"
        )

    family = sensor.family

    if family == SensorFamily.SPAD:
        return _spad_depth_crb(sensor, n_photons, target_depth_m)
    if family == SensorFamily.CW_TOF:
        return _cw_tof_range_crb(sensor, snr)
    if family == SensorFamily.PULSED_DTOF:
        return _pulsed_dtof_range_crb(sensor, snr)
    if family == SensorFamily.LIDAR_FMCW:
        return _fmcw_range_crb(sensor, snr)
    if family == SensorFamily.POLARIMETRIC:
        return _polarimetric_stokes_crb(sensor, n_photons)
    if family == SensorFamily.SPECTRAL:
        return _spectral_unmixing_crb(sensor, snr)
    if family == SensorFamily.STRUCTURED_LIGHT:
        return _structured_light_depth_crb(sensor, target_depth_m, snr)

    # Unreachable if ANALYTICAL_FAMILIES is in sync with dispatch
    raise ValueError(f"No analytical CRB function for '{family.value}'")  # pragma: no cover
