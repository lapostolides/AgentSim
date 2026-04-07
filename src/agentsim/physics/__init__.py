"""Physics validation infrastructure for AgentSim.

Standalone module for deterministic physics checks -- no LLM dependency.
Import: from agentsim.physics import run_deterministic_checks
"""

from __future__ import annotations

from agentsim.physics.checker import run_deterministic_checks

__all__ = ["run_deterministic_checks"]
