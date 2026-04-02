"""Tests for JSON normalization helpers in the orchestrator runner.

These tests reproduce REAL agent output patterns that caused failures:
- Nested JSON wrapping ({"hypothesis": {...}})
- Variant field names (statement vs raw_text)
- Dict-typed variables instead of strings
- Thematic clusters instead of entries
- Missing formalized field under variant keys
"""

import pytest

from agentsim.orchestrator.runner import (
    _coerce_to_str_list,
    _extract_literature_entries,
    _unwrap_json,
)


# ── _unwrap_json ─────────────────────────────────────────────────────


class TestUnwrapJson:
    """Test JSON unwrapping for nested and variant agent outputs."""

    HYPOTHESIS_EXPECTED = {
        "raw_text", "formalized", "variables", "parameter_space",
        "predictions", "assumptions", "quality_ratings",
    }

    def test_flat_json_unchanged(self):
        data = {"raw_text": "test", "formalized": "test formal", "variables": ["x"]}
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["raw_text"] == "test"
        assert result["formalized"] == "test formal"

    def test_single_key_nesting(self):
        """Agent wraps output as {"hypothesis": {"raw_text": ...}}."""
        data = {
            "hypothesis": {
                "raw_text": "my hypothesis",
                "formalized": "formal version",
                "variables": ["x", "y"],
            }
        }
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["raw_text"] == "my hypothesis"
        assert result["formalized"] == "formal version"

    def test_wrapper_key_with_more_inner_matches(self):
        """Outer has metadata, inner has the real fields."""
        data = {
            "model": "opus",
            "hypothesis": {
                "raw_text": "test",
                "formalized": "formal",
                "variables": ["a"],
                "predictions": ["p1"],
            },
        }
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["raw_text"] == "test"
        assert result["formalized"] == "formal"

    def test_field_alias_statement_to_raw_text(self):
        data = {"statement": "my statement", "formalized": "formal"}
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["raw_text"] == "my statement"

    def test_field_alias_formalized_statement(self):
        data = {"raw_text": "test", "formalized_statement": "the formal version"}
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["formalized"] == "the formal version"

    def test_field_alias_formalized_hypothesis(self):
        data = {"raw_text": "test", "formalized_hypothesis": "formal hyp"}
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["formalized"] == "formal hyp"

    def test_canonical_key_not_overwritten_by_alias(self):
        """If both 'formalized' and 'formalized_statement' exist, keep 'formalized'."""
        data = {
            "raw_text": "test",
            "formalized": "canonical",
            "formalized_statement": "alias version",
        }
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["formalized"] == "canonical"

    def test_double_nested_unwrap(self):
        """{"hypothesis": {"statement": "...", "formalized_statement": "..."}}"""
        data = {
            "hypothesis": {
                "statement": "raw idea",
                "formalized_statement": "precise version",
                "variables": ["x"],
            }
        }
        result = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)
        assert result["raw_text"] == "raw idea"
        assert result["formalized"] == "precise version"


# ── _coerce_to_str_list ─────────────────────────────────────────────


class TestCoerceToStrList:
    """Test coercion of variant agent outputs to list[str]."""

    def test_already_str_list(self):
        assert _coerce_to_str_list(["x", "y", "z"]) == ["x", "y", "z"]

    def test_dict_list_with_name(self):
        """Real failure: variables as [{"name": "wall_geometry", "description": "..."}]."""
        data = [
            {"name": "wall_geometry", "description": "Shape of relay wall"},
            {"name": "hidden_target_position", "description": "Position of hidden human"},
        ]
        result = _coerce_to_str_list(data)
        assert len(result) == 2
        assert "wall_geometry" in result[0]
        assert "Shape of relay wall" in result[0]

    def test_dict_list_with_condition(self):
        """Real failure: predictions as [{"condition": "concave_mild", "prediction": "..."}]."""
        data = [
            {"condition": "concave_mild", "prediction": "Focusing improves SNR"},
            {"condition": "convex_strong", "prediction": "Defocusing degrades depth"},
        ]
        result = _coerce_to_str_list(data)
        assert len(result) == 2
        assert "concave_mild" in result[0]
        assert "Focusing improves SNR" in result[0]

    def test_dict_with_independent_dependent(self):
        """Real failure: variables as {"independent": [...], "dependent": [...]}."""
        data = {
            "independent": [
                {"name": "wall_curvature", "description": "Radius of curvature"},
            ],
            "dependent": [
                {"name": "rmse", "description": "Localization error"},
            ],
        }
        result = _coerce_to_str_list(data)
        assert len(result) == 2
        assert "wall_curvature" in result[0]
        assert "rmse" in result[1]

    def test_bare_string(self):
        assert _coerce_to_str_list("single variable") == ["single variable"]

    def test_empty_list(self):
        assert _coerce_to_str_list([]) == []

    def test_empty_dict(self):
        assert _coerce_to_str_list({}) == []

    def test_none_returns_empty(self):
        assert _coerce_to_str_list(None) == []

    def test_mixed_list(self):
        data = ["plain_string", {"name": "structured", "description": "var"}, 42]
        result = _coerce_to_str_list(data)
        assert result[0] == "plain_string"
        assert "structured" in result[1]
        assert result[2] == "42"


# ── _extract_literature_entries ──────────────────────────────────────


class TestExtractLiteratureEntries:
    """Test deep extraction of paper entries from variant agent JSON."""

    PAPER_A = {"title": "Paper A", "authors": ["Smith"], "year": 2024}
    PAPER_B = {"title": "Paper B", "authors": ["Jones"], "year": 2023}

    def test_direct_entries(self):
        data = {"entries": [self.PAPER_A, self.PAPER_B], "summary": "Two papers."}
        entries, flat = _extract_literature_entries(data)
        assert len(entries) == 2
        assert entries[0]["title"] == "Paper A"

    def test_nested_literature_context(self):
        """{"literature_context": {"entries": [...]}}"""
        data = {"literature_context": {"entries": [self.PAPER_A], "summary": "One paper."}}
        entries, flat = _extract_literature_entries(data)
        assert len(entries) == 1
        assert flat["summary"] == "One paper."

    def test_papers_key(self):
        data = {"papers": [self.PAPER_A, self.PAPER_B]}
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 2

    def test_references_key(self):
        data = {"references": [self.PAPER_A]}
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 1

    def test_nested_papers_key(self):
        """{"literature_survey": {"papers": [...]}}"""
        data = {"literature_survey": {"papers": [self.PAPER_A, self.PAPER_B]}}
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 2

    def test_thematic_clusters(self):
        """Real failure: {"literature_survey": {"thematic_clusters": [{"papers": [...]}]}}"""
        data = {
            "literature_survey": {
                "thematic_clusters": [
                    {
                        "theme": "NLOS Imaging",
                        "papers": [self.PAPER_A],
                    },
                    {
                        "theme": "Relay Wall Geometry",
                        "papers": [self.PAPER_B],
                    },
                ],
                "summary": "Survey of NLOS literature.",
            }
        }
        entries, flat = _extract_literature_entries(data)
        assert len(entries) == 2
        assert entries[0]["title"] == "Paper A"
        assert entries[1]["title"] == "Paper B"

    def test_thematic_clusters_with_entries_key(self):
        """Clusters using 'entries' instead of 'papers'."""
        data = {
            "thematic_clusters": [
                {"entries": [self.PAPER_A]},
                {"entries": [self.PAPER_B]},
            ]
        }
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 2

    def test_empty_data_returns_empty(self):
        entries, flat = _extract_literature_entries({"summary": "No papers found."})
        assert entries == []

    def test_deeply_nested_no_entries(self):
        """Agent returns weird structure with no recognizable entries."""
        data = {"metadata": {"query": "NLOS"}, "notes": "Could not search."}
        entries, _ = _extract_literature_entries(data)
        assert entries == []


# ── Full hypothesis parsing pipeline ─────────────────────────────────


class TestHypothesisParsePipeline:
    """End-to-end tests simulating real agent JSON → Hypothesis model.

    These reproduce the exact failure patterns seen in production runs.
    """

    HYPOTHESIS_EXPECTED = {
        "raw_text", "formalized", "variables", "parameter_space",
        "predictions", "assumptions", "quality_ratings",
    }

    def _parse_hypothesis(self, data: dict, raw_hypothesis: str = "test hyp") -> dict:
        """Simulate the hypothesis parsing pipeline from runner.py."""
        from agentsim.state.models import Hypothesis

        data = _unwrap_json(data, self.HYPOTHESIS_EXPECTED)

        if "raw_text" not in data:
            data["raw_text"] = raw_hypothesis

        if not data.get("formalized"):
            for key in ("formalized_statement", "formalized_hypothesis",
                        "hypothesis_statement", "statement", "formal_statement",
                        "testable_statement", "refined_hypothesis"):
                if key in data and isinstance(data[key], str) and data[key]:
                    data["formalized"] = data[key]
                    break

        for list_field in ("variables", "predictions", "assumptions"):
            if list_field in data and not all(
                isinstance(x, str) for x in data.get(list_field, [])
            ):
                data[list_field] = _coerce_to_str_list(data[list_field])

        try:
            hypothesis = Hypothesis.model_validate(data)
        except Exception:
            hypothesis = Hypothesis(
                raw_text=raw_hypothesis,
                formalized=data.get("formalized", "") or "fallback",
                variables=_coerce_to_str_list(data.get("variables", [])),
                predictions=_coerce_to_str_list(data.get("predictions", [])),
                assumptions=_coerce_to_str_list(data.get("assumptions", [])),
            )

        # Guarantee formalized is never empty (mirrors runner.py logic)
        if not hypothesis.formalized:
            fallback_formalized = ""
            for v in data.values():
                if isinstance(v, str) and len(v) > 50:
                    fallback_formalized = v
                    break
            if not fallback_formalized:
                fallback_formalized = raw_hypothesis
            hypothesis = Hypothesis(
                id=hypothesis.id,
                raw_text=hypothesis.raw_text,
                formalized=fallback_formalized,
                variables=hypothesis.variables,
                parameter_space=hypothesis.parameter_space,
                predictions=hypothesis.predictions,
                assumptions=hypothesis.assumptions,
                quality_ratings=hypothesis.quality_ratings,
            )

        return hypothesis

    def test_ideal_agent_output(self):
        """Agent returns exactly what we ask for."""
        data = {
            "raw_text": "Does wall curvature affect NLOS?",
            "formalized": "Concave relay walls improve localization RMSE by >20%.",
            "variables": ["wall_curvature", "rmse"],
            "predictions": ["Concave improves", "Convex degrades"],
            "assumptions": ["Lambertian surface"],
        }
        h = self._parse_hypothesis(data)
        assert h.raw_text == "Does wall curvature affect NLOS?"
        assert h.formalized == "Concave relay walls improve localization RMSE by >20%."
        assert len(h.variables) == 2
        assert len(h.predictions) == 2

    def test_real_failure_nested_with_dict_variables(self):
        """Exact pattern from April 2 run: nested + dict variables."""
        data = {
            "hypothesis": {
                "statement": "Wall curvature affects NLOS localization.",
                "formalized_statement": "Concave relay walls with R<2m improve 3D localization RMSE by >20%.",
                "variables": [
                    {"name": "wall_geometry", "description": "Shape", "levels": ["flat", "concave", "convex"]},
                    {"name": "target_position", "description": "Hidden human position"},
                ],
                "predictions": [
                    {"condition": "concave_mild", "prediction": "Focusing boosts SNR"},
                    {"condition": "convex_strong", "prediction": "Degrades depth accuracy"},
                ],
                "assumptions": ["Lambertian BRDF", "Single hidden person"],
                "quality_ratings": {
                    "decision_relevance": 0.9,
                    "non_triviality": 0.8,
                    "falsifiability": 0.95,
                    "composite_score": 0.85,
                },
                "parameter_space": [
                    {"name": "radius_of_curvature", "values": [1.0, 2.0, 4.0]},
                ],
                "samples_per_pixel": 512,
            }
        }
        h = self._parse_hypothesis(data, "Wall curvature affects NLOS")
        assert h.formalized != ""
        assert "Concave" in h.formalized or "concave" in h.formalized
        assert len(h.variables) >= 2
        assert all(isinstance(v, str) for v in h.variables)
        assert len(h.predictions) >= 2
        assert all(isinstance(p, str) for p in h.predictions)

    def test_real_failure_independent_dependent_dict(self):
        """Variables as {"independent": [...], "dependent": [...]}."""
        data = {
            "raw_text": "test",
            "formalized": "formal test",
            "variables": {
                "independent": [
                    {"name": "wall_curvature", "description": "Radius of curvature"},
                ],
                "dependent": [
                    {"name": "lateral_rmse_m", "description": "Lateral RMSE"},
                    {"name": "depth_rmse_m", "description": "Depth RMSE"},
                ],
            },
            "predictions": ["Concave improves", "Convex degrades"],
        }
        h = self._parse_hypothesis(data)
        assert len(h.variables) == 3
        assert all(isinstance(v, str) for v in h.variables)

    def test_missing_formalized_uses_variant_key(self):
        """Agent uses 'testable_statement' instead of 'formalized'."""
        data = {
            "raw_text": "test",
            "testable_statement": "Concave walls with R=2m reduce RMSE by 20% vs flat walls.",
            "variables": ["curvature", "rmse"],
        }
        h = self._parse_hypothesis(data)
        assert "Concave walls" in h.formalized

    def test_missing_formalized_uses_refined_hypothesis(self):
        data = {
            "raw_text": "test",
            "refined_hypothesis": "A carefully refined statement about wall geometry effects.",
            "variables": ["x"],
        }
        h = self._parse_hypothesis(data)
        assert "refined statement" in h.formalized

    def test_completely_missing_formalized_uses_long_string(self):
        """No recognizable formalized key — falls back to first long string."""
        data = {
            "raw_text": "test",
            "analysis_text": "This is a very detailed analysis of the hypothesis that spans many words and provides a thorough formalization of the research question.",
            "variables": ["x"],
        }
        h = self._parse_hypothesis(data)
        assert len(h.formalized) > 50

    def test_never_returns_empty_formalized(self):
        """Even with garbage input, formalized is never empty."""
        data = {"garbage_key": 42, "another": True}
        h = self._parse_hypothesis(data, "my raw hypothesis")
        assert h.formalized != ""
        assert h.raw_text == "my raw hypothesis"


# ── Literature entries: additional cluster variants ──────────────────


class TestExtractLiteratureEntriesVariants:
    """Test that newly discovered cluster key names are handled."""

    PAPER = {"title": "Test Paper", "authors": ["Author"], "year": 2024}

    def test_topic_clusters(self):
        """Real failure from April 2: agent used 'topic_clusters'."""
        data = {
            "literature_survey": {
                "topic_clusters": [
                    {"title": "NLOS Methods", "papers": [self.PAPER]},
                    {"title": "Relay Walls", "papers": [self.PAPER]},
                ]
            }
        }
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 2

    def test_research_clusters(self):
        data = {
            "research_clusters": [
                {"papers": [self.PAPER]},
            ]
        }
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 1

    def test_citations_key(self):
        data = {"citations": [self.PAPER, self.PAPER]}
        entries, _ = _extract_literature_entries(data)
        assert len(entries) == 2


# ── Citation auditor parsing ─────────────────────────────────────────


class TestCitationAuditorParsing:
    """Test that citation auditor JSON is parsed robustly."""

    def test_direct_audited_entries(self):
        data = {
            "audited_entries": [
                {"original_title": "Paper A", "verification_status": "verified"},
            ],
            "summary": "1 of 1 verified",
            "fabricated_count": 0,
        }
        expected = {"audited_entries", "summary", "fabricated_count"}
        result = _unwrap_json(data, expected)
        assert "audited_entries" in result
        assert len(result["audited_entries"]) == 1

    def test_wrapped_citation_audit(self):
        """Agent wraps as {"citation_audit": {"audited_entries": [...]}}."""
        data = {
            "citation_audit": {
                "audited_entries": [
                    {"original_title": "Paper A", "verification_status": "verified"},
                ],
                "summary": "1 verified",
                "fabricated_count": 0,
            }
        }
        expected = {"audited_entries", "summary", "fabricated_count"}
        result = _unwrap_json(data, expected)
        assert "audited_entries" in result


# ── Analyst parsing ──────────────────────────────────────────────────


class TestAnalystParsing:
    """Test analyst JSON variants."""

    def test_direct_analyst_output(self):
        data = {
            "hypothesis_id": "abc123",
            "findings": ["Finding 1", "Finding 2"],
            "confidence": 0.85,
            "supports_hypothesis": True,
            "should_stop": False,
            "reasoning": "Based on results...",
        }
        expected = {"hypothesis_id", "findings", "confidence",
                    "supports_hypothesis", "should_stop"}
        result = _unwrap_json(data, expected)
        assert result["hypothesis_id"] == "abc123"

    def test_wrapped_analysis(self):
        """Agent wraps as {"analysis": {...}}."""
        data = {
            "analysis": {
                "hypothesis_id": "abc123",
                "findings": ["Finding 1"],
                "confidence": 0.9,
                "supports_hypothesis": True,
                "should_stop": True,
                "reasoning": "Clear result.",
            }
        }
        expected = {"hypothesis_id", "findings", "confidence",
                    "supports_hypothesis", "should_stop"}
        result = _unwrap_json(data, expected)
        assert result["hypothesis_id"] == "abc123"
        assert result["confidence"] == 0.9


# ── Literature validator parsing ─────────────────────────────────────


class TestLiteratureValidatorParsing:
    """Test literature validator JSON variants."""

    def test_direct_output(self):
        from agentsim.state.models import LiteratureValidation

        data = {
            "hypothesis_id": "hyp1",
            "consistency_assessment": "Results align with prior work.",
            "novel_findings": ["Novel finding 1"],
            "concerns": [],
            "suggested_citations": ["Smith 2024"],
            "overall_confidence_adjustment": 0.1,
            "reasoning": "Literature supports these findings.",
        }
        v = LiteratureValidation.model_validate(data)
        assert v.hypothesis_id == "hyp1"

    def test_wrapped_validation(self):
        """Agent wraps as {"validation": {...}}."""
        data = {
            "validation": {
                "hypothesis_id": "hyp1",
                "consistency_assessment": "Consistent.",
                "novel_findings": [],
                "concerns": [],
                "suggested_citations": [],
                "overall_confidence_adjustment": 0.0,
                "reasoning": "No issues.",
            }
        }
        expected = {"hypothesis_id", "consistency_assessment",
                    "novel_findings", "concerns", "reasoning"}
        result = _unwrap_json(data, expected)
        assert result["hypothesis_id"] == "hyp1"

    def test_missing_hypothesis_id_handled(self):
        """Parser should not crash if hypothesis_id is missing."""
        data = {
            "consistency_assessment": "Results are consistent.",
            "reasoning": "All good.",
        }
        expected = {"hypothesis_id", "consistency_assessment", "reasoning"}
        result = _unwrap_json(data, expected)
        # hypothesis_id won't be magically added by unwrap, but shouldn't crash
        assert "consistency_assessment" in result


# ── Scene parsing ────────────────────────────────────────────────────


class TestSceneParsing:
    """Test scene JSON variants."""

    def test_scenes_list(self):
        data = {
            "scenes": [
                {"plan_id": "p1", "code": "print('hello')", "language": "python"},
            ]
        }
        expected = {"plan_id", "scenes", "code", "language"}
        result = _unwrap_json(data, expected)
        assert "scenes" in result
        assert len(result["scenes"]) == 1

    def test_single_scene_no_wrapper(self):
        """Agent returns a single scene without the 'scenes' list."""
        data = {"code": "print('hello')", "language": "python", "parameters": {}}
        expected = {"plan_id", "scenes", "code", "language"}
        result = _unwrap_json(data, expected)
        assert "code" in result

    def test_wrapped_scene(self):
        """Agent wraps as {"scene": {"code": ...}}."""
        data = {
            "scene": {
                "code": "import numpy as np\nprint(np.ones(3))",
                "language": "python",
                "plan_id": "auto",
            }
        }
        expected = {"plan_id", "scenes", "code", "language"}
        result = _unwrap_json(data, expected)
        assert "code" in result


# ── Executor parsing ─────────────────────────────────────────────────


class TestExecutorParsing:
    """Test executor JSON variants."""

    def test_results_list(self):
        data = {
            "results": [
                {"scene_id": "s1", "status": "success", "duration_seconds": 1.5},
            ]
        }
        expected = {"results", "scene_id", "status"}
        result = _unwrap_json(data, expected)
        assert "results" in result

    def test_single_result_no_wrapper(self):
        data = {"scene_id": "s1", "status": "success", "stdout": "done"}
        expected = {"results", "scene_id", "status"}
        result = _unwrap_json(data, expected)
        assert "scene_id" in result


# ── Evaluator parsing ────────────────────────────────────────────────


class TestEvaluatorParsing:
    """Test evaluator JSON variants."""

    def test_evaluations_list(self):
        data = {
            "evaluations": [
                {"scene_id": "s1", "metrics": {"psnr": 25.3}, "summary": "Good."},
            ]
        }
        expected = {"evaluations", "scene_id", "metrics"}
        result = _unwrap_json(data, expected)
        assert "evaluations" in result

    def test_wrapped_evaluation(self):
        """Agent wraps as {"evaluation": {"scene_id": ...}}."""
        data = {
            "evaluation": {
                "scene_id": "s1",
                "metrics": {"psnr": 25.3},
                "summary": "Good results.",
            }
        }
        expected = {"evaluations", "scene_id", "metrics"}
        result = _unwrap_json(data, expected)
        assert "scene_id" in result
