"""Optimizer mode -- rank sensor+algorithm combinations by propagation-derived scores.

Enumerates the cartesian product of compatible sensors and algorithms,
propagates constraints through merged transfer function chains, and
scores each combination. No LLM calls -- purely deterministic.
"""

from __future__ import annotations

from agentsim.physics.domains.schema import DomainBundle, ParadigmKnowledge
from agentsim.physics.reasoning.models import OptimizerResult, PropagationResult


def optimize_setup(
    hypothesis_params: dict[str, float],
    bundle: DomainBundle,
    paradigm: ParadigmKnowledge,
) -> OptimizerResult:
    """Rank sensor+algorithm combinations for a given hypothesis.

    Args:
        hypothesis_params: Parameter name-value pairs from the hypothesis.
        bundle: Complete domain bundle with sensors and algorithms.
        paradigm: Paradigm under which to optimize.

    Returns:
        OptimizerResult with scored setups sorted descending by score.
    """
    raise NotImplementedError("optimize_setup not yet implemented")


def _compute_setup_score(
    result: PropagationResult,
    hypothesis_params: dict[str, float],
) -> float:
    """Score a propagation result for hypothesis relevance.

    Args:
        result: Propagation output for a sensor+algorithm combo.
        hypothesis_params: Original hypothesis parameters.

    Returns:
        Numeric score (higher is better).
    """
    raise NotImplementedError("_compute_setup_score not yet implemented")
