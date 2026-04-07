"""NLOS transient imaging geometry validation.

Deterministic checks for three-bounce light path feasibility,
sensor FOV coverage, and temporal resolution sufficiency.
No LLM calls, no side effects, pure geometry math.
"""

from __future__ import annotations

import math

import numpy as np

from agentsim.physics.constants import lookup_constant
from agentsim.physics.models import CheckResult, Severity

# Speed of light from the constants registry (m/s).
_c_const = lookup_constant("speed_of_light")
SPEED_OF_LIGHT: float = _c_const.magnitude if _c_const is not None else 299_792_458.0

# Minimum FOV-to-wall coverage ratio for practical scanning.
_MIN_FOV_COVERAGE_RATIO = 0.05


def _to_array(v: tuple[float, float, float]) -> np.ndarray:
    """Convert a 3-tuple to a numpy array."""
    return np.array(v, dtype=np.float64)


def _safe_normalize(v: np.ndarray) -> np.ndarray | None:
    """Normalize a vector, returning None if zero-length."""
    norm = float(np.linalg.norm(v))
    if norm < 1e-12:
        return None
    return v / norm


# ---------------------------------------------------------------------------
# Three-bounce geometry check
# ---------------------------------------------------------------------------


def check_three_bounce_geometry(
    sensor_pos: tuple[float, float, float],
    sensor_look_at: tuple[float, float, float],
    relay_wall_pos: tuple[float, float, float],
    relay_wall_normal: tuple[float, float, float],
    relay_wall_size: float,
    hidden_objects: tuple[tuple[float, float, float], ...],
    occluder_pos: tuple[float, float, float] | None = None,
    occluder_size: tuple[float, float, float] | None = None,
    sensor_fov_deg: float = 20.0,
) -> tuple[CheckResult, ...]:
    """Validate three-bounce NLOS light path feasibility.

    Checks:
    a) Sensor can see relay wall (direction within FOV cone, wall faces sensor).
    b) Relay wall normal faces sensor hemisphere.
    c) Hidden objects behind occluder (only if occluder provided).
    d) Return path: relay wall can "see" hidden objects.

    Args:
        sensor_pos: Sensor position in 3D.
        sensor_look_at: Point the sensor is looking at.
        relay_wall_pos: Center of the relay wall.
        relay_wall_normal: Outward normal of relay wall (toward sensor).
        relay_wall_size: Side length of the relay wall (square).
        hidden_objects: Positions of hidden objects behind the wall.
        occluder_pos: Center of the occluder (optional).
        occluder_size: Dimensions (width, depth, height) of the occluder (optional).
        sensor_fov_deg: Sensor field of view in degrees.

    Returns:
        Tuple of CheckResult with findings.
    """
    results: list[CheckResult] = []

    s_pos = _to_array(sensor_pos)
    s_look = _to_array(sensor_look_at)
    w_pos = _to_array(relay_wall_pos)
    w_normal = _to_array(relay_wall_normal)

    # Sensor look direction
    look_dir = _safe_normalize(s_look - s_pos)
    if look_dir is None:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.ERROR,
            message="Sensor look-at direction is zero-length (sensor_pos == sensor_look_at)",
        ))
        return tuple(results)

    # Wall normal normalization
    w_normal_hat = _safe_normalize(w_normal)
    if w_normal_hat is None:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.ERROR,
            message="Relay wall normal is zero-length",
        ))
        return tuple(results)

    # Direction from sensor to wall center
    sensor_to_wall = w_pos - s_pos
    sensor_to_wall_hat = _safe_normalize(sensor_to_wall)
    if sensor_to_wall_hat is None:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.ERROR,
            message="Sensor is at the same position as the relay wall center",
        ))
        return tuple(results)

    # (b) Check wall normal faces sensor hemisphere
    # Wall normal should point toward sensor: dot(normal, sensor-wall direction) > 0
    # i.e., dot(normal, -(sensor_to_wall)) > 0
    wall_to_sensor_hat = -sensor_to_wall_hat
    normal_dot = float(np.dot(w_normal_hat, wall_to_sensor_hat))
    if normal_dot <= 0:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.ERROR,
            message=(
                f"Relay wall normal is not facing the sensor "
                f"(dot product with wall-to-sensor direction = {normal_dot:.3f}). "
                f"The wall normal should point toward the sensor."
            ),
        ))

    # (a) Check sensor can see relay wall: sensor look-at direction within FOV cone
    cos_angle = float(np.dot(look_dir, sensor_to_wall_hat))
    cos_angle = max(-1.0, min(1.0, cos_angle))
    angle_to_wall_deg = math.degrees(math.acos(cos_angle))
    half_fov = sensor_fov_deg / 2.0

    if angle_to_wall_deg > half_fov:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.ERROR,
            message=(
                f"Sensor cannot see relay wall: wall center is at {angle_to_wall_deg:.1f} deg "
                f"from sensor look-at direction, but sensor FOV half-angle is {half_fov:.1f} deg"
            ),
        ))

    # (c) Occluder check (only if occluder is provided)
    if occluder_pos is not None and occluder_size is not None:
        o_pos = _to_array(occluder_pos)
        o_size = _to_array(occluder_size)

        # Check if occluder blocks sensor-to-wall path.
        # Simplified: does the line from sensor to wall center pass through
        # the occluder's bounding box?
        if _line_intersects_box(s_pos, w_pos, o_pos, o_size):
            results.append(CheckResult(
                check="nlos_three_bounce",
                severity=Severity.ERROR,
                message=(
                    "Occluder blocks the sensor-to-relay-wall light path. "
                    "The sensor cannot illuminate or observe the relay wall."
                ),
            ))

        # Check hidden objects are on far side of occluder from sensor
        for i, h_obj in enumerate(hidden_objects):
            h_pos = _to_array(h_obj)
            # If hidden object is on the sensor side of the occluder, warning
            sensor_side = float(np.dot(s_pos - o_pos, w_normal_hat))
            hidden_side = float(np.dot(h_pos - o_pos, w_normal_hat))
            if sensor_side * hidden_side > 0:
                results.append(CheckResult(
                    check="nlos_three_bounce",
                    severity=Severity.WARNING,
                    message=(
                        f"Hidden object {i} is on the same side of the occluder "
                        f"as the sensor (not properly hidden)"
                    ),
                ))

    # (d) Return path: hidden objects should be behind the wall (opposite
    # side from sensor, i.e., on the side the wall normal does NOT point to).
    for i, h_obj in enumerate(hidden_objects):
        h_pos = _to_array(h_obj)
        wall_to_hidden = h_pos - w_pos
        # Hidden object should be on the back side of the wall
        # (opposite to where the normal points, which is toward the sensor)
        dot_hidden = float(np.dot(w_normal_hat, wall_to_hidden))
        if dot_hidden < 0:
            # Hidden object is on the same side as the sensor (front side)
            results.append(CheckResult(
                check="nlos_three_bounce",
                severity=Severity.WARNING,
                message=(
                    f"Hidden object {i} at {h_obj} is on the sensor side of the "
                    f"relay wall, not behind it"
                ),
            ))

    # If no issues found, add a passing result
    if not results:
        results.append(CheckResult(
            check="nlos_three_bounce",
            severity=Severity.INFO,
            message="Three-bounce geometry is valid",
        ))

    return tuple(results)


def _line_intersects_box(
    start: np.ndarray,
    end: np.ndarray,
    box_center: np.ndarray,
    box_size: np.ndarray,
) -> bool:
    """Check if a line segment intersects an axis-aligned bounding box.

    Uses the slab method for ray-AABB intersection.

    Args:
        start: Start point of the line segment.
        end: End point of the line segment.
        box_center: Center of the box.
        box_size: Dimensions (width, depth, height) of the box.

    Returns:
        True if the line segment intersects the box.
    """
    half_size = box_size / 2.0
    box_min = box_center - half_size
    box_max = box_center + half_size

    direction = end - start
    length = float(np.linalg.norm(direction))
    if length < 1e-12:
        return False

    direction = direction / length

    t_min = 0.0
    t_max = length

    for i in range(3):
        if abs(direction[i]) < 1e-12:
            # Ray is parallel to slab
            if start[i] < box_min[i] or start[i] > box_max[i]:
                return False
        else:
            inv_d = 1.0 / direction[i]
            t1 = (box_min[i] - start[i]) * inv_d
            t2 = (box_max[i] - start[i]) * inv_d
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return False

    return True


# ---------------------------------------------------------------------------
# Sensor FOV check
# ---------------------------------------------------------------------------


def check_sensor_fov(
    sensor_pos: tuple[float, float, float],
    sensor_look_at: tuple[float, float, float],
    sensor_fov_deg: float,
    relay_wall_pos: tuple[float, float, float],
    relay_wall_size: float,
) -> tuple[CheckResult, ...]:
    """Validate sensor FOV covers the relay wall adequately for scanning.

    Computes the angular extent of the relay wall as seen from the sensor
    and compares with the sensor FOV. If the FOV is too narrow relative
    to the wall extent (< 5% coverage), reports an ERROR.

    Args:
        sensor_pos: Sensor position in 3D.
        sensor_look_at: Point the sensor is looking at.
        sensor_fov_deg: Sensor field of view in degrees.
        relay_wall_pos: Center of the relay wall.
        relay_wall_size: Side length of the relay wall (square).

    Returns:
        Tuple of CheckResult with FOV assessment.
    """
    s_pos = _to_array(sensor_pos)
    w_pos = _to_array(relay_wall_pos)

    distance = float(np.linalg.norm(w_pos - s_pos))
    if distance < 1e-12:
        return (CheckResult(
            check="nlos_sensor_fov",
            severity=Severity.ERROR,
            message="Sensor is at the same position as the relay wall",
        ),)

    # Angular extent of the wall as seen from the sensor (full angle)
    wall_half_angle_rad = math.atan2(relay_wall_size / 2.0, distance)
    wall_angular_extent_deg = math.degrees(2.0 * wall_half_angle_rad)

    # Coverage ratio: what fraction of the wall does the FOV subtend
    coverage_ratio = sensor_fov_deg / wall_angular_extent_deg if wall_angular_extent_deg > 0 else 0

    if coverage_ratio < _MIN_FOV_COVERAGE_RATIO:
        return (CheckResult(
            check="nlos_sensor_fov",
            severity=Severity.ERROR,
            message=(
                f"Sensor FOV ({sensor_fov_deg:.1f} deg) is too narrow to practically "
                f"scan the relay wall (wall subtends {wall_angular_extent_deg:.1f} deg, "
                f"coverage ratio {coverage_ratio:.3f} < {_MIN_FOV_COVERAGE_RATIO})"
            ),
        ),)

    return (CheckResult(
        check="nlos_sensor_fov",
        severity=Severity.INFO,
        message=(
            f"Sensor FOV ({sensor_fov_deg:.1f} deg) provides "
            f"{coverage_ratio:.1%} coverage of relay wall "
            f"({wall_angular_extent_deg:.1f} deg extent)"
        ),
    ),)


# ---------------------------------------------------------------------------
# Temporal resolution check
# ---------------------------------------------------------------------------


def check_temporal_resolution(
    time_bin_ps: float,
    min_feature_separation_m: float,
    wall_to_object_distance_m: float | None = None,
) -> tuple[CheckResult, ...]:
    """Validate time-bin width resolves hidden scene geometry.

    Uses round-trip formula: spatial_resolution = c * dt / 2
    (Pitfall 2: ALWAYS round-trip, not one-way).

    Args:
        time_bin_ps: Time-bin width in picoseconds.
        min_feature_separation_m: Minimum feature separation to resolve (meters).
        wall_to_object_distance_m: Optional distance for additional context.

    Returns:
        Tuple of CheckResult with temporal resolution assessment.
    """
    dt_seconds = time_bin_ps * 1e-12
    # Round-trip spatial resolution (c * dt / 2)
    spatial_resolution_m = SPEED_OF_LIGHT * dt_seconds / 2.0

    if spatial_resolution_m >= min_feature_separation_m:
        return (CheckResult(
            check="nlos_temporal_resolution",
            severity=Severity.ERROR,
            message=(
                f"Temporal resolution insufficient: time-bin {time_bin_ps:.0f} ps gives "
                f"spatial resolution {spatial_resolution_m * 1000:.1f} mm (round-trip c*dt/2), "
                f"but minimum feature separation is "
                f"{min_feature_separation_m * 1000:.1f} mm"
            ),
            details=(
                f"spatial_resolution_m={spatial_resolution_m:.6f}, "
                f"min_feature_separation_m={min_feature_separation_m:.6f}"
            ),
        ),)

    return (CheckResult(
        check="nlos_temporal_resolution",
        severity=Severity.INFO,
        message=(
            f"Temporal resolution sufficient: time-bin {time_bin_ps:.0f} ps gives "
            f"spatial resolution {spatial_resolution_m * 1000:.1f} mm (round-trip c*dt/2), "
            f"min feature separation is {min_feature_separation_m * 1000:.1f} mm"
        ),
        details=(
            f"spatial_resolution_m={spatial_resolution_m:.6f}, "
            f"min_feature_separation_m={min_feature_separation_m:.6f}"
        ),
    ),)
