"""Pydantic models for YAML-based domain knowledge files.

These frozen models define the schema for domain-specific physics knowledge:
governing equations, geometry constraints, sensor parameters, reconstruction
algorithms, published parameter sets, and dimensionless groups.

All models are immutable (frozen=True), matching the codebase convention.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParameterRange(BaseModel, frozen=True):
    """A numeric range with optional typical value and description."""

    min: float
    max: float
    typical: float | None = None
    description: str = ""


class GoverningEquation(BaseModel, frozen=True):
    """A governing equation with LaTeX representation and variable definitions."""

    name: str
    latex: str = ""
    description: str = ""
    variables: dict[str, str] = Field(default_factory=dict)


class GeometryConstraintRule(BaseModel, frozen=True):
    """A single geometry constraint rule with description and requirements."""

    description: str = ""
    requirements: tuple[str, ...] = ()


class GeometryConstraint(BaseModel, frozen=True):
    """Geometry constraints for a domain (e.g., three-bounce path, relay wall)."""

    three_bounce_path: GeometryConstraintRule | None = None
    relay_wall: dict[str, float | str] = Field(default_factory=dict)
    sensor_to_wall_distance: dict[str, float] = Field(default_factory=dict)
    wall_to_hidden_distance: dict[str, float] = Field(default_factory=dict)


class SpadParameters(BaseModel, frozen=True):
    """SPAD sensor parameter ranges."""

    temporal_resolution_ps: ParameterRange | None = None
    jitter_ps: ParameterRange | None = None
    dead_time_ns: ParameterRange | None = None
    fov_degrees: ParameterRange | None = None
    scan_points: ParameterRange | None = None


class SensorParameters(BaseModel, frozen=True):
    """Sensor parameters container (currently SPAD only, extensible)."""

    spad: SpadParameters | None = None


class ReconstructionAlgorithm(BaseModel, frozen=True):
    """A reconstruction algorithm with reference and parameter constraints."""

    name: str
    reference: str = ""
    requires_confocal: bool = False
    spatial_resolution: str = ""
    frequency_constraint: str = ""
    parameters: dict[str, ParameterRange | dict] = Field(default_factory=dict)


class PublishedParameterSet(BaseModel, frozen=True):
    """Parameters from a published codebase or paper."""

    paper: str
    venue: str = ""
    wall_size_m: float | None = None
    scan_resolution: str = ""
    temporal_bins: int | None = None
    temporal_resolution_ps: float | None = None
    object_distance_m: float | None = None
    scanning: str = ""
    nonplanar_wall_size_m: float | None = None
    nonplanar_resolution: str = ""
    frame_rate_fps: float | None = None
    virtual_wavelength_range_m: list[float] | None = None


class DimensionlessGroup(BaseModel, frozen=True):
    """A dimensionless group used for physics scaling analysis."""

    name: str
    formula: str = ""
    description: str = ""


class DomainKnowledge(BaseModel, frozen=True):
    """Top-level domain knowledge model loaded from YAML.

    Each YAML file in the domains directory defines one physics domain
    with its governing equations, geometry constraints, sensor parameters,
    reconstruction algorithms, published parameter index, and dimensionless groups.
    """

    domain: str
    version: str = "1.0"
    description: str = ""
    governing_equations: tuple[GoverningEquation, ...] = ()
    geometry_constraints: GeometryConstraint | None = None
    sensor_parameters: SensorParameters | None = None
    reconstruction_algorithms: dict[str, ReconstructionAlgorithm] = Field(
        default_factory=dict,
    )
    published_parameter_index: dict[str, PublishedParameterSet] = Field(
        default_factory=dict,
    )
    dimensionless_groups: tuple[DimensionlessGroup, ...] = ()
    transfer_functions: tuple["TransferFunction", ...] = ()


# ---------------------------------------------------------------------------
# Paradigm-agnostic models (Phase 02.1)
# ---------------------------------------------------------------------------


class TransferFunction(BaseModel, frozen=True):
    """A computable physics relationship between parameters.

    Stores structured mappings from input parameters to output quantities
    with functional relationships. Data-only in Phase 02.1; Phase 02.2
    adds evaluation logic.

    Args:
        input: Source parameter name (e.g. "temporal_resolution_ps").
        output: Derived quantity name (e.g. "spatial_resolution_m").
        relationship: Functional form — one of "linear", "inverse", "sqrt",
            "quadratic", "logarithmic", "proportional", "inverse_sqrt".
        formula: Human-readable formula string (not evaluated).
        description: Explanation of the physics coupling.
        coupling_strength: Qualitative strength — "strong", "moderate", "weak".
    """

    input: str
    output: str
    relationship: str
    formula: str = ""
    description: str = ""
    coupling_strength: str = ""


class ValidationRule(BaseModel, frozen=True):
    """A validation rule declaration — either declarative or Python reference.

    For ``python_check``: references a module + function that performs
    complex geometry validation (e.g. three-bounce path tracing).

    For ``range_check`` / ``threshold_check``: declarative YAML-only rule
    evaluated by the generic dispatcher without custom Python.

    Args:
        name: Unique rule identifier within a paradigm.
        type: One of "python_check", "range_check", "threshold_check".
        description: Human-readable explanation.
        module: Python dotted path for python_check rules.
        function: Function name within module for python_check rules.
        parameter: Parameter name for range_check / threshold_check.
        min: Lower bound for range_check (inclusive).
        max: Upper bound for range_check (inclusive).
        severity: "error" or "warning".
        message: Custom message on rule violation.
    """

    name: str
    type: str
    description: str = ""
    # python_check fields
    module: str = ""
    function: str = ""
    # range_check / threshold_check fields
    parameter: str = ""
    min: float | None = None
    max: float | None = None
    severity: str = "error"
    message: str = ""


class ParadigmKnowledge(BaseModel, frozen=True):
    """Paradigm-level knowledge loaded from a paradigm YAML file.

    A paradigm is a specific experimental approach within a domain.
    For example, within the ``nlos_transient_imaging`` domain, ``relay_wall``
    and ``penumbra`` are distinct paradigms with different geometry
    constraints, validation rules, and compatible sensor types.

    Args:
        paradigm: Paradigm identifier (e.g. "relay_wall", "penumbra").
        domain: Parent domain identifier.
        version: Schema version string.
        description: Human-readable paradigm description.
        keywords: Keyword phrases for paradigm auto-detection.
        compatible_sensor_types: Sensor type tags (e.g. "spad", "streak_camera").
        geometry_constraints: Paradigm-specific geometry parameters as nested dicts.
        validation_rules: Ordered tuple of validation rule declarations.
        transfer_functions: Physics coupling relationships.
        published_baselines: Published experiment baselines keyed by identifier.
    """

    paradigm: str
    domain: str
    version: str = "1.0"
    description: str = ""
    keywords: tuple[str, ...] = ()
    compatible_sensor_types: tuple[str, ...] = ()  # deprecated: use compatible_sensor_classes
    compatible_sensor_classes: tuple[str, ...] = ()
    compatible_algorithms: tuple[str, ...] = ()
    geometry_constraints: dict[str, dict[str, float | str]] = Field(
        default_factory=dict,
    )
    validation_rules: tuple[ValidationRule, ...] = ()
    transfer_functions: tuple[TransferFunction, ...] = ()
    published_baselines: dict[str, dict] = Field(default_factory=dict)


class TimingParameters(BaseModel, frozen=True):
    """Temporal characteristics of a sensor.

    Args:
        temporal_resolution_ps: Time-bin width range in picoseconds.
        jitter_fwhm_ps: Timing jitter FWHM range in picoseconds.
        dead_time_ns: Dead-time range in nanoseconds.
        gate_width_ns: Gate width range in nanoseconds (time-gated sensors).
    """

    temporal_resolution_ps: ParameterRange | None = None
    jitter_fwhm_ps: ParameterRange | None = None
    dead_time_ns: ParameterRange | None = None
    gate_width_ns: ParameterRange | None = None


class SpatialParameters(BaseModel, frozen=True):
    """Spatial characteristics of a sensor array.

    Args:
        array_size: Pixel array dimensions (rows, columns).
        pixel_pitch_um: Pixel pitch in micrometres.
        fill_factor: Active area fraction (0–1).
        fov_degrees: Field-of-view range in degrees.
    """

    array_size: tuple[int, int]
    pixel_pitch_um: float
    fill_factor: float = 1.0
    fov_degrees: ParameterRange | None = None


class NoiseModel(BaseModel, frozen=True):
    """Noise characteristics of a sensor.

    Args:
        dark_count_rate_hz: Dark count rate in Hz.
        afterpulsing_probability: Afterpulsing probability (0–1).
        crosstalk_probability: Optical crosstalk probability (0–1).
        quantum_efficiency: Photon detection efficiency (0–1).
    """

    dark_count_rate_hz: float = 0.0
    afterpulsing_probability: float = 0.0
    crosstalk_probability: float = 0.0
    quantum_efficiency: float = 0.0


class OperationalMode(BaseModel, frozen=True):
    """An operational mode for a sensor (e.g. time-gated, free-running).

    Args:
        name: Mode identifier.
        timing_constraints: Mode-specific timing limits.
        description: Human-readable explanation.
    """

    name: str
    timing_constraints: dict[str, float] = Field(default_factory=dict)
    description: str = ""


class SensorProfile(BaseModel, frozen=True):
    """A named sensor hardware profile with full characterisation.

    Sensor profiles are paradigm-independent — a SwissSPAD2 can be used
    in relay-wall NLOS or penumbra imaging.

    Args:
        name: Display name (e.g. "SwissSPAD2").
        sensor_type: Type tag matching paradigm compatible_sensor_types.
        manufacturer: Hardware manufacturer.
        reference: Primary reference publication.
        timing: Temporal parameters.
        spatial: Spatial / array parameters.
        noise: Noise model (optional).
        operational_modes: Available operating modes.
        transfer_functions: Sensor-level physics couplings.
    """

    name: str
    sensor_type: str
    manufacturer: str = ""
    reference: str = ""
    timing: TimingParameters
    spatial: SpatialParameters
    noise: NoiseModel | None = None
    operational_modes: tuple[OperationalMode, ...] = ()
    transfer_functions: tuple[TransferFunction, ...] = ()


class SensorCatalog(BaseModel, frozen=True):
    """A collection of named sensor profiles.

    Loaded from sensors.yaml. Keys are lowercase identifiers
    (e.g. "swissspad2", "linospad2", "streak_camera").
    """

    sensors: dict[str, SensorProfile] = Field(default_factory=dict)


class ReconstructionAlgorithmV2(BaseModel, frozen=True):
    """Extended reconstruction algorithm with structured physics knowledge.

    Extends the original ReconstructionAlgorithm with input requirements,
    output characteristics, and transfer functions per D-15.
    The original model is kept unchanged for backward compatibility.

    Args:
        name: Algorithm display name.
        reference: Primary publication reference.
        requires_confocal: Whether confocal scanning is required.
        spatial_resolution: Resolution description.
        frequency_constraint: Frequency-domain constraint description.
        parameters: Legacy parameter ranges (backward compat).
        input_requirements: Structured input requirements as dicts.
        output_characteristics: Qualitative output descriptions.
        transfer_functions: Parameter-to-quality physics couplings.
    """

    name: str
    reference: str = ""
    requires_confocal: bool = False
    spatial_resolution: str = ""
    frequency_constraint: str = ""
    parameters: dict[str, ParameterRange | dict] = Field(default_factory=dict)
    input_requirements: tuple[dict[str, bool | int | str], ...] = ()
    output_characteristics: tuple[str, ...] = ()
    transfer_functions: tuple[TransferFunction, ...] = ()


# ---------------------------------------------------------------------------
# Directory-per-domain models (domain restructure)
# ---------------------------------------------------------------------------


class SensorClass(BaseModel, frozen=True):
    """Class-level sensor description — physics capabilities and tradeoffs.

    Represents a category of sensors (e.g. "research-grade SPAD arrays")
    rather than a specific model. Agents reason at this level by default
    and only drill into SensorProfile when exact specs are needed.
    """

    name: str
    display_name: str = ""
    description: str = ""
    sensor_type: str = ""
    timing_range: TimingParameters | None = None
    spatial_range: SpatialParameters | None = None
    noise_range: NoiseModel | None = None
    transfer_functions: tuple[TransferFunction, ...] = ()
    tradeoffs: str = ""
    typical_models: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()


class AlgorithmKnowledge(BaseModel, frozen=True):
    """Reconstruction algorithm as a first-class domain resource.

    Extracted from domain YAML into its own file with explicit
    paradigm and sensor compatibility declarations.
    """

    name: str
    algorithm: str = ""
    reference: str = ""
    description: str = ""
    requires_confocal: bool = False
    spatial_resolution: str = ""
    frequency_constraint: str = ""
    compatible_paradigms: tuple[str, ...] = ()
    compatible_sensor_classes: tuple[str, ...] = ()
    parameters: dict[str, ParameterRange | dict] = Field(default_factory=dict)
    input_requirements: tuple[dict[str, bool | int | str], ...] = ()
    output_characteristics: tuple[str, ...] = ()
    transfer_functions: tuple[TransferFunction, ...] = ()


class DomainBundle(BaseModel, frozen=True):
    """Complete loaded domain — all resources resolved and accessible.

    The bundle is the primary unit returned by load_domain_bundle().
    It contains the domain knowledge plus all paradigms, sensor classes,
    sensor profiles, and algorithms within the domain directory.
    """

    domain: DomainKnowledge
    paradigms: dict[str, ParadigmKnowledge] = Field(default_factory=dict)
    sensor_classes: dict[str, SensorClass] = Field(default_factory=dict)
    sensor_profiles: dict[str, SensorProfile] = Field(default_factory=dict)
    algorithms: dict[str, AlgorithmKnowledge] = Field(default_factory=dict)
