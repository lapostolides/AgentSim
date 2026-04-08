"""Deterministic constraint propagation engine.

Evaluates transfer function chains entirely in Python -- no LLM calls.
Given input parameter values and a collection of TransferFunctions,
propagates constraints via BFS to compute all reachable derived quantities.

Key design choices:
- Relationship dispatch table avoids eval() of formula strings.
- BFS with visited-edge tracking prevents infinite loops on circular TFs.
- Immutable inputs: neither the inputs dict nor the TF tuple are mutated.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Callable

import structlog

from agentsim.physics.domains.schema import TransferFunction
from agentsim.physics.reasoning.models import ComputedValue, PropagationResult

logger = structlog.get_logger()

# Maximum BFS iterations to guard against pathological graphs.
_MAX_ITERATIONS = 100

# ---------------------------------------------------------------------------
# Relationship evaluators — pure functions, no side effects
# ---------------------------------------------------------------------------

_RELATIONSHIP_EVALUATORS: dict[str, Callable[[float], float]] = {
    "linear": lambda x: x,
    "proportional": lambda x: x,
    "inverse": lambda x: 1.0 / x if x != 0.0 else float("inf"),
    "sqrt": lambda x: math.sqrt(abs(x)),
    "inverse_sqrt": lambda x: 1.0 / math.sqrt(abs(x)) if x != 0.0 else float("inf"),
    "quadratic": lambda x: x * x,
    "logarithmic": lambda x: math.log(abs(x)) if abs(x) > 0.0 else float("-inf"),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_tf(tf: TransferFunction, input_value: float) -> float:
    """Evaluate a single transfer function on an input value.

    Looks up ``tf.relationship`` in the dispatch table and applies it.
    Unknown relationships fall through as identity (pass-through).

    Args:
        tf: The transfer function to evaluate.
        input_value: Numeric value of the input parameter.

    Returns:
        The computed output value.
    """
    evaluator = _RELATIONSHIP_EVALUATORS.get(tf.relationship)
    if evaluator is None:
        logger.warning(
            "unknown_tf_relationship",
            relationship=tf.relationship,
            input_param=tf.input,
            output_param=tf.output,
        )
        return input_value
    return evaluator(input_value)


def build_tf_graph(
    transfer_functions: tuple[TransferFunction, ...],
) -> dict[str, list[TransferFunction]]:
    """Build a lookup graph keyed by input parameter name.

    Deduplicates by (input, output) pair, keeping the first occurrence.

    Args:
        transfer_functions: Tuple of TransferFunction objects.

    Returns:
        Dict mapping input parameter names to lists of TFs that consume them.
    """
    graph: dict[str, list[TransferFunction]] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for tf in transfer_functions:
        pair = (tf.input, tf.output)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        if tf.input not in graph:
            graph[tf.input] = []
        graph[tf.input].append(tf)

    return graph


def propagate_constraints(
    inputs: dict[str, float],
    transfer_functions: tuple[TransferFunction, ...],
) -> PropagationResult:
    """Propagate input parameters through a TF graph via BFS.

    Evaluates each reachable transfer function, cascading outputs as inputs
    for downstream TFs. Tracks visited (input, output) edges to prevent
    infinite loops on circular graphs.

    Args:
        inputs: Parameter name-value pairs to seed propagation.
        transfer_functions: All available transfer functions.

    Returns:
        PropagationResult with all computed values and any warnings.
    """
    graph = build_tf_graph(transfer_functions)
    computed: list[ComputedValue] = []
    warnings: list[str] = []

    # BFS queue: (parameter_name, parameter_value)
    queue: deque[tuple[str, float]] = deque()
    for param, value in inputs.items():
        queue.append((param, value))

    # Track visited edges to prevent cycles
    visited_edges: set[tuple[str, str]] = set()
    iterations = 0

    while queue and iterations < _MAX_ITERATIONS:
        iterations += 1
        param, value = queue.popleft()

        # Find all TFs that consume this parameter
        tfs_for_param = graph.get(param, [])
        for tf in tfs_for_param:
            edge = (tf.input, tf.output)
            if edge in visited_edges:
                continue
            visited_edges.add(edge)

            output_value = evaluate_tf(tf, value)
            cv = ComputedValue(
                parameter=tf.output,
                value=output_value,
                source_input=param,
                source_tf_formula=tf.formula,
                relationship=tf.relationship,
            )
            computed.append(cv)

            # Cascade: if the output feeds other TFs, enqueue it
            if tf.output in graph:
                queue.append((tf.output, output_value))

    if iterations >= _MAX_ITERATIONS:
        warnings.append(
            f"Propagation reached max iterations ({_MAX_ITERATIONS}); "
            "possible circular TF chain."
        )

    return PropagationResult(
        inputs=dict(inputs),  # defensive copy — do not hold reference to caller's dict
        computed=tuple(computed),
        warnings=tuple(warnings),
    )
