"""Physics-space reasoning engine -- deterministic constraint propagation.

Re-exports the public API for the reasoning package.
"""

from __future__ import annotations

from agentsim.physics.reasoning.propagation import propagate_constraints

__all__ = ["propagate_constraints"]
