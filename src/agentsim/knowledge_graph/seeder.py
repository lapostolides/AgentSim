"""YAML-to-Neo4j seed pipeline with MERGE-based idempotent seeding.

Reads all sensor YAML files via the Phase 7 loader and creates corresponding
Neo4j nodes (SensorFamily, Sensor, Algorithm) and edges (BELONGS_TO,
SHARES_PHYSICS) using MERGE for safe re-runs. Calls ensure_schema() before
any MERGE operations to prevent the "MERGE without uniqueness constraints"
anti-pattern (Research Pitfall 1).
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from agentsim.knowledge_graph.client import GraphClient
from agentsim.knowledge_graph.loader import load_family_ranges, load_sensors
from agentsim.knowledge_graph.models import (
    AlgorithmNode,
    BelongsToEdge,
    SensorFamily,
    SharesPhysicsEdge,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# SeedResult model
# ---------------------------------------------------------------------------


class SeedResult(BaseModel, frozen=True):
    """Frozen summary of a graph seed operation."""

    sensors_created: int
    families_created: int
    edges_created: int
    errors: tuple[str, ...]


# ---------------------------------------------------------------------------
# SHARED_PHYSICS_EDGES -- Cross-family physics connections (D-09)
#
# These edges encode which sensor families share underlying physical
# measurement principles. Each edge documents the shared_principle and
# a coupling_note explaining the downstream effect.
#
# Deep domain research notes:
#
# 1. SPAD <-> CW_TOF (photon_timing): Both measure photon arrival or
#    phase-of-arrival to infer depth. SPAD timestamps individual photon
#    arrivals (TCSPC histograms); CW-ToF modulates illumination and
#    measures phase shift of the reflected signal. The shared principle
#    is that depth is encoded in the temporal relationship between
#    emitted and received photons. Downstream: SPAD yields raw photon
#    timestamps (ps resolution) while CW-ToF yields phase (mm resolution),
#    so reconstruction algorithms differ (histogram fitting vs phase
#    unwrapping).
#
# 2. SPAD <-> PULSED_DTOF (photon_counting): Both rely on single-photon
#    detection via avalanche multiplication. SPAD arrays count individual
#    photons with picosecond timing; pulsed dToF fires a laser pulse and
#    times the return using SPAD-like detectors. The shared principle is
#    single-photon sensitivity and time-correlated counting. Downstream:
#    SPAD arrays provide 2D+time images, pulsed dToF provides per-beam
#    range measurements, so spatial vs point-cloud tradeoffs differ.
#
# 3. CW_TOF <-> LIDAR_FMCW (phase_measurement): Both extract range from
#    the phase of a modulated or chirped signal. CW-ToF uses sinusoidal
#    amplitude modulation; FMCW LiDAR uses frequency-swept chirps and
#    measures beat frequency. Shared principle: range is linearly related
#    to measured phase or frequency offset. Downstream: CW-ToF is
#    limited by modulation frequency ambiguity (multi-freq needed for
#    long range); FMCW simultaneously yields range AND velocity from
#    beat frequency, enabling Doppler sensing.
#
# 4. LIDAR_MECHANICAL <-> LIDAR_SOLID_STATE (time_of_flight): Both
#    measure round-trip time of a laser pulse to determine range.
#    Mechanical LiDAR uses spinning optics for 360-degree coverage;
#    solid-state uses flash illumination or MEMS mirrors for a fixed
#    FoV. Shared principle: direct time-of-flight measurement (c*t/2).
#    Downstream: mechanical provides sparse 360-degree point clouds
#    (automotive mapping); solid-state provides dense depth in a fixed
#    cone (ADAS, robotics), so different coverage/density tradeoffs.
#
# 5. CODED_APERTURE <-> LENSLESS (computational_reconstruction): Both
#    replace traditional optics with coded elements and recover images
#    via solving an inverse problem. Coded apertures use known mask
#    patterns (MURA, random) placed before the sensor; lensless cameras
#    use diffusers or gratings that spread incoming light. Shared
#    principle: the measurement is a coded projection of the scene,
#    requiring deconvolution or iterative reconstruction. Downstream:
#    coded aperture excels at extended depth-of-field and 3D; lensless
#    excels at ultra-thin form factor and wide FoV, but both share
#    ill-conditioning sensitivity (PSF condition number matters).
#
# 6. LIGHT_FIELD <-> STRUCTURED_LIGHT (multi_view_geometry): Both
#    exploit multi-view or multi-pattern observations to recover 3D
#    geometry. Light-field cameras capture multiple angular views via
#    microlens arrays; structured light projects known patterns and
#    triangulates from pattern deformation. Shared principle: 3D
#    recovery from multiple geometric observations (disparity or
#    pattern correspondence). Downstream: light-field enables
#    post-capture refocusing and depth from disparity; structured
#    light provides dense metric depth but requires active projection,
#    so ambient light sensitivity differs fundamentally.
#
# 7. POLARIMETRIC <-> RGB (intensity_imaging): Both capture intensity
#    images through a Bayer-like filter mosaic on a conventional
#    image sensor. Polarimetric cameras use a micro-polarizer array
#    (0/45/90/135 degrees) in front of pixels; RGB cameras use a
#    color filter array (R/G/B). Shared principle: spatial multiplexing
#    of different filter responses on a 2D sensor with demosaicking.
#    Downstream: RGB yields color channels (scene appearance);
#    polarimetric yields Stokes parameters (surface normal, material
#    properties), so the information content is fundamentally different
#    despite the same sensor architecture.
#
# 8. SPECTRAL <-> RGB (spectral_sampling): RGB imaging is a 3-band
#    spectral sampling with broad overlapping filters; spectral/
#    hyperspectral imaging extends this to tens or hundreds of narrow
#    bands. Shared principle: the scene radiance spectrum is sampled
#    at discrete wavelength bands via optical filtering. Downstream:
#    RGB provides perceptual color (metameric ambiguity); spectral
#    provides material-specific reflectance signatures (chemical ID),
#    but mathematical treatment (linear mixing, unmixing) is shared.
#
# 9. SPAD <-> LIDAR_MECHANICAL (single_photon_ranging): Both can
#    operate in single-photon detection mode for long-range sensing.
#    SPAD arrays in Geiger mode detect individual photons with timing
#    circuits; mechanical LiDAR increasingly uses SPAD-based receivers
#    for improved sensitivity. Shared principle: single-photon-level
#    detection with precise timing for range measurement. Downstream:
#    SPAD arrays provide flood-illuminated 2D depth; mechanical LiDAR
#    provides scanned point clouds, so field of regard differs.
#
# 10. EVENT_CAMERA <-> RGB (pixel_level_sensing): Both use arrays of
#     independent photodetectors on a silicon substrate. RGB reads all
#     pixels synchronously (frame-based); event cameras fire
#     asynchronously when individual pixel intensity changes exceed a
#     threshold. Shared principle: pixel-level photoelectric conversion
#     on a CMOS sensor. Downstream: RGB yields full-frame snapshots
#     with motion blur; event cameras yield sparse asynchronous events
#     with microsecond latency and no motion blur, requiring completely
#     different reconstruction (event integration vs frame processing).
#
# 11. PULSED_DTOF <-> LIDAR_MECHANICAL (pulsed_ranging): Both emit
#     short laser pulses and time the return echo. Pulsed dToF
#     (direct time-of-flight) is the measurement principle; mechanical
#     LiDAR is a scanning implementation of pulsed dToF. Shared
#     principle: pulsed laser emission with time-gated detection.
#     Downstream: pulsed dToF can be flash (full-frame) or scanned;
#     mechanical LiDAR is always scanned, so angular coverage and
#     point density tradeoffs differ.
#
# 12. LIDAR_FMCW <-> LIDAR_SOLID_STATE (coherent_detection): Both
#     can employ coherent detection for improved noise rejection.
#     FMCW inherently uses heterodyne detection; some solid-state
#     LiDAR designs use coherent receivers. Shared principle:
#     coherent mixing of reference and signal beams for shot-noise-
#     limited detection. Downstream: FMCW yields simultaneous range
#     and velocity; solid-state coherent designs focus on range
#     only but benefit from ambient light rejection.
# ---------------------------------------------------------------------------


SHARED_PHYSICS_EDGES: tuple[SharesPhysicsEdge, ...] = (
    # 1. SPAD <-> CW_TOF: depth from photon timing
    SharesPhysicsEdge(
        source_family=SensorFamily.SPAD,
        target_family=SensorFamily.CW_TOF,
        shared_principle="photon_timing",
        coupling_note=(
            "Both infer depth from the temporal relationship between emitted and "
            "received photons. SPAD uses TCSPC histograms (ps resolution); CW-ToF "
            "uses phase shift of modulated illumination (mm resolution). Reconstruction "
            "differs: histogram fitting vs phase unwrapping."
        ),
    ),
    # 2. SPAD <-> PULSED_DTOF: single-photon detection
    SharesPhysicsEdge(
        source_family=SensorFamily.SPAD,
        target_family=SensorFamily.PULSED_DTOF,
        shared_principle="photon_counting",
        coupling_note=(
            "Both rely on avalanche-based single-photon detection with time-correlated "
            "counting. SPAD arrays provide 2D+time flood-illuminated images; pulsed dToF "
            "provides per-beam range. Spatial vs point-cloud tradeoffs differ."
        ),
    ),
    # 3. CW_TOF <-> LIDAR_FMCW: range from phase/frequency
    SharesPhysicsEdge(
        source_family=SensorFamily.CW_TOF,
        target_family=SensorFamily.LIDAR_FMCW,
        shared_principle="phase_measurement",
        coupling_note=(
            "Both extract range from phase or frequency offset of a modulated signal. "
            "CW-ToF: sinusoidal modulation with phase ambiguity. FMCW: chirped sweep "
            "yielding beat frequency for simultaneous range and velocity (Doppler)."
        ),
    ),
    # 4. LIDAR_MECHANICAL <-> LIDAR_SOLID_STATE: direct ToF
    SharesPhysicsEdge(
        source_family=SensorFamily.LIDAR_MECHANICAL,
        target_family=SensorFamily.LIDAR_SOLID_STATE,
        shared_principle="time_of_flight",
        coupling_note=(
            "Both measure round-trip time of a laser pulse (c*t/2). Mechanical uses "
            "spinning optics for 360-degree sparse point clouds; solid-state uses flash "
            "or MEMS for dense depth in a fixed FoV. Coverage vs density tradeoffs."
        ),
    ),
    # 5. CODED_APERTURE <-> LENSLESS: inverse problem reconstruction
    SharesPhysicsEdge(
        source_family=SensorFamily.CODED_APERTURE,
        target_family=SensorFamily.LENSLESS,
        shared_principle="computational_reconstruction",
        coupling_note=(
            "Both replace traditional optics with coded elements (masks, diffusers) "
            "and recover images via solving an inverse problem. PSF condition number "
            "governs reconstruction quality. Coded aperture excels at extended DoF/3D; "
            "lensless excels at ultra-thin form factor."
        ),
    ),
    # 6. LIGHT_FIELD <-> STRUCTURED_LIGHT: multi-view 3D
    SharesPhysicsEdge(
        source_family=SensorFamily.LIGHT_FIELD,
        target_family=SensorFamily.STRUCTURED_LIGHT,
        shared_principle="multi_view_geometry",
        coupling_note=(
            "Both recover 3D from multiple geometric observations. Light-field captures "
            "angular views via microlens arrays (post-capture refocus + disparity depth). "
            "Structured light triangulates from projected pattern deformation (dense metric "
            "depth). Active vs passive illumination changes ambient sensitivity."
        ),
    ),
    # 7. POLARIMETRIC <-> RGB: filter-array spatial multiplexing
    SharesPhysicsEdge(
        source_family=SensorFamily.POLARIMETRIC,
        target_family=SensorFamily.RGB,
        shared_principle="intensity_imaging",
        coupling_note=(
            "Both use spatial multiplexing of filter responses on a 2D CMOS sensor with "
            "demosaicking. Polarimetric uses micro-polarizer arrays yielding Stokes "
            "parameters (surface normals, material). RGB uses color filters yielding "
            "perceptual color. Same sensor architecture, different information content."
        ),
    ),
    # 8. SPECTRAL <-> RGB: wavelength-band sampling
    SharesPhysicsEdge(
        source_family=SensorFamily.SPECTRAL,
        target_family=SensorFamily.RGB,
        shared_principle="spectral_sampling",
        coupling_note=(
            "RGB is 3-band spectral sampling with broad overlapping filters; spectral/ "
            "hyperspectral extends to tens-hundreds of narrow bands. Both sample scene "
            "radiance at discrete wavelength bands. RGB has metameric ambiguity; spectral "
            "provides material-specific reflectance for chemical ID."
        ),
    ),
    # 9. SPAD <-> LIDAR_MECHANICAL: single-photon ranging
    SharesPhysicsEdge(
        source_family=SensorFamily.SPAD,
        target_family=SensorFamily.LIDAR_MECHANICAL,
        shared_principle="single_photon_ranging",
        coupling_note=(
            "Both can operate in single-photon detection mode. SPAD arrays in Geiger mode "
            "detect individual photons; mechanical LiDAR increasingly uses SPAD receivers "
            "for improved sensitivity. SPAD = flood-illuminated 2D depth; mechanical = "
            "scanned point clouds with different FoR."
        ),
    ),
    # 10. EVENT_CAMERA <-> RGB: pixel-level photoelectric conversion
    SharesPhysicsEdge(
        source_family=SensorFamily.EVENT_CAMERA,
        target_family=SensorFamily.RGB,
        shared_principle="pixel_level_sensing",
        coupling_note=(
            "Both use CMOS pixel arrays for photoelectric conversion. RGB reads all pixels "
            "synchronously (frame-based, motion blur). Event cameras fire asynchronously "
            "per-pixel when intensity change exceeds threshold (no motion blur, us latency). "
            "Requires completely different reconstruction approaches."
        ),
    ),
    # 11. PULSED_DTOF <-> LIDAR_MECHANICAL: pulsed laser ranging
    SharesPhysicsEdge(
        source_family=SensorFamily.PULSED_DTOF,
        target_family=SensorFamily.LIDAR_MECHANICAL,
        shared_principle="pulsed_ranging",
        coupling_note=(
            "Both emit short laser pulses and time the return echo. Pulsed dToF is the "
            "measurement principle; mechanical LiDAR is a scanning implementation. Pulsed "
            "dToF can be flash (full-frame) or scanned; mechanical is always scanned."
        ),
    ),
    # 12. LIDAR_FMCW <-> LIDAR_SOLID_STATE: coherent detection
    SharesPhysicsEdge(
        source_family=SensorFamily.LIDAR_FMCW,
        target_family=SensorFamily.LIDAR_SOLID_STATE,
        shared_principle="coherent_detection",
        coupling_note=(
            "Both can employ coherent (heterodyne) detection for shot-noise-limited "
            "measurement and ambient light rejection. FMCW inherently uses heterodyne; "
            "solid-state coherent designs benefit from background noise immunity. FMCW "
            "yields simultaneous range + velocity; solid-state focuses on range."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Seed pipeline
# ---------------------------------------------------------------------------


def seed_graph(
    client: GraphClient,
    force_clean: bool = False,
) -> SeedResult:
    """Seed the Neo4j knowledge graph from YAML sensor files.

    Reads all 14 sensor YAML files via the Phase 7 loader, creates
    SensorFamily nodes, Sensor nodes, BELONGS_TO edges, SHARES_PHYSICS
    edges, and a generic Algorithm placeholder.

    Uses MERGE throughout -- running this function multiple times is safe
    and produces no duplicates.

    Args:
        client: An open GraphClient connected to Neo4j.
        force_clean: If True, wipe the entire graph before seeding.

    Returns:
        Frozen SeedResult with counts of created entities.
    """
    errors: list[str] = []
    sensors_created = 0
    families_created = 0
    edges_created = 0

    # Optionally wipe the database
    if force_clean:
        client.clear_all()
        logger.info("seed_force_clean", action="cleared all nodes and edges")

    # CRITICAL: ensure_schema BEFORE any MERGE (Research Pitfall 1)
    client.ensure_schema()

    # Load sensor data from YAML files
    sensors = load_sensors()
    family_ranges = load_family_ranges()

    # Extract unique families from loaded sensors
    unique_families: set[SensorFamily] = {s.family for s in sensors}

    # Also include families from family_ranges that might not have sensors loaded
    for fam in family_ranges:
        unique_families.add(fam)

    # Create SensorFamily nodes
    for family in sorted(unique_families, key=lambda f: f.value):
        ranges = family_ranges.get(family)
        display_name = ranges.display_name if ranges else ""
        description = ranges.description if ranges else ""

        # Build flat props from family ranges
        props: dict[str, object] = {
            "description": description,
        }
        if ranges and ranges.ranges:
            for param_name, param_range in ranges.ranges.items():
                dumped = param_range.model_dump()
                for k, v in dumped.items():
                    if v is not None:
                        props[f"range_{param_name}_{k}"] = v

        client.create_sensor_family(
            name=family.value,
            display_name=display_name,
            props=props,
        )
        families_created += 1

    # Create Sensor nodes (individual errors don't abort)
    for sensor in sensors:
        try:
            client.create_sensor(sensor)
            sensors_created += 1
        except Exception as exc:
            msg = f"Failed to create sensor '{sensor.name}': {exc}"
            logger.warning("seed_sensor_error", sensor=sensor.name, error=str(exc))
            errors.append(msg)

    # Create BELONGS_TO edges
    for sensor in sensors:
        try:
            edge = BelongsToEdge(sensor_name=sensor.name, family=sensor.family)
            client.create_relationship(edge)
            edges_created += 1
        except Exception as exc:
            msg = f"Failed to create BELONGS_TO edge for '{sensor.name}': {exc}"
            logger.warning("seed_belongs_to_error", sensor=sensor.name, error=str(exc))
            errors.append(msg)

    # Create SHARES_PHYSICS edges
    for physics_edge in SHARED_PHYSICS_EDGES:
        try:
            client.create_relationship(physics_edge)
            edges_created += 1
        except Exception as exc:
            msg = (
                f"Failed to create SHARES_PHYSICS edge "
                f"{physics_edge.source_family.value}->{physics_edge.target_family.value}: {exc}"
            )
            logger.warning(
                "seed_shares_physics_error",
                source=physics_edge.source_family.value,
                target=physics_edge.target_family.value,
                error=str(exc),
            )
            errors.append(msg)

    # Create generic Algorithm placeholder (Phase 10 populates real algorithms)
    placeholder_algo = AlgorithmNode(
        name="generic",
        description="Generic placeholder -- Phase 10 populates real algorithms",
    )
    try:
        client.create_algorithm(placeholder_algo)
    except Exception as exc:
        msg = f"Failed to create generic algorithm placeholder: {exc}"
        logger.warning("seed_algorithm_error", error=str(exc))
        errors.append(msg)

    result = SeedResult(
        sensors_created=sensors_created,
        families_created=families_created,
        edges_created=edges_created,
        errors=tuple(errors),
    )

    logger.info(
        "seed_complete",
        sensors_created=result.sensors_created,
        families_created=result.families_created,
        edges_created=result.edges_created,
        error_count=len(result.errors),
    )

    return result
