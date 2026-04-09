"""Frozen Pydantic models for CRB computation results.

Provides CRBResult (complete CRB computation output), CRBBound (single
parameter bound), and SensitivityEntry (parameter sensitivity ranking).
All models are immutable (frozen=True) per project convention (CRB-04, D-10).
"""

from __future__ import annotations

from pydantic import BaseModel

from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily


class CRBBound(BaseModel, frozen=True):
    """A single CRB bound on one estimated parameter."""

    parameter_name: str
    bound_value: float  # sqrt(variance lower bound) -- standard deviation
    bound_unit: str


class CRBResult(BaseModel, frozen=True):
    """Complete CRB computation result (CRB-04, D-10).

    The ``bound_value`` field stores the square root of the variance lower
    bound (i.e. a standard-deviation floor), not the variance itself.
    """

    sensor_family: SensorFamily
    estimation_task: str  # e.g., "depth", "range", "dolp", "abundance"
    bounds: tuple[CRBBound, ...] = ()
    bound_value: float  # primary bound (sqrt of variance)
    bound_unit: str  # "meter" or "dimensionless"
    bound_type: str  # "analytical" or "numerical"
    confidence: ConfidenceQualifier
    condition_number: float | None = None  # None for analytical
    model_assumptions: tuple[str, ...] = ()
    sensor_name: str = ""


class SensitivityEntry(BaseModel, frozen=True):
    """One entry in a parameter sensitivity ranking (CRB-05, D-08, D-09).

    Morris method fields:
    - ``mu_star``: mean absolute elementary effect (importance measure)
    - ``sigma``: standard deviation of elementary effects (interaction indicator)
    - ``classification``: negligible / linear / nonlinear based on sigma/mu_star

    Legacy fields (``sensitivity``, ``perturbed_crb``) retained for backward
    compatibility but are optional.
    """

    parameter_name: str
    nominal_value: float
    mu_star: float = 0.0  # mean |EE| across trajectories (importance)
    sigma: float = 0.0  # std(EE) across trajectories (interaction indicator)
    classification: str = ""  # negligible, linear, nonlinear
    perturbed_crb: float = 0.0
    sensitivity: float = 0.0  # kept for backward compat
    rank: int = 0
