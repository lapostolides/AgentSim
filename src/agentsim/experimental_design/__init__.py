"""Experimental design package: DoE strategy selection and parameter sampling.

Provides automated selection of Design of Experiments strategies (LHS, Sobol,
full factorial, Bayesian) based on parameter space dimensionality and budget,
plus space-filling samplers that generate design matrices for scene variants.
"""

from __future__ import annotations

from agentsim.experimental_design.models import (
    DoEStrategy,
    DoEStrategyType,
    ParameterBound,
    ParameterSpace,
    SampledDesign,
)

__all__ = [
    "DoEStrategy",
    "DoEStrategyType",
    "ParameterBound",
    "ParameterSpace",
    "SampledDesign",
]
