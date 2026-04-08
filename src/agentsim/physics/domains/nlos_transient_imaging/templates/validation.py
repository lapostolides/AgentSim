"""Transient validation: OPL-to-time conversion and peak timing comparison.

Provides utilities for validating transient rendering outputs against
expected physical values. Converts between optical path length (meters)
and time (nanoseconds), extracts peak timing from transient data arrays,
and compares measured vs expected timing within a tolerance.

No mitsuba imports — works with raw numpy arrays from any renderer.
"""

from __future__ import annotations

import numpy as np
import structlog
from pydantic import BaseModel

SPEED_OF_LIGHT: float = 299_792_458.0

logger = structlog.get_logger()


class TransientValidationResult(BaseModel, frozen=True):
    """Result of comparing measured vs expected peak timing.

    Fields:
        measured_peak_ns: Measured peak time in nanoseconds.
        expected_peak_ns: Expected peak time in nanoseconds.
        delta_ns: Absolute difference between measured and expected.
        tolerance_ns: Maximum allowed difference for a match.
        match: Whether delta_ns <= tolerance_ns.
    """

    measured_peak_ns: float
    expected_peak_ns: float
    delta_ns: float
    tolerance_ns: float
    match: bool


def opl_to_time_ns(opl_m: float) -> float:
    """Convert optical path length (meters) to time (nanoseconds).

    Args:
        opl_m: Optical path length in meters.

    Returns:
        Time in nanoseconds.
    """
    return (opl_m / SPEED_OF_LIGHT) * 1e9


def time_ns_to_opl(time_ns: float) -> float:
    """Convert time (nanoseconds) to optical path length (meters).

    Args:
        time_ns: Time in nanoseconds.

    Returns:
        Optical path length in meters.
    """
    return time_ns * 1e-9 * SPEED_OF_LIGHT


def extract_peak_timing_ns(
    transient_data: np.ndarray,
    bin_width_opl: float,
    start_opl: float = 0.0,
) -> float:
    """Extract peak timing from a transient data array.

    Sums over spatial (W, H) and channel (C) dimensions to get a
    temporal profile, finds the argmax bin, and converts to nanoseconds.

    Args:
        transient_data: Array of shape (W, H, T, C) with transient data.
        bin_width_opl: Optical path length per temporal bin (meters).
        start_opl: OPL offset of the first temporal bin (meters).

    Returns:
        Peak timing in nanoseconds.
    """
    # Sum over W (axis 0), H (axis 1), and C (axis 3) to get temporal profile
    temporal_profile = transient_data.sum(axis=(0, 1, 3))

    # Handle all-zero or empty data
    if temporal_profile.max() == 0.0:
        logger.warning(
            "transient_data_all_zero",
            start_opl=start_opl,
        )
        return opl_to_time_ns(start_opl)

    peak_bin = int(np.argmax(temporal_profile))
    peak_opl = start_opl + peak_bin * bin_width_opl
    result = opl_to_time_ns(peak_opl)

    logger.debug(
        "peak_timing_extracted",
        peak_bin=peak_bin,
        peak_opl=peak_opl,
        peak_ns=result,
    )
    return result


def validate_peak_timing(
    measured_peak_ns: float,
    expected_peak_ns: float,
    tolerance_ns: float = 0.5,
) -> TransientValidationResult:
    """Compare measured vs expected peak timing within tolerance.

    Args:
        measured_peak_ns: Measured peak time in nanoseconds.
        expected_peak_ns: Expected peak time in nanoseconds.
        tolerance_ns: Maximum allowed absolute difference (default 0.5 ns).

    Returns:
        TransientValidationResult with match status and delta.
    """
    delta_ns = abs(measured_peak_ns - expected_peak_ns)
    result = TransientValidationResult(
        measured_peak_ns=measured_peak_ns,
        expected_peak_ns=expected_peak_ns,
        delta_ns=delta_ns,
        tolerance_ns=tolerance_ns,
        match=delta_ns <= tolerance_ns,
    )

    logger.info(
        "peak_timing_validated",
        match=result.match,
        delta_ns=delta_ns,
        tolerance_ns=tolerance_ns,
    )
    return result
