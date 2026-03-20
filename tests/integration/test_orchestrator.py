"""Integration tests for the orchestrator.

These tests verify the orchestrator's internal logic (JSON extraction,
state transitions, config handling) WITHOUT making real API calls.
Real API calls are tested in E2E tests.
"""

import json

import pytest

from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.orchestrator.runner import _extract_json_from_text


class TestExtractJsonFromText:
    def test_direct_json(self):
        text = '{"key": "value", "count": 42}'
        result = _extract_json_from_text(text)
        assert result == {"key": "value", "count": 42}

    def test_json_in_code_fence(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        result = _extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_json_in_plain_fence(self):
        text = 'Result:\n```\n{"key": "value"}\n```'
        result = _extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'The analysis shows {"findings": ["result1"], "confidence": 0.85} as output.'
        result = _extract_json_from_text(text)
        assert result["confidence"] == 0.85

    def test_no_json(self):
        text = "This is plain text with no JSON content."
        result = _extract_json_from_text(text)
        assert result is None

    def test_nested_json(self):
        data = {
            "hypothesis_id": "abc",
            "findings": ["finding1"],
            "confidence": 0.9,
            "supports_hypothesis": True,
            "should_stop": False,
            "next_experiments": ["try more values"],
            "reasoning": "Based on metrics...",
        }
        text = f"Analysis complete:\n```json\n{json.dumps(data)}\n```"
        result = _extract_json_from_text(text)
        assert result["hypothesis_id"] == "abc"
        assert result["confidence"] == 0.9


class TestOrchestratorConfig:
    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.max_iterations == 5
        assert config.max_budget_usd == 10.0
        assert config.extra_packages == {}

    def test_custom_config(self):
        config = OrchestratorConfig(
            max_iterations=3,
            max_budget_usd=5.0,
            extra_packages={"custom_sim": "custom_sim"},
        )
        assert config.max_iterations == 3
        assert "custom_sim" in config.extra_packages

    def test_frozen(self):
        config = OrchestratorConfig()
        with pytest.raises(Exception):
            config.max_iterations = 10  # type: ignore[misc]
