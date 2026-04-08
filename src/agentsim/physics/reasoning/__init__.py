"""Physics-space reasoning engine -- deterministic constraint propagation.

Re-exports the public API for the reasoning package:
- propagate_constraints: BFS constraint propagation through TF graphs
- optimize_setup: Rank sensor+algorithm combinations by propagation scores
- find_novel_regions: Identify parameters outside published baselines
"""

from __future__ import annotations

from agentsim.physics.reasoning.explorer import find_novel_regions
from agentsim.physics.reasoning.optimizer import optimize_setup
from agentsim.physics.reasoning.propagation import propagate_constraints

__all__ = ["find_novel_regions", "optimize_setup", "propagate_constraints"]
