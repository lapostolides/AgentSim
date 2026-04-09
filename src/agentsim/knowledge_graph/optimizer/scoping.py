"""Experiment scope filtering and auto-detection for Pareto fronts.

Controls how many Pareto-optimal configurations agents see:
- wide: all Pareto-optimal configs across all families
- medium: top-5 configs per family (default)
- narrow: single best config per family

Auto-detection infers scope from hypothesis text (D-06, D-07).
"""

from __future__ import annotations

import structlog

from agentsim.knowledge_graph.optimizer.models import (
    FamilyOptimizationResult,
    OptimizationResult,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCOPES: frozenset[str] = frozenset({"wide", "medium", "narrow"})

_MEDIUM_LIMIT: int = 5

_COMPARISON_PATTERNS: tuple[str, ...] = (
    "compare sensor",
    "which sensor",
    "evaluate sensor",
    "sensor comparison",
    "cross-family",
    "best sensor for",
)

_SPECIFIC_SENSOR_NAMES: tuple[str, ...] = (
    "swissspad",
    "swisspad",
    "prophesee",
    "evk4",
    "basler",
    "flir",
    "hamamatsu",
    "velodyne",
    "ouster",
    "intel realsense",
    "kinect",
    "pmd",
)


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------


def _filter_family(
    family_result: FamilyOptimizationResult,
    scope: str,
) -> FamilyOptimizationResult:
    """Apply scope filtering to a single family's Pareto front.

    Returns a new FamilyOptimizationResult with filtered pareto_front.
    The bo_metadata is preserved unchanged.
    """
    front = family_result.pareto_front

    if scope == "wide":
        filtered = front
    else:
        sorted_front = tuple(sorted(front, key=lambda p: p.crb_bound))
        if scope == "medium":
            filtered = sorted_front[:_MEDIUM_LIMIT]
        else:  # narrow
            filtered = sorted_front[:1]

    return family_result.model_copy(update={"pareto_front": filtered})


def filter_by_scope(result: OptimizationResult, scope: str) -> OptimizationResult:
    """Filter optimization results by scope level.

    Args:
        result: Complete optimization result across families.
        scope: One of "wide", "medium", or "narrow".

    Returns:
        New OptimizationResult with filtered Pareto fronts and updated scope.

    Raises:
        ValueError: If scope is not in VALID_SCOPES.
    """
    if scope not in VALID_SCOPES:
        msg = f"unknown scope '{scope}', must be one of {sorted(VALID_SCOPES)}"
        raise ValueError(msg)

    filtered_families = tuple(
        _filter_family(fr, scope) for fr in result.family_results
    )

    return result.model_copy(
        update={
            "family_results": filtered_families,
            "scope": scope,
        }
    )


# ---------------------------------------------------------------------------
# Scope auto-detection
# ---------------------------------------------------------------------------


def detect_scope(hypothesis: str) -> str:
    """Infer experiment scope from hypothesis text.

    Args:
        hypothesis: Free-text hypothesis string.

    Returns:
        Scope string: "narrow" for specific sensor mentions,
        "wide" for comparison language, "medium" as default.
    """
    lower = hypothesis.lower()

    # Check for specific sensor names first (most specific wins)
    for name in _SPECIFIC_SENSOR_NAMES:
        if name in lower:
            logger.info("scope_auto_detected", scope="narrow", reason=f"sensor name '{name}'")
            return "narrow"

    # Check for comparison / exploration language
    for pattern in _COMPARISON_PATTERNS:
        if pattern in lower:
            logger.info("scope_auto_detected", scope="wide", reason=f"pattern '{pattern}'")
            return "wide"

    # Default to medium
    logger.info("scope_auto_detected", scope="medium", reason="no specific signals")
    return "medium"
