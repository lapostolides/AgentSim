"""CRB and information-theoretic bounds for computational imaging sensors.

Public API:
- compute_crb(): Unified dispatch (analytical or numerical)
- compute_analytical_crb(): Direct analytical CRB
- compute_numerical_crb(): Direct numerical CRB (requires JAX)
- compute_sensitivity(): Parameter importance ranking (Morris method)
- CRBResult, CRBBound, SensitivityEntry, SensitivityResult: Frozen result models
- ANALYTICAL_FAMILIES, NUMERICAL_FAMILIES, SUPPORTED_FAMILIES: Family sets
- jax_available(): Check JAX availability
- Stability guards: check_condition_number, regularize_fisher, assert_positive_variance
"""

from __future__ import annotations

from agentsim.knowledge_graph.crb.analytical import (
    ANALYTICAL_FAMILIES,
    compute_analytical_crb,
)
from agentsim.knowledge_graph.crb.dispatch import (
    SUPPORTED_FAMILIES,
    compute_crb,
)
from agentsim.knowledge_graph.crb.models import (
    CRBBound,
    CRBResult,
    SensitivityEntry,
)
from agentsim.knowledge_graph.crb.numerical import (
    NUMERICAL_FAMILIES,
    compute_numerical_crb,
    jax_available,
)
from agentsim.knowledge_graph.crb.sensitivity import (
    SensitivityResult,
    compute_sensitivity,
)
from agentsim.knowledge_graph.crb.stability import (
    CONDITION_THRESHOLD,
    assert_positive_variance,
    check_condition_number,
    regularize_fisher,
)

__all__ = [
    "ANALYTICAL_FAMILIES",
    "CONDITION_THRESHOLD",
    "CRBBound",
    "CRBResult",
    "NUMERICAL_FAMILIES",
    "SUPPORTED_FAMILIES",
    "SensitivityEntry",
    "SensitivityResult",
    "assert_positive_variance",
    "check_condition_number",
    "compute_analytical_crb",
    "compute_crb",
    "compute_numerical_crb",
    "compute_sensitivity",
    "jax_available",
    "regularize_fisher",
]
