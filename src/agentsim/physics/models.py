"""Frozen Pydantic models for the physics validation layer.

All models are immutable (frozen=True), matching the codebase convention.
A single Pint UnitRegistry instance is shared across the entire physics module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pint
from pydantic import BaseModel, Field

# Single Pint UnitRegistry for the entire physics module (avoids multi-registry pitfall).
_ureg = pint.UnitRegistry()


def _now() -> datetime:
    """UTC timestamp factory for default field values."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Severity level for physics check results."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Core check result models
# ---------------------------------------------------------------------------


class CheckResult(BaseModel, frozen=True):
    """Single result from a deterministic physics check."""

    check: str
    severity: Severity
    message: str
    parameter: str = ""
    details: str = ""


class ValidationReport(BaseModel, frozen=True):
    """Aggregated results from one or more physics checks."""

    results: tuple[CheckResult, ...] = ()
    passed: bool = True
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Physical constants and parameters
# ---------------------------------------------------------------------------


class PhysicalConstant(BaseModel, frozen=True):
    """A curated physical constant with SI unit string.

    Magnitude and unit are stored as separate fields so the model
    stays JSON-serializable without Pint dependency at the boundary.
    """

    name: str
    symbol: str
    magnitude: float
    unit: str
    description: str = ""
    domain: str = "universal"


class PhysicalParameter(BaseModel, frozen=True):
    """A named physical parameter with magnitude and unit.

    Provides conversion helpers to/from pint.Quantity for calculations.
    """

    name: str
    magnitude: float
    unit: str
    description: str = ""

    def to_quantity(self) -> pint.Quantity:
        """Convert to a Pint Quantity for dimensional analysis."""
        return _ureg.Quantity(self.magnitude, self.unit)

    @classmethod
    def from_quantity(
        cls,
        name: str,
        q: pint.Quantity,
        description: str = "",
    ) -> PhysicalParameter:
        """Create from a Pint Quantity, extracting magnitude and unit string."""
        return cls(
            name=name,
            magnitude=float(q.magnitude),
            unit=str(q.units),
            description=description,
        )


# ---------------------------------------------------------------------------
# AST extraction models
# ---------------------------------------------------------------------------


class ExtractedParameter(BaseModel, frozen=True):
    """A parameter extracted from simulation source code via AST analysis."""

    name: str
    value: float
    line: int
    unit_hint: str = ""


class ExtractedSimulationParams(BaseModel, frozen=True):
    """Parameters extracted from generated simulation code."""

    parameters: tuple[ExtractedParameter, ...] = ()
    solver_type: str = "unknown"
    velocity: float | None = None
    timestep: float | None = None
    mesh_spacing: float | None = None
    mesh_paths: tuple[str, ...] = ()
    function_calls: tuple[str, ...] = ()


class ASTExtractionResult(BaseModel, frozen=True):
    """Result of AST-based code analysis, including any issues found."""

    params: ExtractedSimulationParams
    issues: tuple[CheckResult, ...] = ()


# ---------------------------------------------------------------------------
# Physics advisor consultation models
# ---------------------------------------------------------------------------


class PhysicsQuery(BaseModel, frozen=True):
    """A query sent to the physics advisor agent."""

    query_type: str
    context: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class PhysicsGuidance(BaseModel, frozen=True):
    """Response from the physics advisor agent."""

    domain_detected: str = ""
    confidence: float = 0.0
    recommendations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    governing_equations: tuple[str, ...] = ()
    dimensionless_groups: tuple[str, ...] = ()


class ConsultationLogEntry(BaseModel, frozen=True):
    """A logged physics consultation (query + response) for reproducibility."""

    query: PhysicsQuery
    response: PhysicsGuidance
    domain: str = ""
    confidence: float = 0.0
    timestamp: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# State-level physics models (embedded in ExperimentState)
# ---------------------------------------------------------------------------


class PhysicsValidation(BaseModel, frozen=True):
    """Physics validation result for a single scene."""

    scene_id: str
    report: ValidationReport
    timestamp: datetime = Field(default_factory=_now)


class PhysicsConsultationSummary(BaseModel, frozen=True):
    """Aggregate summary of all physics consultations in an experiment."""

    total_consultations: int = 0
    domains_consulted: tuple[str, ...] = ()
    total_errors: int = 0
    total_warnings: int = 0
