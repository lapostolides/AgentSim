"""Explorer mode -- find novel parameter regions outside published baselines.

Compares hypothesis parameters against published baselines from paradigm
knowledge and identifies novel parameter combinations. Proposes experiments
for parameter regions not covered by published work. No LLM calls.
"""

from __future__ import annotations

from agentsim.physics.domains.schema import ParadigmKnowledge
from agentsim.physics.reasoning.models import (
    ExplorerResult,
    NovelExperiment,
    NovelParameter,
)


def _build_covered_ranges(
    published_baselines: dict[str, dict],
) -> dict[str, tuple[float, float]]:
    """Build min/max coverage ranges from published baselines.

    Scans all baseline dicts and collects numeric values per parameter.
    Non-numeric values (strings like "confocal", "paper") are skipped.

    Args:
        published_baselines: Baseline identifier -> parameter dict.

    Returns:
        Dict mapping parameter name to (min, max) tuple.
    """
    ranges: dict[str, tuple[float, float]] = {}

    for _baseline_name, baseline_data in published_baselines.items():
        for key, val in baseline_data.items():
            if not isinstance(val, (int, float)):
                continue
            if key in ranges:
                current_min, current_max = ranges[key]
                new_range = (min(current_min, float(val)), max(current_max, float(val)))
                ranges[key] = new_range
            else:
                ranges[key] = (float(val), float(val))

    return ranges


def _find_novel_params(
    hypothesis_params: dict[str, float],
    covered_ranges: dict[str, tuple[float, float]],
) -> tuple[NovelParameter, ...]:
    """Identify hypothesis parameters outside covered baseline ranges.

    Args:
        hypothesis_params: Parameter name-value pairs from hypothesis.
        covered_ranges: Parameter -> (min, max) from baselines.

    Returns:
        Tuple of NovelParameter objects for novel params.
    """
    novel: list[NovelParameter] = []

    for param, value in hypothesis_params.items():
        if param in covered_ranges:
            baseline_min, baseline_max = covered_ranges[param]
            if value < baseline_min or value > baseline_max:
                novel.append(
                    NovelParameter(
                        parameter=param,
                        value=value,
                        baseline_min=baseline_min,
                        baseline_max=baseline_max,
                        novelty_type="out_of_range",
                    )
                )
        else:
            novel.append(
                NovelParameter(
                    parameter=param,
                    value=value,
                    novelty_type="no_baseline",
                )
            )

    return tuple(novel)


def _propose_experiments(
    hypothesis_params: dict[str, float],
    novel_params: tuple[NovelParameter, ...],
) -> tuple[NovelExperiment, ...]:
    """Generate proposed experiments from novel parameter combinations.

    Creates one experiment when there are novel parameters, combining
    all novel values into a single experimental configuration.

    Args:
        hypothesis_params: Original hypothesis parameters.
        novel_params: Identified novel parameters.

    Returns:
        Tuple of proposed experiments (0 or 1 element).
    """
    if not novel_params:
        return ()

    novel_param_names = [np.parameter for np in novel_params]
    experiment_params = {
        np.parameter: np.value
        for np in novel_params
    }

    description = f"Novel configuration: {', '.join(novel_param_names)}"
    scientific_interest = (
        f"Explores parameter region outside published baselines: "
        f"{', '.join(novel_param_names)}"
    )

    experiment = NovelExperiment(
        description=description,
        parameters=experiment_params,
        novel_aspects=novel_params,
        scientific_interest=scientific_interest,
    )

    return (experiment,)


def find_novel_regions(
    hypothesis_params: dict[str, float],
    paradigm: ParadigmKnowledge,
) -> ExplorerResult:
    """Find parameter regions not covered by published baselines.

    Compares each hypothesis parameter against the min/max range
    observed across published baselines in the paradigm. Parameters
    outside the range are flagged as "out_of_range"; parameters not
    present in any baseline are flagged as "no_baseline".

    When novel parameters are found, proposes an experiment combining
    the novel values.

    Args:
        hypothesis_params: Parameter name-value pairs from the hypothesis.
        paradigm: Paradigm with published_baselines to compare against.

    Returns:
        ExplorerResult with novel parameters and proposed experiments.
    """
    covered_ranges = _build_covered_ranges(paradigm.published_baselines)
    novel_params = _find_novel_params(hypothesis_params, covered_ranges)
    experiments = _propose_experiments(hypothesis_params, novel_params)

    return ExplorerResult(
        paradigm=paradigm.paradigm,
        novel_parameters=novel_params,
        proposed_experiments=experiments,
    )
