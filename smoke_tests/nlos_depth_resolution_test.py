"""NLOS Depth Resolution Smoke Test.

Simulates confocal NLOS relay-wall imaging at multiple temporal bin widths
to verify that depth resolution follows the physics prediction: dr = c*dt/2.

Sensor: SPAD array (per optimizer recommendation)
Algorithm: LCT-style depth reconstruction (confocal, per Reference Guide)
Paradigm: relay_wall (three-bounce confocal NLOS)

This is a numerical validation — no ray tracing. We:
1. Place a hidden reflector at known depth behind a relay wall
2. Simulate the transient signal (time-of-flight histogram)
3. Reconstruct depth via peak detection
4. Measure depth error across bin widths (8ps to 64ps)
5. Compare against physics prediction (c*dt/2)
"""

import json
import pathlib

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants and scene parameters
# ---------------------------------------------------------------------------

C = 299_792_458.0  # speed of light (m/s)

# Relay wall geometry (from paradigm YAML typical values)
RELAY_WALL_SIZE_M = 2.0
SENSOR_TO_WALL_M = 1.5
WALL_TO_HIDDEN_M = 1.0  # hidden object at 1m behind relay wall

# SPAD parameters (from spad_array YAML)
JITTER_FWHM_PS = 70.0  # timing jitter floor
DEAD_TIME_NS = 15.0

# Temporal bin widths to sweep
BIN_WIDTHS_PS = [8, 16, 32, 48, 64]

# Hidden object: point reflector at known depth
TRUE_DEPTH_M = WALL_TO_HIDDEN_M

# Number of scan points (confocal)
SCAN_POINTS = 64

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_transient(depth_m: float, bin_width_ps: float, jitter_ps: float) -> dict:
    """Simulate a confocal NLOS transient histogram for a point reflector.

    Three-bounce path: sensor → wall → hidden → wall → sensor
    Total path length = 2 * (sensor_to_wall + wall_to_hidden) for confocal.

    Args:
        depth_m: True depth of hidden object behind relay wall.
        bin_width_ps: Temporal bin width in picoseconds.
        jitter_ps: SPAD jitter FWHM in picoseconds.

    Returns:
        Dict with time bins, histogram, and reconstructed depth.
    """
    bin_width_s = bin_width_ps * 1e-12
    jitter_s = jitter_ps * 1e-12

    # Three-bounce round-trip time
    # Confocal: laser and detector at same point on wall
    # Path: sensor → wall → hidden → wall → sensor
    round_trip_m = 2 * (SENSOR_TO_WALL_M + depth_m)
    true_time_s = round_trip_m / C

    # Create time axis (enough bins to cover the round trip + margin)
    max_time_s = 2 * true_time_s
    n_bins = int(np.ceil(max_time_s / bin_width_s))
    time_bins_s = np.arange(n_bins) * bin_width_s

    # Simulate transient: Gaussian peak at true_time with jitter broadening
    # Effective timing sigma = jitter / 2.355 (FWHM to sigma)
    sigma_s = jitter_s / 2.355
    # Add bin quantization noise
    total_sigma = np.sqrt(sigma_s**2 + (bin_width_s / np.sqrt(12))**2)

    histogram = np.exp(-0.5 * ((time_bins_s - true_time_s) / total_sigma) ** 2)
    histogram = histogram / histogram.max()  # normalize peak to 1

    # Add shot noise (Poisson-like)
    rng = np.random.default_rng(42)
    photon_count = 1000
    noisy_histogram = rng.poisson(histogram * photon_count).astype(float)

    # Reconstruct depth: find peak time bin
    peak_bin = np.argmax(noisy_histogram)
    reconstructed_time_s = time_bins_s[peak_bin]

    # Invert three-bounce: depth = (c * t / 2) - sensor_to_wall
    reconstructed_total_depth = C * reconstructed_time_s / 2
    reconstructed_depth_m = reconstructed_total_depth - SENSOR_TO_WALL_M

    # Depth error
    depth_error_m = abs(reconstructed_depth_m - depth_m)

    # Physics prediction: resolution limit = c * dt / 2
    predicted_resolution_m = C * bin_width_s / 2

    return {
        "bin_width_ps": bin_width_ps,
        "n_bins": n_bins,
        "true_depth_m": depth_m,
        "reconstructed_depth_m": float(reconstructed_depth_m),
        "depth_error_m": float(depth_error_m),
        "predicted_resolution_m": float(predicted_resolution_m),
        "error_within_resolution": bool(depth_error_m <= predicted_resolution_m),
        "peak_snr": float(noisy_histogram[peak_bin] / (np.std(noisy_histogram[:peak_bin // 2]) + 1e-10)),
    }


def main() -> None:
    """Run depth resolution sweep and save results."""
    output_dir = pathlib.Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    results = []
    print("NLOS Depth Resolution Smoke Test")
    print("=" * 60)
    print(f"Hidden object depth: {TRUE_DEPTH_M:.2f} m")
    print(f"Relay wall size: {RELAY_WALL_SIZE_M:.1f} m")
    print(f"Sensor-to-wall: {SENSOR_TO_WALL_M:.1f} m")
    print(f"SPAD jitter: {JITTER_FWHM_PS:.0f} ps FWHM")
    print()

    print(f"{'Bin Width':>10} {'Predicted dr':>14} {'Actual Error':>14} {'Within Limit':>14} {'Peak SNR':>10}")
    print("-" * 66)

    for bw in BIN_WIDTHS_PS:
        r = simulate_transient(TRUE_DEPTH_M, bw, JITTER_FWHM_PS)
        results.append(r)
        within = "YES" if r["error_within_resolution"] else "NO"
        print(
            f"{bw:>7} ps"
            f"{r['predicted_resolution_m']*1000:>12.2f} mm"
            f"{r['depth_error_m']*1000:>12.2f} mm"
            f"{within:>14}"
            f"{r['peak_snr']:>10.1f}"
        )

    print()

    # Summary
    all_within = all(r["error_within_resolution"] for r in results)
    print(f"All depth errors within predicted resolution limit: {all_within}")
    print()

    # Key result for the hypothesis
    r32 = next(r for r in results if r["bin_width_ps"] == 32)
    print(f"At 32ps bins:")
    print(f"  Predicted depth resolution: {r32['predicted_resolution_m']*1000:.2f} mm")
    print(f"  Actual depth error: {r32['depth_error_m']*1000:.2f} mm")
    print(f"  Conclusion: Depth resolution limit is ~{r32['predicted_resolution_m']*1000:.1f} mm at 32ps")

    # Save results
    output_path = output_dir / "depth_resolution_results.json"
    with open(output_path, "w") as f:
        json.dump({"scene_id": "scene-001", "results": results, "summary": {
            "hypothesis": "Depth resolution of confocal NLOS scales as c*dt/2",
            "all_within_limit": bool(all_within),
            "bin_32ps_resolution_mm": r32["predicted_resolution_m"] * 1000,
            "bin_32ps_error_mm": r32["depth_error_m"] * 1000,
        }}, f, indent=2)
    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
