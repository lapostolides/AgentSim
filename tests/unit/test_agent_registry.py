"""Tests for agent registry factory."""

from claude_agent_sdk.types import AgentDefinition

from agentsim.orchestrator.agent_registry import (
    build_agent_registry,
    get_agent_names,
)
from agentsim.state.models import AvailablePackage, EnvironmentInfo


class TestBuildAgentRegistry:
    def test_no_environment(self):
        registry = build_agent_registry()
        expected = {
            "literature_scout", "citation_auditor", "hypothesis", "scene",
            "executor", "evaluator", "analyst", "literature_validator",
        }
        assert set(registry.keys()) == expected
        for agent in registry.values():
            assert isinstance(agent, AgentDefinition)

    def test_with_environment(self):
        env = EnvironmentInfo(
            packages=(
                AvailablePackage(name="mitsuba", version="3.5.0", import_name="mitsuba"),
                AvailablePackage(name="numpy", version="1.26.0", import_name="numpy"),
            ),
            python_version="3.12.1",
        )
        registry = build_agent_registry(env)

        # All agents should be present
        assert len(registry) == 8

        # Scene and hypothesis agents should know about packages
        assert "mitsuba" in registry["hypothesis"].prompt
        assert "numpy" in registry["hypothesis"].prompt
        assert "mitsuba" in registry["scene"].prompt

    def test_agent_tools(self):
        registry = build_agent_registry()

        # All agents use simple tools — no MCP patterns
        assert registry["literature_scout"].tools == ["WebSearch", "WebFetch", "Read"]
        assert registry["citation_auditor"].tools == ["WebSearch", "WebFetch", "Read"]
        assert registry["hypothesis"].tools == ["Read", "Glob"]
        assert registry["scene"].tools == ["Read", "Bash"]
        assert registry["executor"].tools == ["Bash", "Read"]
        assert registry["evaluator"].tools == ["Bash", "Read", "Glob"]
        assert registry["analyst"].tools == ["Read", "Glob"]
        assert registry["literature_validator"].tools == ["WebSearch", "Read"]

    def test_model_assignments(self):
        registry = build_agent_registry()
        assert registry["literature_scout"].model == "claude-opus-4-6"
        assert "sonnet" in registry["citation_auditor"].model
        assert registry["hypothesis"].model == "claude-opus-4-6"
        assert registry["scene"].model == "sonnet"
        assert registry["executor"].model == "sonnet"
        assert registry["evaluator"].model == "sonnet"
        assert registry["analyst"].model == "claude-opus-4-6"
        assert registry["literature_validator"].model == "claude-opus-4-6"


class TestGetAgentNames:
    def test_returns_ordered_phases(self):
        names = get_agent_names()
        assert names == [
            "literature_scout",
            "citation_auditor",
            "hypothesis",
            "scene",
            "executor",
            "evaluator",
            "analyst",
            "literature_validator",
        ]
