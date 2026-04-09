"""Frozen Pydantic models for sensor family parameter ranges.

ParameterRange captures min/max/typical bounds for a single physical parameter.
SensorFamilyRanges groups ranges under a sensor family for feasibility filtering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentsim.knowledge_graph.models import SensorFamily


class ParameterRange(BaseModel, frozen=True):
    """Min/max/typical bounds for a single sensor parameter.

    Used by the feasibility query engine to prune sensor configurations
    that fall outside physically realizable ranges.
    """

    min: float | None = None
    max: float | None = None
    typical: float | None = None
    unit: str = ""
    description: str = ""


class SensorFamilyRanges(BaseModel, frozen=True):
    """Aggregate parameter ranges for an entire sensor family.

    Loaded from the family-level `ranges` section of each sensor YAML file.
    """

    family: SensorFamily
    display_name: str = ""
    description: str = ""
    ranges: dict[str, ParameterRange] = Field(default_factory=dict)
