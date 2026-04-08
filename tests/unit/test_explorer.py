"""Tests for explorer mode -- find novel parameter regions.

Covers:
- Params inside baselines → no novelty
- Params below baseline min → out_of_range
- Baseline min/max values correct
- Params not in any baseline → no_baseline
- Non-numeric baseline values filtered without error
- 2+ novel params generates proposed experiment
- NovelExperiment.parameters contains novel values
- Real relay_wall data end-to-end
"""

from __future__ import annotations

import pytest

from agentsim.physics.domains.schema import ParadigmKnowledge
from agentsim.physics.reasoning.explorer import find_novel_regions
from agentsim.physics.reasoning.models import ExplorerResult, NovelParameter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_paradigm(
    *,
    published_baselines: dict[str, dict] | None = None,
) -> ParadigmKnowledge:
    return ParadigmKnowledge(
        paradigm="test_paradigm",
        domain="test_domain",
        published_baselines=published_baselines or {},
    )


# Baselines mimicking relay_wall structure
_BASELINES: dict[str, dict] = {
    "study_a": {
        "paper": "Study A",
        "venue": "Conference 2020",
        "temporal_resolution_ps": 32,
        "wall_size_m": 2.0,
        "scanning": "confocal",
    },
    "study_b": {
        "paper": "Study B",
        "venue": "Journal 2021",
        "temporal_resolution_ps": 55,
        "wall_size_m": 2.0,
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindNovelRegions:
    """Tests for find_novel_regions function."""

    def test_params_inside_baselines(self) -> None:
        """Params inside all baseline ranges → empty novel_parameters."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions(
            {"temporal_resolution_ps": 40.0, "wall_size_m": 2.0},
            paradigm,
        )
        assert isinstance(result, ExplorerResult)
        assert len(result.novel_parameters) == 0

    def test_below_baseline_min_out_of_range(self) -> None:
        """temporal_resolution_ps=5.0 (below 32) → out_of_range."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions({"temporal_resolution_ps": 5.0}, paradigm)
        assert len(result.novel_parameters) == 1
        novel = result.novel_parameters[0]
        assert novel.parameter == "temporal_resolution_ps"
        assert novel.novelty_type == "out_of_range"

    def test_baseline_min_max_values(self) -> None:
        """Baseline min=32, max=55 from _BASELINES fixture."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions({"temporal_resolution_ps": 5.0}, paradigm)
        novel = result.novel_parameters[0]
        assert novel.baseline_min == 32.0
        assert novel.baseline_max == 55.0

    def test_no_baseline_param(self) -> None:
        """Param not in any baseline → no_baseline."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions({"custom_param": 42.0}, paradigm)
        assert len(result.novel_parameters) == 1
        assert result.novel_parameters[0].novelty_type == "no_baseline"

    def test_filters_non_numeric_values(self) -> None:
        """String values in baselines (e.g., 'confocal') are skipped without error."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        # "scanning" is a string field in baselines -- should not crash
        result = find_novel_regions({"temporal_resolution_ps": 40.0}, paradigm)
        assert isinstance(result, ExplorerResult)
        assert len(result.novel_parameters) == 0

    def test_two_novel_params_generates_experiment(self) -> None:
        """2+ novel params → at least 1 proposed experiment."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions(
            {"temporal_resolution_ps": 5.0, "custom_param": 99.0},
            paradigm,
        )
        assert len(result.novel_parameters) >= 2
        assert len(result.proposed_experiments) >= 1

    def test_experiment_contains_novel_values(self) -> None:
        """NovelExperiment.parameters dict contains the novel parameter values."""
        paradigm = _make_paradigm(published_baselines=_BASELINES)
        result = find_novel_regions(
            {"temporal_resolution_ps": 5.0, "custom_param": 99.0},
            paradigm,
        )
        exp = result.proposed_experiments[0]
        assert "temporal_resolution_ps" in exp.parameters
        assert exp.parameters["temporal_resolution_ps"] == 5.0
        assert "custom_param" in exp.parameters
        assert exp.parameters["custom_param"] == 99.0

    def test_real_relay_wall_data(self) -> None:
        """Integration: relay_wall paradigm from YAML works end-to-end."""
        from agentsim.physics.domains import load_domain_bundle

        bundle = load_domain_bundle("nlos_transient_imaging")
        assert bundle is not None
        paradigm = bundle.paradigms["relay_wall"]
        # Use value below published minimum (32 ps)
        result = find_novel_regions({"temporal_resolution_ps": 5.0}, paradigm)
        assert isinstance(result, ExplorerResult)
        assert result.paradigm == "relay_wall"
        assert len(result.novel_parameters) >= 1
