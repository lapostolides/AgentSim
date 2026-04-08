"""Frozen Pydantic output models for the physics-space reasoning engine.

These models represent computed quantities from deterministic constraint
propagation, optimizer scoring, and novelty exploration. All models are
immutable (frozen=True), following the codebase convention.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Propagation outputs
# ---------------------------------------------------------------------------


class ComputedValue(BaseModel, frozen=True):
    """A single derived quantity produced by evaluating a transfer function.

    Args:
        parameter: Name of the derived output parameter.
        value: Computed numeric value.
        source_input: Name of the input parameter that produced this value.
        source_tf_formula: Human-readable formula string from the TF.
        relationship: Functional relationship type (e.g. "linear", "inverse").
    """

    parameter: str
    value: float
    source_input: str = ""
    source_tf_formula: str = ""
    relationship: str = ""


class PropagationResult(BaseModel, frozen=True):
    """Result of cascading constraint propagation through a TF graph.

    Args:
        inputs: The input parameter values that seeded propagation.
        computed: All derived quantities produced by BFS traversal.
        warnings: Any warnings generated during propagation.
    """

    inputs: dict[str, float] = Field(default_factory=dict)
    computed: tuple[ComputedValue, ...] = ()
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Optimizer outputs
# ---------------------------------------------------------------------------


class ScoredSetup(BaseModel, frozen=True):
    """A sensor+algorithm pairing scored by the optimizer.

    Args:
        sensor_class: Sensor class identifier.
        algorithm: Algorithm identifier.
        computed_metrics: Metrics derived from propagation for this setup.
        score: Numeric quality score (higher is better).
        rationale: Human-readable explanation of the score.
    """

    sensor_class: str
    algorithm: str
    computed_metrics: tuple[ComputedValue, ...] = ()
    score: float = 0.0
    rationale: str = ""


class OptimizerResult(BaseModel, frozen=True):
    """Result of optimizer mode: ranked sensor+algorithm setups.

    Args:
        paradigm: Paradigm under which optimization was performed.
        setups: Scored setups ordered by descending score.
        rationale: Overall optimization rationale.
    """

    paradigm: str
    setups: tuple[ScoredSetup, ...] = ()
    rationale: str = ""


# ---------------------------------------------------------------------------
# Explorer outputs
# ---------------------------------------------------------------------------


class NovelParameter(BaseModel, frozen=True):
    """A parameter value that falls outside published baselines.

    Args:
        parameter: Parameter name.
        value: The novel value.
        baseline_min: Minimum published baseline value.
        baseline_max: Maximum published baseline value.
        novelty_type: Description of how it's novel (e.g. "above_max").
    """

    parameter: str
    value: float
    baseline_min: float = 0.0
    baseline_max: float = 0.0
    novelty_type: str = ""


class NovelExperiment(BaseModel, frozen=True):
    """A proposed novel experiment with parameters and scientific interest.

    Args:
        description: What the experiment investigates.
        parameters: Parameter name-value pairs for the experiment.
        novel_aspects: Which parameters are novel and why.
        scientific_interest: Why this experiment is scientifically interesting.
    """

    description: str
    parameters: dict[str, float] = Field(default_factory=dict)
    novel_aspects: tuple[NovelParameter, ...] = ()
    scientific_interest: str = ""


class ExplorerResult(BaseModel, frozen=True):
    """Result of explorer mode: novel parameter combinations and experiments.

    Args:
        paradigm: Paradigm under which exploration was performed.
        novel_parameters: Parameters outside published baselines.
        proposed_experiments: Suggested novel experiments.
        rationale: Overall exploration rationale.
    """

    paradigm: str
    novel_parameters: tuple[NovelParameter, ...] = ()
    proposed_experiments: tuple[NovelExperiment, ...] = ()
    rationale: str = ""
