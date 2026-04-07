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
