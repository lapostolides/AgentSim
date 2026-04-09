"""CRB (Cramer-Rao Bound) computation subpackage.

Re-exports public symbols from models and analytical modules.
"""

from __future__ import annotations

from agentsim.knowledge_graph.crb.analytical import (
    ANALYTICAL_FAMILIES,
    compute_analytical_crb,
)
from agentsim.knowledge_graph.crb.models import CRBBound, CRBResult, SensitivityEntry

__all__ = [
    "ANALYTICAL_FAMILIES",
    "CRBBound",
    "CRBResult",
    "SensitivityEntry",
    "compute_analytical_crb",
]
