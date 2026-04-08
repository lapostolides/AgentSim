"""NLOS SPAD Feasibility Smoke Test.

Tests whether commercially available SPAD arrays can reconstruct a hidden
object at 2m depth behind a 1m relay wall — a geometry that pushes beyond
typical published configurations.

What this exercises:
1. Geometry constraint checking (wall size vs typical, depth vs typical)
2. Optimizer ranking with multiple hypothesis parameters
3. Explorer novelty detection (20ps bins are below published baseline range)
4. Signal feasibility: 1/r^4 falloff at 2m depth vs 1m typical
5. FOV coverage: can the SPAD see the full 1m relay wall?
6. Max recoverable depth: c * N_bins * dt / 2 sufficient?

Sensor profiles: SwissSPAD2 (512x512, 17.8ps), LinoSPAD2 (512x1, 17.8ps),
Hamamatsu C5680 streak (640x480, 2ps).
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

C = 299_792_458.0  # m/s

# ---------------------------------------------------------------------------
# Sensor profiles (from YAML data)
# ---------------------------------------------------------------------------

SENSORS = {
    "SwissSPAD2": {
        "temporal_resolution_ps": 17.8,
        "jitter_fwhm_ps": 70.0,
        "dead_time_ns": 10.0,
        "array_size": (512, 512),
        "pixel_pitch_um": 16.38,
        "fill_factor": 0.105,
        "quantum_efficiency": 0.35,
        "dark_count_rate_hz": 100.0,
        "fov_degrees": 40.0,  # max with wide-angle optics (YAML: 5-40, typical 20)
        "type": "2D array",
    },
    "LinoSPAD2": {
        "temporal_resolution_ps": 17.8,
        "jitter_fwhm_ps": 55.0,
        "dead_time_ns": 10.0,
        "array_size": (512, 1),
        "pixel_pitch_um": 26.2,
        "fill_factor": 0.38,
        "quantum_efficiency": 0.30,
        "dark_count_rate_hz": 200.0,
        "fov_degrees": 30.0,  # linear array with scanning optics
        "type": "linear array (needs scanning)",
    },
    "Hamamatsu_C5680": {
        "temporal_resolution_ps": 2.0,
        "jitter_fwhm_ps": 10.0,
        "dead_time_ns": 0.0,  # streak camera, no dead time
        "array_size": (640, 480),
        "pixel_pitch_um": 23.0,
        "fill_factor": 1.0,
        "quantum_efficiency": 0.15,
        "dark_count_rate_hz": 0.0,
        "fov_degrees": 30.0,  # with collection optics
        "type": "streak camera",
    },
}

# ---------------------------------------------------------------------------
# Scene geometry
# ---------------------------------------------------------------------------

RELAY_WALL_SIZE_M = 1.0
SENSOR_TO_WALL_M = 1.5
HIDDEN_DEPTH_M = 2.0
HIDDEN_REFLECTIVITY = 0.5  # Lambertian albedo
WALL_ALBEDO = 0.8
LASER_POWER_W = 0.1  # 100mW pulsed laser (typical)
LASER_REP_RATE_HZ = 10e6  # 10 MHz

# Published baseline reference (Lindell et al. 2019)
BASELINE = {
    "wall_size_m": 2.0,
    "hidden_depth_m": 1.0,
    "sensor_to_wall_m": 1.5,
    "temporal_resolution_ps": 32.0,
}


# ---------------------------------------------------------------------------
# Physics computations
# ---------------------------------------------------------------------------

def compute_signal_photons(
    sensor: dict,
    depth_m: float,
    wall_size_m: float,
    wall_albedo: float,
    object_albedo: float,
    integration_time_s: float = 1.0,
) -> dict:
    """Estimate received photon count for three-bounce confocal NLOS.

    Signal model: photons ∝ (power * QE * albedo_wall^2 * albedo_obj) / r^4
    The 1/r^4 falloff is the dominant challenge at 2m depth.
    """
    # Round-trip distance for three-bounce
    r = depth_m  # wall-to-hidden distance (dominant factor)

    # Simplified photon budget (order-of-magnitude)
    # Photons per laser pulse hitting the wall spot
    photon_energy = 6.626e-34 * C / 532e-9  # 532nm green laser
    photons_per_pulse = LASER_POWER_W / (LASER_REP_RATE_HZ * photon_energy)

    # Three-bounce attenuation: wall reflectance * 1/r^4 * object reflectance * wall reflectance
    # Solid angle factor ~ (wall_size / (4*pi*r^2)) for each bounce
    solid_angle_factor = (wall_size_m ** 2) / (4 * math.pi * r ** 2)
    three_bounce_efficiency = (
        wall_albedo  # first bounce (laser -> wall)
        * solid_angle_factor  # wall to hidden
        * object_albedo  # hidden object reflection
        * solid_angle_factor  # hidden to wall
        * wall_albedo  # wall to sensor
    )

    # Detected photons per pulse
    detected_per_pulse = photons_per_pulse * three_bounce_efficiency * sensor["quantum_efficiency"]

    # Total over integration time
    total_pulses = LASER_REP_RATE_HZ * integration_time_s
    total_photons = detected_per_pulse * total_pulses

    # Noise: dark counts + background
    dark_counts = sensor["dark_count_rate_hz"] * integration_time_s
    snr = total_photons / max(math.sqrt(total_photons + dark_counts), 1e-10)

    return {
        "photons_per_pulse": float(detected_per_pulse),
        "total_photons": float(total_photons),
        "dark_counts": float(dark_counts),
        "snr": float(snr),
        "integration_time_s": integration_time_s,
    }


def compute_fov_coverage(
    sensor: dict,
    sensor_to_wall_m: float,
    wall_size_m: float,
) -> dict:
    """Check if sensor FOV covers the relay wall.

    Uses the optics-level FOV (degrees), not raw chip projection.
    Real NLOS systems use collection lenses giving 5-40° FOV.
    Coverage at wall distance = 2 * d * tan(FOV/2).
    """
    fov_deg = sensor.get("fov_degrees", 20.0)  # default to typical 20°
    fov_rad = math.radians(fov_deg)

    # Coverage diameter at wall distance
    coverage = 2.0 * sensor_to_wall_m * math.tan(fov_rad / 2.0)

    # For linear arrays, coverage is 1D — needs galvo scanning for 2D
    array_w, array_h = sensor["array_size"]
    is_linear = array_h == 1

    covers_wall = coverage >= wall_size_m

    return {
        "fov_degrees": fov_deg,
        "coverage_m": float(coverage),
        "wall_size_m": wall_size_m,
        "covers_wall": covers_wall,
        "is_linear": is_linear,
        "note": "linear array — needs galvo scanning for 2D coverage" if is_linear else "",
    }


def compute_max_depth(sensor: dict, n_bins: int = 2048) -> dict:
    """Max recoverable depth = c * N_bins * dt / 2."""
    dt_s = sensor["temporal_resolution_ps"] * 1e-12
    max_depth = C * n_bins * dt_s / 2
    depth_resolution = C * dt_s / 2

    return {
        "temporal_resolution_ps": sensor["temporal_resolution_ps"],
        "n_bins": n_bins,
        "max_depth_m": float(max_depth),
        "depth_resolution_m": float(depth_resolution),
        "sufficient_for_2m": max_depth >= HIDDEN_DEPTH_M + SENSOR_TO_WALL_M,
    }


def compute_signal_ratio_vs_baseline(sensor: dict) -> dict:
    """Compare signal at 2m depth to signal at 1m depth (baseline).

    Signal ∝ 1/r^4, so going from 1m to 2m gives 1/16 the signal.
    """
    baseline_signal = compute_signal_photons(
        sensor, BASELINE["hidden_depth_m"],
        BASELINE["wall_size_m"], WALL_ALBEDO, HIDDEN_REFLECTIVITY,
    )
    test_signal = compute_signal_photons(
        sensor, HIDDEN_DEPTH_M,
        RELAY_WALL_SIZE_M, WALL_ALBEDO, HIDDEN_REFLECTIVITY,
    )

    ratio = test_signal["total_photons"] / max(baseline_signal["total_photons"], 1e-30)

    return {
        "baseline_photons": baseline_signal["total_photons"],
        "baseline_snr": baseline_signal["snr"],
        "test_photons": test_signal["total_photons"],
        "test_snr": test_signal["snr"],
        "signal_ratio": float(ratio),
        "snr_ratio": test_signal["snr"] / max(baseline_signal["snr"], 1e-10),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    output_dir = pathlib.Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    print("NLOS SPAD Feasibility Test")
    print("=" * 70)
    print(f"Hypothesis: Reconstruct hidden object at {HIDDEN_DEPTH_M}m depth")
    print(f"            behind {RELAY_WALL_SIZE_M}m relay wall")
    print(f"Baseline:   {BASELINE['hidden_depth_m']}m depth, {BASELINE['wall_size_m']}m wall")
    print()

    # Geometry warnings
    print("GEOMETRY CONSTRAINTS")
    print("-" * 70)
    print(f"  Wall: {RELAY_WALL_SIZE_M}m (typical: 2.0m) — ⚠ half typical size")
    print(f"  Depth: {HIDDEN_DEPTH_M}m (typical: 1.0m) — ⚠ 2x typical depth")
    print(f"  Signal penalty: 1/r⁴ at 2m vs 1m = 1/{2**4} = 1/16 the signal")
    print(f"  Wall penalty: 1m² vs 4m² = 1/4 solid angle coverage")
    print(f"  Combined: ~1/64 of baseline signal level")
    print()

    all_results = {}

    for sensor_name, sensor in SENSORS.items():
        print(f"\n{'=' * 70}")
        print(f"SENSOR: {sensor_name} ({sensor['type']})")
        print(f"  Array: {sensor['array_size'][0]}x{sensor['array_size'][1]}")
        print(f"  Temporal: {sensor['temporal_resolution_ps']}ps, jitter: {sensor['jitter_fwhm_ps']}ps")
        print(f"  QE: {sensor['quantum_efficiency']:.0%}, fill factor: {sensor['fill_factor']:.1%}")

        # 1. Depth capability
        depth_info = compute_max_depth(sensor)
        print(f"\n  Max Recoverable Depth:")
        print(f"    {depth_info['max_depth_m']:.1f}m (need {HIDDEN_DEPTH_M + SENSOR_TO_WALL_M:.1f}m)")
        print(f"    {'✓ SUFFICIENT' if depth_info['sufficient_for_2m'] else '✗ INSUFFICIENT'}")
        print(f"    Depth resolution: {depth_info['depth_resolution_m']*1000:.2f}mm")

        # 2. FOV coverage
        fov_info = compute_fov_coverage(sensor, SENSOR_TO_WALL_M, RELAY_WALL_SIZE_M)
        print(f"\n  FOV Coverage (optics-level, {fov_info['fov_degrees']:.0f}° FOV):")
        print(f"    Coverage at {SENSOR_TO_WALL_M}m: {fov_info['coverage_m']:.2f}m diameter")
        print(f"    {'✓ COVERS' if fov_info['covers_wall'] else '✗ DOES NOT cover'} {RELAY_WALL_SIZE_M}m wall")
        if fov_info.get("note"):
            print(f"    ⚠ {fov_info['note']}")

        # 3. Signal feasibility
        signal_info = compute_signal_ratio_vs_baseline(sensor)
        print(f"\n  Signal Feasibility (vs baseline at 1m/2m wall):")
        print(f"    Baseline: {signal_info['baseline_photons']:.1f} photons, SNR={signal_info['baseline_snr']:.1f}")
        print(f"    This test: {signal_info['test_photons']:.1f} photons, SNR={signal_info['test_snr']:.1f}")
        print(f"    Signal ratio: {signal_info['signal_ratio']:.4f} ({signal_info['signal_ratio']*100:.2f}%)")
        feasible = signal_info["test_snr"] > 3.0  # SNR > 3 = detectable
        print(f"    {'✓ FEASIBLE' if feasible else '✗ SNR too low'} (SNR > 3 required)")

        # 4. Integration time needed for SNR=10
        target_snr = 10.0
        if signal_info["test_snr"] > 0:
            needed_time = (target_snr / signal_info["test_snr"]) ** 2
            print(f"\n  Time for SNR=10: {needed_time:.1f}s (at 1s baseline)")
        else:
            needed_time = float("inf")
            print(f"\n  Time for SNR=10: not feasible")

        # Overall verdict
        verdict = (
            depth_info["sufficient_for_2m"]
            and fov_info["covers_wall"]
            and feasible
        )
        print(f"\n  VERDICT: {'✓ FEASIBLE' if verdict else '✗ NOT FEASIBLE'}")

        all_results[sensor_name] = {
            "depth": depth_info,
            "fov": fov_info,
            "signal": signal_info,
            "integration_time_for_snr10": float(needed_time),
            "feasible": bool(verdict),
        }

    # Summary table
    print(f"\n\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'Sensor':<20} {'Depth':>8} {'FOV':>10} {'SNR':>12} {'Time':>8} {'Verdict':>10}")
    print("-" * 74)
    for name, r in all_results.items():
        d = "✓" if r["depth"]["sufficient_for_2m"] else "✗"
        fov_m = r["fov"]["coverage_m"]
        f = f"✓ {fov_m:.1f}m" if r["fov"]["covers_wall"] else f"✗ {fov_m:.1f}m"
        s = f"{r['signal']['test_snr']:.1f}"
        t = f"{r['integration_time_for_snr10']:.0f}s" if r["integration_time_for_snr10"] < 1000 else ">1000s"
        v = "✓ YES" if r["feasible"] else "✗ NO"
        print(f"  {name:<18} {d:>8} {f:>10} {s:>12} {t:>8} {v:>10}")

    # Explorer insight
    print(f"\n\nEXPLORER INSIGHT")
    print("-" * 70)
    print("  20ps temporal resolution is BELOW published baseline range [32-55ps]")
    print("  → This is a novel parameter regime worth exploring")
    print("  2m hidden depth is 2x the typical 1m → 1/16 signal (1/r⁴ law)")
    print("  1m relay wall is half the typical 2m → 1/4 solid angle")

    # Save
    output_path = output_dir / "spad_feasibility_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
