"""Tests for literature grounding state models."""

import pytest
from pydantic import ValidationError

from agentsim.state.models import (
    ExperimentState,
    ExperimentStatus,
    LiteratureContext,
    LiteratureEntry,
    LiteratureValidation,
)


class TestLiteratureEntry:
    def test_create_minimal(self):
        entry = LiteratureEntry(
            title="Non-Line-of-Sight Imaging via Neural Transient Fields",
            relevance="Establishes baseline NLOS reconstruction method",
        )
        assert entry.title == "Non-Line-of-Sight Imaging via Neural Transient Fields"
        assert entry.relevance != ""
        assert entry.authors == ()
        assert entry.year is None
        assert entry.key_findings == ()
        assert entry.url == ""

    def test_create_full(self):
        entry = LiteratureEntry(
            title="Wave-based NLOS imaging",
            authors=("Liu, X.", "Bauer, S.", "Velten, A."),
            year=2019,
            key_findings=(
                "Phasor fields enable diffraction-limited NLOS imaging",
                "Computational cost scales with O(N^3)",
            ),
            relevance="Foundational method for wave-based reconstruction",
            url="https://arxiv.org/abs/1903.04017",
            doi="10.1038/s41586-019-1461-3",
        )
        assert len(entry.authors) == 3
        assert len(entry.key_findings) == 2
        assert entry.year == 2019
        assert entry.doi != ""

    def test_frozen(self):
        entry = LiteratureEntry(title="Test", relevance="Test")
        with pytest.raises(ValidationError):
            entry.title = "Changed"  # type: ignore[misc]


class TestLiteratureContext:
    def test_create(self):
        entries = (
            LiteratureEntry(title="Paper A", relevance="Method baseline"),
            LiteratureEntry(title="Paper B", relevance="Competing approach"),
        )
        ctx = LiteratureContext(
            entries=entries,
            summary="Two key papers establish the state of the art.",
            open_questions=("Can phasor fields handle specular surfaces?",),
            methodology_notes="Standard metrics: PSNR, SSIM, LPIPS",
        )
        assert len(ctx.entries) == 2
        assert ctx.summary != ""
        assert len(ctx.open_questions) == 1
        assert ctx.methodology_notes != ""

    def test_empty(self):
        ctx = LiteratureContext()
        assert ctx.entries == ()
        assert ctx.summary == ""
        assert ctx.open_questions == ()

    def test_frozen(self):
        ctx = LiteratureContext(summary="test")
        with pytest.raises(ValidationError):
            ctx.summary = "changed"  # type: ignore[misc]


class TestLiteratureValidation:
    def test_create(self):
        validation = LiteratureValidation(
            hypothesis_id="h1",
            consistency_assessment="Results align with Smith et al. (2020) findings on surface roughness.",
            novel_findings=(
                "Discovered non-linear relationship at extreme roughness values",
            ),
            concerns=(
                "Sample size smaller than typical in field (n=3 vs n=10+)",
            ),
            suggested_citations=(
                "Smith et al. (2020) - baseline roughness study",
                "Jones et al. (2022) - non-linear surface effects",
            ),
            overall_confidence_adjustment=0.1,
            reasoning="Strong alignment with prior work boosts confidence.",
        )
        assert validation.hypothesis_id == "h1"
        assert len(validation.novel_findings) == 1
        assert len(validation.concerns) == 1
        assert validation.overall_confidence_adjustment == 0.1

    def test_defaults(self):
        validation = LiteratureValidation(hypothesis_id="h1")
        assert validation.consistency_assessment == ""
        assert validation.novel_findings == ()
        assert validation.concerns == ()
        assert validation.suggested_citations == ()
        assert validation.overall_confidence_adjustment == 0.0

    def test_frozen(self):
        validation = LiteratureValidation(hypothesis_id="h1")
        with pytest.raises(ValidationError):
            validation.hypothesis_id = "h2"  # type: ignore[misc]


class TestExperimentStateWithLiterature:
    def test_initial_state_has_no_literature(self):
        state = ExperimentState(raw_hypothesis="test")
        assert state.literature_context is None
        assert state.literature_validation is None

    def test_state_with_literature_context(self):
        ctx = LiteratureContext(
            entries=(LiteratureEntry(title="Key Paper", relevance="Baseline"),),
            summary="One relevant paper found.",
        )
        state = ExperimentState(
            raw_hypothesis="test",
            literature_context=ctx,
        )
        assert state.literature_context is not None
        assert len(state.literature_context.entries) == 1

    def test_state_with_literature_validation(self):
        validation = LiteratureValidation(
            hypothesis_id="h1",
            consistency_assessment="Consistent with prior work",
        )
        state = ExperimentState(
            raw_hypothesis="test",
            literature_validation=validation,
        )
        assert state.literature_validation is not None

    def test_serialization_roundtrip_with_literature(self):
        ctx = LiteratureContext(
            entries=(
                LiteratureEntry(
                    title="Paper A",
                    authors=("Author 1",),
                    year=2023,
                    key_findings=("Finding 1",),
                    relevance="Relevant",
                ),
            ),
            summary="Summary",
            open_questions=("Question 1",),
        )
        validation = LiteratureValidation(
            hypothesis_id="h1",
            consistency_assessment="Consistent",
            novel_findings=("Novel 1",),
        )
        state = ExperimentState(
            raw_hypothesis="test",
            literature_context=ctx,
            literature_validation=validation,
        )
        json_str = state.model_dump_json()
        restored = ExperimentState.model_validate_json(json_str)
        assert restored.literature_context is not None
        assert len(restored.literature_context.entries) == 1
        assert restored.literature_context.entries[0].title == "Paper A"
        assert restored.literature_validation is not None
        assert restored.literature_validation.consistency_assessment == "Consistent"
