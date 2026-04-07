"""SymPy dimensional equation tracing for physics validation.

Checks dimensional consistency of expressions using SymPy's SI
dimensional analysis system. Purely deterministic, no LLM calls.
"""

from __future__ import annotations

from sympy.physics.units.dimensions import Dimension
from sympy.physics.units.systems.si import dimsys_SI

from agentsim.physics.models import (
    ASTExtractionResult,
    CheckResult,
    Severity,
)


def check_expression_dimensions(lhs_dim: Dimension, rhs_dim: Dimension) -> bool:
    """Check if two SymPy dimensions are compatible.

    Args:
        lhs_dim: Left-hand side dimension.
        rhs_dim: Right-hand side dimension.

    Returns:
        True if dimensional dependencies match, False otherwise.
    """
    lhs_deps = dimsys_SI.get_dimensional_dependencies(lhs_dim)
    rhs_deps = dimsys_SI.get_dimensional_dependencies(rhs_dim)
    return lhs_deps == rhs_deps


def check_equation_dimensions(
    equations: tuple[tuple[Dimension, Dimension, str], ...],
) -> tuple[CheckResult, ...]:
    """Check dimensional consistency of a batch of equation pairs.

    Args:
        equations: Tuple of (lhs_dimension, rhs_dimension, description) triples.

    Returns:
        Tuple of CheckResult, one per equation pair.
    """
    results: list[CheckResult] = []
    for lhs_dim, rhs_dim, expr_description in equations:
        lhs_deps = dimsys_SI.get_dimensional_dependencies(lhs_dim)
        rhs_deps = dimsys_SI.get_dimensional_dependencies(rhs_dim)

        if lhs_deps == rhs_deps:
            results.append(
                CheckResult(
                    check="equations",
                    severity=Severity.INFO,
                    message=f"Dimensions consistent: '{expr_description}'",
                )
            )
        else:
            results.append(
                CheckResult(
                    check="equations",
                    severity=Severity.ERROR,
                    message=(
                        f"Dimensional mismatch in '{expr_description}': "
                        f"LHS dims {dict(lhs_deps)} != RHS dims {dict(rhs_deps)}"
                    ),
                )
            )
    return tuple(results)


def trace_dimensions_from_ast(
    extracted: ASTExtractionResult,
) -> tuple[CheckResult, ...]:
    """Bridge from AST extraction to SymPy dimensional checking.

    For Phase 1, implements a conservative version that only reports
    when no traceable expressions are found. Full expression tracing
    (arithmetic on parameters with known unit hints) is planned for
    later phases.

    Args:
        extracted: Result from AST-based code analysis.

    Returns:
        Tuple of CheckResult with dimensional analysis findings.
    """
    # Phase 1: conservative — only trace if we have parameters with unit hints
    params_with_units = [
        p for p in extracted.params.parameters if p.unit_hint
    ]

    if not params_with_units:
        return (
            CheckResult(
                check="equations",
                severity=Severity.INFO,
                message="No traceable dimensional expressions found in code",
            ),
        )

    # Future: trace arithmetic expressions on these parameters
    return (
        CheckResult(
            check="equations",
            severity=Severity.INFO,
            message=(
                f"Found {len(params_with_units)} parameters with unit hints; "
                "full expression tracing deferred to Phase 2"
            ),
        ),
    )
