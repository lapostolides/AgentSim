"""Tests for NLOS benchmark scenes and reconstruction sanity checks."""

from __future__ import annotations

import math

import pytest

from agentsim.benchmarks.nlos_benchmarks import (
    CONFOCAL_POINT_REFLECTOR,
    NON_CONFOCAL_TWO_OBJECTS,
    RETROREFLECTIVE_CORNER,
    SPEED_OF_LIGHT,
    get_benchmark_scene,
    list_benchmarks,
)
from agentsim.physics.checker import run_nlos_checks
from agentsim.physics.checks.nlos_geometry import check_reconstruction_sanity
from agentsim.physics.models import Severity


class TestBenchmarkSceneDefinitions:
    """Tests for benchmark scene correctness."""

    def test_confocal_geometry(self) -> None:
        """Test 1: CONFOCAL_POINT_REFLECTOR has expected geometry."""
        scene = CONFOCAL_POINT_REFLECTOR
        assert scene.relay_wall_size == 2.0
        assert scene.sensor_pos == (0.0, -1.5, 0.0)
        assert scene.hidden_objects == ((0.0, 1.0, 0.0),)

    def test_confocal_expected_peak(self) -> None:
        """Test 2: CONFOCAL_POINT_REFLECTOR peak is ~16.7 ns."""
        scene = CONFOCAL_POINT_REFLECTOR
        expected = round(2 * (1.5 + 1.0) / SPEED_OF_LIGHT * 1e9, 1)
        assert scene.expected_peak_ns is not None
        assert math.isclose(scene.expected_peak_ns, expected, rel_tol=0.01)
        assert math.isclose(scene.expected_peak_ns, 16.7, abs_tol=0.1)

    def test_non_confocal_two_objects(self) -> None:
        """Test 3: NON_CONFOCAL_TWO_OBJECTS has two hidden objects at different depths."""
        scene = NON_CONFOCAL_TWO_OBJECTS
        assert len(scene.hidden_objects) == 2
        # Different y-coordinates (depth)
        assert scene.hidden_objects[0][1] != scene.hidden_objects[1][1]

    def test_retroreflective_corner(self) -> None:
        """Test 4: RETROREFLECTIVE_CORNER has corner geometry."""
        scene = RETROREFLECTIVE_CORNER
        assert len(scene.hidden_objects) == 2
        # Objects at different z (forming a corner)
        assert scene.hidden_objects[0][2] != scene.hidden_objects[1][2]


class TestBenchmarkRegistry:
    """Tests for benchmark listing and lookup."""

    def test_list_benchmarks_returns_three(self) -> None:
        """Test 5: list_benchmarks() returns 3 names."""
        names = list_benchmarks()
        assert len(names) == 3

    def test_get_benchmark_scene_confocal(self) -> None:
        """Test 6: get_benchmark_scene returns confocal benchmark."""
        scene = get_benchmark_scene("confocal_point_reflector")
        assert scene is not None
        assert scene.name == "confocal_point_reflector"

    def test_get_benchmark_scene_nonexistent(self) -> None:
        """Test 7: get_benchmark_scene returns None for nonexistent."""
        assert get_benchmark_scene("nonexistent") is None


class TestBenchmarkGeometryValidity:
    """Tests that all benchmarks pass NLOS geometry checks."""

    @pytest.mark.parametrize("name", list(list_benchmarks()))
    def test_benchmark_passes_nlos_checks(self, name: str) -> None:
        """Test 8: All benchmarks pass run_nlos_checks."""
        scene = get_benchmark_scene(name)
        assert scene is not None
        report = run_nlos_checks(
            sensor_pos=scene.sensor_pos,
            sensor_look_at=scene.sensor_look_at,
            relay_wall_pos=scene.relay_wall_pos,
            relay_wall_normal=scene.relay_wall_normal,
            relay_wall_size=scene.relay_wall_size,
            hidden_objects=scene.hidden_objects,
            sensor_fov_deg=scene.sensor_fov_deg,
            occluder_pos=scene.occluder_pos,
            occluder_size=scene.occluder_size,
        )
        assert report.passed, (
            f"Benchmark {name} failed NLOS checks: "
            + "; ".join(
                r.message for r in report.results if r.severity == Severity.ERROR
            )
        )


class TestReconstructionSanityCheck:
    """Tests for check_reconstruction_sanity."""

    def test_object_inside_visibility_cone(self) -> None:
        """Test 9: Object inside visibility cone returns no ERROR."""
        results = check_reconstruction_sanity(
            reconstructed_object_pos=(0.0, 0.8, 0.0),  # Behind wall
            relay_wall_pos=(0.0, 0.0, 0.0),
            relay_wall_normal=(0.0, -1.0, 0.0),
            relay_wall_size=2.0,
            sensor_pos=(0.0, -1.5, 0.0),
        )
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_object_outside_visibility_cone(self) -> None:
        """Test 10: Object outside visibility cone returns ERROR."""
        results = check_reconstruction_sanity(
            reconstructed_object_pos=(5.0, 0.8, 0.0),  # Far lateral
            relay_wall_pos=(0.0, 0.0, 0.0),
            relay_wall_normal=(0.0, -1.0, 0.0),
            relay_wall_size=2.0,
            sensor_pos=(0.0, -1.5, 0.0),
        )
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("visibility cone" in e.message for e in errors)

    def test_timing_violation(self) -> None:
        """Test 11: Object too far for temporal bins returns ERROR."""
        results = check_reconstruction_sanity(
            reconstructed_object_pos=(0.0, 100.0, 0.0),  # Very far
            relay_wall_pos=(0.0, 0.0, 0.0),
            relay_wall_normal=(0.0, -1.0, 0.0),
            relay_wall_size=2.0,
            sensor_pos=(0.0, -1.5, 0.0),
            temporal_bins=64,
            temporal_resolution_ps=32.0,
        )
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("depth" in e.message.lower() for e in errors)
