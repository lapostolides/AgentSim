"""Frozen Pydantic models for Bayesian optimization of sensor configurations.

Defines the data structures used throughout the optimizer subpackage:
CostWeights for operational cost normalization, ParetoPoint for non-dominated
solutions, BOMetadata for per-family optimization tracking, and
OptimizationResult as the top-level envelope (D-12).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily


class CostWeights(BaseModel, frozen=True):
    """Weights for normalized operational cost dimensions (D-04).

    Defaults sum to 1.0: usd=0.5, power=0.3, weight=0.2.
    """

    usd: float = 0.5
    power: float = 0.3
    weight: float = 0.2


class ParetoPoint(BaseModel, frozen=True):
    """A single point on the Pareto front of CRB vs operational cost.

    Represents a non-dominated sensor configuration with its objective
    values, constraint margin, and confidence qualifier.
    """

    sensor_name: str
    family: SensorFamily
    parameter_values: dict[str, float]
    crb_bound: float
    crb_unit: str
    operational_cost: float
    constraint_margin: float
    confidence: ConfidenceQualifier


class BOMetadata(BaseModel, frozen=True):
    """Tracking metadata for a single-family Bayesian optimization run."""

    evaluations: int
    converged: bool
    final_acquisition_improvement: float
    computation_time_s: float


class FamilyOptimizationResult(BaseModel, frozen=True):
    """Optimization result for one sensor family."""

    family: SensorFamily
    pareto_front: tuple[ParetoPoint, ...] = ()
    bo_metadata: BOMetadata | None = None


class OptimizationResult(BaseModel, frozen=True):
    """Top-level result aggregating all family optimization runs."""

    family_results: tuple[FamilyOptimizationResult, ...] = ()
    scope: str = "medium"
    cost_weights: CostWeights = Field(default_factory=CostWeights)
    total_evaluations: int = 0
    total_computation_time_s: float = 0.0
