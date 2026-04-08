"""Explorer mode -- find novel parameter regions outside published baselines.

Compares hypothesis parameters against published baselines from paradigm
knowledge and identifies novel parameter combinations. No LLM calls.
"""

from __future__ import annotations

from agentsim.physics.domains.schema import ParadigmKnowledge
from agentsim.physics.reasoning.models import ExplorerResult


def find_novel_regions(
    hypothesis_params: dict[str, float],
    paradigm: ParadigmKnowledge,
) -> ExplorerResult:
    """Find parameter regions not covered by published baselines.

    Args:
        hypothesis_params: Parameter name-value pairs from the hypothesis.
        paradigm: Paradigm with published_baselines to compare against.

    Returns:
        ExplorerResult with novel parameters and proposed experiments.
    """
    raise NotImplementedError("find_novel_regions not yet implemented")
