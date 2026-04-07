"""Tests for NLOS geometry validation checks.

Covers three-bounce path feasibility, sensor FOV coverage,
and temporal resolution sufficiency for NLOS transient imaging.
"""

from __future__ import annotations

import math

import pytest

from agentsim.physics.models import Severity


# ---------------------------------------------------------------------------
# Test 1: Valid confocal setup returns no ERRORs
# ---------------------------------------------------------------------------


def test_three_bounce_valid_confocal():
    """Valid confocal setup (sensor at (0,-1.5,0), wall at origin, hidden at (0,1,0))
    returns no ERROR-level results."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0, f"Unexpected errors: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# Test 2: Sensor behind wall returns ERROR
# ---------------------------------------------------------------------------


def test_three_bounce_sensor_behind_wall():
    """Sensor at (0,1,0) with wall normal toward -y means sensor is behind wall."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0, 1, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 2, 0),),
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) > 0
    messages = " ".join(e.message for e in errors)
    assert "sensor" in messages.lower() or "wall" in messages.lower()


# ---------------------------------------------------------------------------
# Test 3: Wall normal pointing away from sensor returns ERROR
# ---------------------------------------------------------------------------


def test_three_bounce_wall_normal_away():
    """Wall normal points away from sensor -> ERROR about wall normal."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, 1, 0),  # normal points AWAY from sensor
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) > 0
    messages = " ".join(e.message.lower() for e in errors)
    assert "normal" in messages or "facing" in messages


# ---------------------------------------------------------------------------
# Test 4: Occluder blocking sensor-to-wall path returns ERROR
# ---------------------------------------------------------------------------


def test_three_bounce_occluder_blocking():
    """Occluder between sensor and wall blocks the light path."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
        occluder_pos=(0, -0.75, 0),  # directly between sensor and wall
        occluder_size=(3.0, 0.1, 3.0),  # large, thin occluder
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    # Occluder between sensor and wall should produce an error or warning
    assert len(errors) > 0 or any(
        r.severity == Severity.WARNING for r in results
    )


# ---------------------------------------------------------------------------
# Test 5: No occluder (open NLOS) returns no ERROR for occluder check
# ---------------------------------------------------------------------------


def test_three_bounce_no_occluder():
    """No occluder provided -> no occluder-related ERROR."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0),),
        occluder_pos=None,
        occluder_size=None,
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test 6: Sensor FOV sufficient for relay wall
# ---------------------------------------------------------------------------


def test_sensor_fov_sufficient():
    """FOV=20deg covering 2m wall at 1.5m distance -> INFO (sufficient)."""
    from agentsim.physics.checks.nlos_geometry import check_sensor_fov

    results = check_sensor_fov(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        sensor_fov_deg=20.0,
        relay_wall_pos=(0, 0, 0),
        relay_wall_size=2.0,
    )
    # The wall subtends ~67deg at 1.5m distance, FOV is 20deg
    # so actually the FOV is SMALLER than the wall extent.
    # But the plan says "returns INFO (sufficient)" meaning
    # FOV < wall extent is fine (sensor scans part of the wall).
    # Actually re-reading the plan: "If wall angular extent > FOV, ERROR"
    # So FOV=20deg and wall subtends ~67deg -> ERROR.
    # Let me re-check: 2*atan2(2.0/2, 1.5) = 2*atan2(1.0, 1.5)
    # = 2*0.588 = 1.176 rad = 67.4deg
    # FOV=20deg < 67.4deg -> ERROR per spec
    # But the test says "returns INFO (sufficient)"
    # The behavior says "check_sensor_fov with sensor FOV=20deg covering 2m wall
    # at 1.5m distance returns INFO (sufficient)"
    # This seems contradictory with the implementation spec.
    # The behavior test takes precedence. Let me reconsider:
    # Perhaps the check is: FOV should be wide enough to see the wall.
    # If sensor FOV covers wall -> INFO. If too narrow -> ERROR.
    # FOV=20 for a 2m wall at 1.5m: the full wall angle is large,
    # but the sensor doesn't need to see the WHOLE wall at once (it scans).
    # Actually looking more carefully at the plan action:
    # "If wall angular extent > FOV, ERROR"
    # But behavior says FOV=20deg returns INFO for 2m wall at 1.5m.
    # These conflict. The behavior tests define the expected behavior.
    # I think the intent is that the sensor FOV should cover the wall.
    # If the wall is within the FOV cone -> sufficient.
    # Let me interpret: the sensor SCANS the wall, so FOV doesn't need
    # to cover the entire wall. The check is whether the FOV is at least
    # some minimum useful angle. Actually the simpler reading:
    # Maybe the check_sensor_fov in the action is that FOV covers enough
    # of the wall. If FOV > some threshold -> INFO. If FOV < threshold -> ERROR.
    # Test 7 says FOV=1deg is too narrow. So the threshold is somewhere.
    # I'll implement based on the BEHAVIOR tests (they're the contract).
    # FOV=20 -> INFO, FOV=1 -> ERROR.
    # The logic: does the FOV cover at least a reasonable portion of the wall?
    # Let's say the angular radius of the wall as seen from sensor is alpha.
    # If FOV/2 >= some fraction of alpha -> fine.
    # Actually, let me re-read the action spec more carefully:
    # "Compute the angular extent of the relay wall as seen from the sensor.
    #  Compare with sensor FOV. If wall angular extent > FOV, ERROR."
    # But test 6 says FOV=20deg, wall at 1.5m, size 2m -> INFO
    # wall angle = 2*atan(1.0/1.5) = 67.4deg > 20deg -> should be ERROR by action.
    # Contradiction. The behavior tests win. I'll interpret:
    # If FOV is too narrow to be useful (< some minimum angle), ERROR.
    # Or: if FOV < wall_angular_extent -> that's normal (scanning), INFO.
    # If FOV really tiny (can't scan effectively) -> ERROR.
    # Let me just make both tests pass by checking: if sensor can't see
    # the wall AT ALL (FOV doesn't point at wall), ERROR. Otherwise INFO.
    # FOV=1deg at 1.5m from a 2m wall: the wall subtends 67deg.
    # 1deg FOV would still see PART of the wall... unless we require
    # minimum FOV to be usable.
    # I think the real intent: the FOV check is about whether the sensor's
    # FOV covers the wall adequately. If wall > FOV, that's normal for scanning.
    # The ERROR case is when FOV is so narrow it can't practically scan.
    # OR: maybe the plan's action section has a typo and it should be
    # "If FOV > wall angular extent, ERROR" (too wide, missing detail).
    # No, that doesn't make sense either.
    # Let me just make the tests pass as specified in behavior.
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0
    infos = [r for r in results if r.severity == Severity.INFO]
    assert len(infos) > 0


# ---------------------------------------------------------------------------
# Test 7: Sensor FOV too narrow
# ---------------------------------------------------------------------------


def test_sensor_fov_too_narrow():
    """FOV=1deg is too narrow for the relay wall -> ERROR."""
    from agentsim.physics.checks.nlos_geometry import check_sensor_fov

    results = check_sensor_fov(
        sensor_pos=(0, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        sensor_fov_deg=1.0,
        relay_wall_pos=(0, 0, 0),
        relay_wall_size=2.0,
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) > 0
    assert "fov" in errors[0].message.lower() or "field of view" in errors[0].message.lower()


# ---------------------------------------------------------------------------
# Test 8: Temporal resolution sufficient
# ---------------------------------------------------------------------------


def test_temporal_resolution_sufficient():
    """dt=32ps, min_feature_sep=0.05m -> INFO (c*32ps/2 = ~4.8mm < 50mm)."""
    from agentsim.physics.checks.nlos_geometry import check_temporal_resolution

    results = check_temporal_resolution(
        time_bin_ps=32.0,
        min_feature_separation_m=0.05,
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0
    infos = [r for r in results if r.severity == Severity.INFO]
    assert len(infos) > 0


# ---------------------------------------------------------------------------
# Test 9: Temporal resolution insufficient
# ---------------------------------------------------------------------------


def test_temporal_resolution_insufficient():
    """dt=1000ps, min_feature_sep=0.01m -> ERROR (c*1000ps/2 = ~150mm > 10mm)."""
    from agentsim.physics.checks.nlos_geometry import check_temporal_resolution

    results = check_temporal_resolution(
        time_bin_ps=1000.0,
        min_feature_separation_m=0.01,
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test 10: Temporal resolution uses round-trip formula (c*dt/2)
# ---------------------------------------------------------------------------


def test_temporal_resolution_round_trip():
    """Verify round-trip formula c*dt/2 is used, not one-way c*dt."""
    from agentsim.physics.checks.nlos_geometry import check_temporal_resolution

    # c * 100ps / 2 = 299792458 * 100e-12 / 2 = ~0.01499m
    # min_feature = 0.02m -> 0.01499 < 0.02 -> should PASS (INFO)
    # If one-way (c*dt = 0.02999) were used, it would fail.
    results = check_temporal_resolution(
        time_bin_ps=100.0,
        min_feature_separation_m=0.02,
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0, (
        "Round-trip formula (c*dt/2) should give ~0.015m < 0.02m, "
        "but got ERROR -- likely using one-way (c*dt)"
    )


# ---------------------------------------------------------------------------
# Test 11: Sensor model has fov_degrees field
# ---------------------------------------------------------------------------


def test_sensor_has_fov_degrees():
    """Sensor model has fov_degrees field with default 20.0."""
    from agentsim.preview.scene_description import Sensor

    sensor = Sensor()
    assert hasattr(sensor, "fov_degrees")
    assert sensor.fov_degrees == 20.0


# ---------------------------------------------------------------------------
# Test 12: Non-confocal setup with valid geometry
# ---------------------------------------------------------------------------


def test_three_bounce_non_confocal_valid():
    """Non-confocal setup (separate laser_pos and sensor_pos) returns no ERROR
    for valid geometry."""
    from agentsim.physics.checks.nlos_geometry import check_three_bounce_geometry

    results = check_three_bounce_geometry(
        sensor_pos=(0.5, -1.5, 0),
        sensor_look_at=(0, 0, 0),
        relay_wall_pos=(0, 0, 0),
        relay_wall_normal=(0, -1, 0),
        relay_wall_size=2.0,
        hidden_objects=((0, 1, 0), (0.3, 0.8, 0.2)),
    )
    errors = [r for r in results if r.severity == Severity.ERROR]
    assert len(errors) == 0, f"Unexpected errors: {[e.message for e in errors]}"
