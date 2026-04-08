"""Frozen Pydantic models for Design of Experiments (DoE).

Defines the parameter space, strategy selection result, and sampled design
matrix. All models are immutable (frozen=True) following project conventions.
"""

from __future__ import annotations

from enum import Enum

import structlog
from pydantic import BaseModel, Field

from agentsim.state.models import ParameterSpec

logger = structlog.get_logger()


class ParameterBound(BaseModel, frozen=True):
    """A single parameter with numeric bounds for experimental design.

    Args:
        name: Parameter identifier.
        low: Lower bound of the parameter range.
        high: Upper bound of the parameter range.
        description: Human-readable description.
        log_scale: If True, sampling is done in log space.
    """

    name: str
    low: float
    high: float
    description: str = ""
    log_scale: bool = False


class ParameterSpace(BaseModel, frozen=True):
    """Collection of parameter bounds defining the experimental search space.

    Args:
        parameters: Tuple of ParameterBound instances (tuple for immutability).
    """

    parameters: tuple[ParameterBound, ...] = ()

    @property
    def dimensionality(self) -> int:
        """Number of parameters in the space."""
        return len(self.parameters)

    @property
    def names(self) -> tuple[str, ...]:
        """Tuple of parameter names."""
        return tuple(p.name for p in self.parameters)

    @property
    def bounds(self) -> list[dict]:
        """SALib-compatible problem bounds format.

        Returns:
            List of dicts with 'name' and 'bounds' keys for each parameter.
        """
        return [
            {"name": p.name, "bounds": [p.low, p.high]}
            for p in self.parameters
        ]

    @classmethod
    def from_hypothesis_params(cls, specs: list[ParameterSpec]) -> ParameterSpace:
        """Convert hypothesis ParameterSpec list to a ParameterSpace.

        Skips specs where range_min or range_max is None (non-numeric parameters).

        Args:
            specs: List of ParameterSpec from the hypothesis.

        Returns:
            New ParameterSpace with bounds derived from specs that have ranges.
        """
        param_bounds: list[ParameterBound] = []
        for spec in specs:
            if spec.range_min is None or spec.range_max is None:
                logger.debug(
                    "skipping_parameter_no_range",
                    name=spec.name,
                )
                continue
            param_bounds.append(
                ParameterBound(
                    name=spec.name,
                    low=spec.range_min,
                    high=spec.range_max,
                    description=spec.description,
                )
            )
        return cls(parameters=tuple(param_bounds))


class DoEStrategyType(str, Enum):
    """Supported Design of Experiments strategy types."""

    LHS = "lhs"
    SOBOL = "sobol"
    FULL_FACTORIAL = "full_factorial"
    BAYESIAN = "bayesian"


class DoEStrategy(BaseModel, frozen=True):
    """Result of DoE strategy selection.

    Args:
        strategy_type: The selected strategy type.
        n_samples: Number of samples to generate.
        rationale: Human-readable explanation of why this strategy was chosen.
    """

    strategy_type: DoEStrategyType
    n_samples: int
    rationale: str = ""


class SampledDesign(BaseModel, frozen=True):
    """A generated experimental design matrix.

    The design_matrix is stored as nested tuples for immutability.
    Shape is (n_runs, n_params).

    Args:
        strategy: The DoE strategy used to generate this design.
        parameter_names: Tuple of parameter names matching matrix columns.
        design_matrix: Nested tuples of float values, shape (n_runs, n_params).
    """

    strategy: DoEStrategy
    parameter_names: tuple[str, ...]
    design_matrix: tuple[tuple[float, ...], ...]

    @property
    def n_runs(self) -> int:
        """Number of experimental runs (rows in design matrix)."""
        return len(self.design_matrix)

    def to_parameter_dicts(self) -> list[dict[str, float]]:
        """Convert design matrix to a list of parameter dictionaries.

        Each dict maps parameter names to their values for one run,
        suitable for passing to scene generation.

        Returns:
            List of dicts with parameter name keys and float values.
        """
        return [
            dict(zip(self.parameter_names, row))
            for row in self.design_matrix
        ]
