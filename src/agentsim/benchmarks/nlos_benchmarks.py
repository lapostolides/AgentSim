"""NLOS benchmark scenes with known transient profiles.

Three canonical configurations for verifying NLOS simulation solvers:
confocal point reflector, non-confocal two objects, retroreflective corner.

Each benchmark contains geometry, acquisition parameters, and expected
output characteristics (peak timing, peak count) for validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

SPEED_OF_LIGHT: float = 299_792_458.0


class NLOSBenchmarkScene(BaseModel, frozen=True):
    """A benchmark NLOS scene with known expected output."""

    name: str
    description: str = ""
    # Geometry
    relay_wall_pos: tuple[float, float, float] = (0.0, 0.0, 0.0)
    relay_wall_normal: tuple[float, float, float] = (0.0, -1.0, 0.0)
    relay_wall_size: float = 2.0
    sensor_pos: tuple[float, float, float] = (0.0, -1.5, 0.0)
    sensor_look_at: tuple[float, float, float] = (0.0, 0.0, 0.0)
    sensor_fov_deg: float = 20.0
    hidden_objects: tuple[tuple[float, float, float], ...] = ()
    occluder_pos: tuple[float, float, float] | None = None
    occluder_size: tuple[float, float, float] | None = None
    # Acquisition
    scanning_mode: str = "confocal"
    scan_resolution: str = "64x64"
    temporal_bins: int = 2048
    temporal_resolution_ps: float = 32.0
    # Expected output
    expected_peak_ns: float | None = None
    expected_peak_count: int = 1
    description_of_expected: str = ""


CONFOCAL_POINT_REFLECTOR = NLOSBenchmarkScene(
    name="confocal_point_reflector",
    description=(
        "Single sphere behind relay wall, confocal scanning. "
        "Expected: single transient peak."
    ),
    relay_wall_pos=(0.0, 0.0, 0.0),
    relay_wall_normal=(0.0, -1.0, 0.0),
    relay_wall_size=2.0,
    sensor_pos=(0.0, -1.5, 0.0),
    sensor_look_at=(0.0, 0.0, 0.0),
    sensor_fov_deg=20.0,
    hidden_objects=((0.0, 1.0, 0.0),),
    scanning_mode="confocal",
    scan_resolution="64x64",
    temporal_bins=2048,
    temporal_resolution_ps=32.0,
    expected_peak_ns=round(2 * (1.5 + 1.0) / SPEED_OF_LIGHT * 1e9, 1),
    expected_peak_count=1,
    description_of_expected=(
        "Single peak at t = 2*(d_sensor_to_wall + d_wall_to_object)/c"
    ),
)

NON_CONFOCAL_TWO_OBJECTS = NLOSBenchmarkScene(
    name="non_confocal_two_objects",
    description=(
        "Two spheres at different depths, non-confocal. "
        "Expected: two separable transient peaks."
    ),
    relay_wall_pos=(0.0, 0.0, 0.0),
    relay_wall_normal=(0.0, -1.0, 0.0),
    relay_wall_size=2.0,
    sensor_pos=(0.0, -1.5, 0.0),
    sensor_look_at=(0.0, 0.0, 0.0),
    sensor_fov_deg=20.0,
    hidden_objects=((0.0, 0.5, 0.0), (0.0, 1.5, 0.0)),
    scanning_mode="non-confocal",
    scan_resolution="64x64",
    temporal_bins=2048,
    temporal_resolution_ps=32.0,
    expected_peak_count=2,
    description_of_expected=(
        "Two peaks separated by round-trip path difference of "
        "2*(1.5-0.5)/c ~ 6.7ns"
    ),
)

RETROREFLECTIVE_CORNER = NLOSBenchmarkScene(
    name="retroreflective_corner",
    description=(
        "Corner reflector (two perpendicular planes). "
        "Expected: enhanced retroreflective return."
    ),
    relay_wall_pos=(0.0, 0.0, 0.0),
    relay_wall_normal=(0.0, -1.0, 0.0),
    relay_wall_size=2.0,
    sensor_pos=(0.0, -1.5, 0.0),
    sensor_look_at=(0.0, 0.0, 0.0),
    sensor_fov_deg=20.0,
    hidden_objects=((0.5, 1.0, 0.0), (0.5, 1.0, 0.5)),
    scanning_mode="confocal",
    scan_resolution="64x64",
    temporal_bins=2048,
    temporal_resolution_ps=32.0,
    expected_peak_count=1,
    description_of_expected=(
        "Strong retroreflective signal from corner geometry, "
        "enhanced return intensity"
    ),
)

_BENCHMARKS: dict[str, NLOSBenchmarkScene] = {
    "confocal_point_reflector": CONFOCAL_POINT_REFLECTOR,
    "non_confocal_two_objects": NON_CONFOCAL_TWO_OBJECTS,
    "retroreflective_corner": RETROREFLECTIVE_CORNER,
}


def list_benchmarks() -> tuple[str, ...]:
    """Return names of all available NLOS benchmark scenes."""
    return tuple(_BENCHMARKS.keys())


def get_benchmark_scene(name: str) -> NLOSBenchmarkScene | None:
    """Look up a benchmark scene by name.

    Args:
        name: Benchmark scene identifier.

    Returns:
        NLOSBenchmarkScene if found, None otherwise.
    """
    return _BENCHMARKS.get(name)
