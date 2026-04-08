"""Frozen Pydantic models for the computational imaging knowledge graph.

All models are immutable (frozen=True). SensorNode uses validated composition
with embedded property groups and a FAMILY_SCHEMAS registry for per-family
validation (D-01, D-02).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from agentsim.knowledge_graph.units import validate_unit


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SensorFamily(str, Enum):
    """Exhaustive taxonomy of computational imaging sensor families."""

    SPAD = "spad"
    CW_TOF = "cw_tof"
    PULSED_DTOF = "pulsed_dtof"
    EVENT_CAMERA = "event_camera"
    CODED_APERTURE = "coded_aperture"
    LIGHT_FIELD = "light_field"
    LIDAR_MECHANICAL = "lidar_mechanical"
    LIDAR_SOLID_STATE = "lidar_solid_state"
    LIDAR_FMCW = "lidar_fmcw"
    LENSLESS = "lensless"
    RGB = "rgb"
    STRUCTURED_LIGHT = "structured_light"
    POLARIMETRIC = "polarimetric"
    SPECTRAL = "spectral"


class ConfidenceQualifier(str, Enum):
    """How a CRB bound was derived."""

    ANALYTICAL = "analytical"
    NUMERICAL = "numerical"
    EMPIRICAL = "empirical"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Property group models (shared physics dimensions)
# ---------------------------------------------------------------------------


class GeometricProps(BaseModel, frozen=True):
    """Geometric/spatial properties shared across sensor families (PHYS-01, D-03)."""

    fov: float
    fov_unit: str = "degree"
    spatial_resolution: float | None = None
    spatial_resolution_unit: str = "pixel"
    depth_of_field: float | None = None
    depth_of_field_unit: str = "meter"
    working_distance_min: float | None = None
    working_distance_max: float | None = None
    working_distance_unit: str = "meter"
    aperture_geometry: str = ""

    @model_validator(mode="after")
    def _validate_units(self) -> GeometricProps:
        validate_unit(self.fov_unit, "angle")
        validate_unit(self.working_distance_unit, "length")
        validate_unit(self.depth_of_field_unit, "length")
        return self


class TemporalProps(BaseModel, frozen=True):
    """Temporal properties shared across sensor families (PHYS-02)."""

    exposure_time: float | None = None
    exposure_time_unit: str = "second"
    temporal_resolution: float | None = None
    temporal_resolution_unit: str = "picosecond"
    readout_mode: str = ""
    frame_rate: float | None = None
    frame_rate_unit: str = "hertz"

    @model_validator(mode="after")
    def _validate_units(self) -> TemporalProps:
        validate_unit(self.exposure_time_unit, "time")
        validate_unit(self.temporal_resolution_unit, "time")
        validate_unit(self.frame_rate_unit, "frequency")
        return self


class RadiometricProps(BaseModel, frozen=True):
    """Radiometric properties shared across sensor families (PHYS-03)."""

    quantum_efficiency: float | None = None
    quantum_efficiency_unit: str = "dimensionless"
    dynamic_range_db: float | None = None
    noise_floor: float | None = None
    noise_floor_unit: str = "dimensionless"
    spectral_sensitivity_peak_nm: float | None = None
    dark_current: float | None = None
    dark_current_unit: str = "hertz"

    @model_validator(mode="after")
    def _validate_units(self) -> RadiometricProps:
        validate_unit(self.quantum_efficiency_unit, "ratio")
        validate_unit(self.dark_current_unit, "frequency")
        return self


class OperationalProps(BaseModel, frozen=True):
    """Operational metadata for sensors (PHYS-05)."""

    cost_min_usd: float | None = None
    cost_max_usd: float | None = None
    power_w: float | None = None
    weight_g: float | None = None
    form_factor: str = ""
    operating_environment: str = ""


# ---------------------------------------------------------------------------
# FAMILY_SCHEMAS registry (must precede SensorNode for runtime lookup)
# ---------------------------------------------------------------------------


FAMILY_SCHEMAS: dict[SensorFamily, dict[str, type | tuple[type, ...]]] = {
    SensorFamily.SPAD: {
        "dead_time_ns": float,
        "afterpulsing_probability": float,
        "crosstalk_probability": float,
        "fill_factor": float,
        "pde": float,
    },
    SensorFamily.CW_TOF: {
        "modulation_frequency_mhz": float,
        "demodulation_contrast": float,
        "phase_tap_count": (int, float),
    },
    SensorFamily.PULSED_DTOF: {
        "pulse_width_ns": float,
        "laser_rep_rate_khz": float,
        "channel_count": (int, float),
    },
    SensorFamily.EVENT_CAMERA: {
        "contrast_threshold": float,
        "refractory_period_us": float,
        "bandwidth_khz": float,
    },
    SensorFamily.CODED_APERTURE: {
        "mask_pattern_type": str,
        "mask_transmittance": float,
        "psf_condition_number": float,
    },
    SensorFamily.LIGHT_FIELD: {
        "microlens_pitch_um": float,
        "angular_samples": (int, float),
        "baseline_mm": float,
    },
    SensorFamily.LIDAR_MECHANICAL: {
        "scan_rate_rpm": float,
        "angular_resolution_deg": float,
        "max_range_m": float,
    },
    SensorFamily.LIDAR_SOLID_STATE: {
        "flash_fov_deg": float,
        "point_density": float,
    },
    SensorFamily.LIDAR_FMCW: {
        "chirp_bandwidth_ghz": float,
        "chirp_duration_us": float,
        "coherence_length_m": float,
    },
    SensorFamily.LENSLESS: {
        "mask_type": str,
        "mask_sensor_distance_mm": float,
        "psf_condition_number": float,
    },
    SensorFamily.RGB: {
        "pixel_pitch_um": float,
        "well_depth_electrons": float,
        "read_noise_electrons": float,
    },
    SensorFamily.STRUCTURED_LIGHT: {
        "pattern_type": str,
        "projector_resolution": str,
        "baseline_mm": float,
    },
    SensorFamily.POLARIMETRIC: {
        "extinction_ratio": float,
        "polarizer_angles_deg": str,
        "dolp_accuracy": float,
    },
    SensorFamily.SPECTRAL: {
        "spectral_range_nm_min": float,
        "spectral_range_nm_max": float,
        "spectral_resolution_nm": float,
        "band_count": (int, float),
    },
}


# ---------------------------------------------------------------------------
# SensorNode (validated composition)
# ---------------------------------------------------------------------------


class SensorNode(BaseModel, frozen=True):
    """A specific sensor instance with physics properties and family-specific specs.

    Uses FAMILY_SCHEMAS to validate that family_specs contains all required
    keys with correct types for the given sensor family (D-01, D-02).
    """

    name: str
    family: SensorFamily
    description: str = ""
    geometric: GeometricProps
    temporal: TemporalProps
    radiometric: RadiometricProps
    operational: OperationalProps | None = None
    family_specs: dict[str, float | str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_family_specs(self) -> SensorNode:
        schema = FAMILY_SCHEMAS.get(self.family)
        if schema is None:
            return self
        for key, expected_type in schema.items():
            if key not in self.family_specs:
                raise ValueError(
                    f"Missing required family_specs key '{key}' "
                    f"for {self.family.value} sensor"
                )
            value = self.family_specs[key]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"family_specs['{key}'] must be {expected_type}, "
                    f"got {type(value).__name__}"
                )
        return self


# ---------------------------------------------------------------------------
# Graph node models
# ---------------------------------------------------------------------------


class AlgorithmNode(BaseModel, frozen=True):
    """A reconstruction or processing algorithm in the knowledge graph."""

    name: str
    paradigm: str = ""
    description: str = ""
    reference: str = ""


class TaskNode(BaseModel, frozen=True):
    """A downstream estimation/reconstruction task."""

    name: str
    description: str = ""
    estimation_target: str = ""
    constraints: tuple[str, ...] = ()


class EnvironmentNode(BaseModel, frozen=True):
    """An operating environment with constraints on sensor selection."""

    name: str
    description: str = ""
    ambient_light: str = ""
    range_m: float | None = None
    constraints: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Edge models
# ---------------------------------------------------------------------------


class SharesPhysicsEdge(BaseModel, frozen=True):
    """Edge connecting two SensorFamily values that share a physical principle."""

    source_family: SensorFamily
    target_family: SensorFamily
    shared_principle: str
    coupling_note: str = ""


class BelongsToEdge(BaseModel, frozen=True):
    """Edge: a named sensor belongs to a sensor family."""

    sensor_name: str
    family: SensorFamily


class CompatibleWithEdge(BaseModel, frozen=True):
    """Edge: a sensor is compatible with a reconstruction algorithm."""

    sensor_name: str
    algorithm_name: str
    paradigm: str = ""
    quality_level: str = ""


class AchievesBoundEdge(BaseModel, frozen=True):
    """Edge: a sensor achieves a CRB bound on a task."""

    sensor_name: str
    task_name: str
    bound_value: float
    bound_unit: str
    confidence: ConfidenceQualifier = ConfidenceQualifier.UNKNOWN


# ---------------------------------------------------------------------------
# Feasibility query result models
# ---------------------------------------------------------------------------


class ConstraintSatisfaction(BaseModel, frozen=True):
    """Whether a single constraint is satisfied by a sensor configuration."""

    constraint_name: str
    satisfied: bool
    margin: float = 0.0
    unit: str = ""
    details: str = ""


class SensorConfig(BaseModel, frozen=True):
    """A ranked sensor+algorithm configuration in a feasibility result."""

    sensor_name: str
    sensor_family: SensorFamily
    algorithm_name: str
    crb_bound: float | None = None
    crb_unit: str = ""
    confidence: ConfidenceQualifier = ConfidenceQualifier.UNKNOWN
    rank: int = 0
    feasibility_score: float = 0.0
    constraint_satisfaction: tuple[ConstraintSatisfaction, ...] = ()
    notes: str = ""


class FeasibilityResult(BaseModel, frozen=True):
    """Result of a natural language feasibility query (QUERY-04).

    Contains ranked sensor configurations that satisfy task and environment
    constraints, with CRB bounds and confidence qualifiers.
    """

    query_text: str
    detected_task: str = ""
    detected_domain: str = ""
    environment_constraints: tuple[str, ...] = ()
    ranked_configs: tuple[SensorConfig, ...] = ()
    pruned_count: int = 0
    total_count: int = 0
    computation_time_s: float = 0.0
