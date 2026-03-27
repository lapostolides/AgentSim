"""Tests for literature scout, citation auditor, and literature validator agents."""

from claude_agent_sdk.types import AgentDefinition

from agentsim.agents.citation_auditor import create_citation_auditor_agent
from agentsim.agents.literature_scout import create_literature_scout_agent
from agentsim.agents.literature_validator import create_literature_validator_agent


class TestLiteratureScoutAgent:
    def test_creates_valid_definition(self):
        agent = create_literature_scout_agent()
        assert isinstance(agent, AgentDefinition)

    def test_has_web_search_tools(self):
        agent = create_literature_scout_agent()
        assert "WebSearch" in agent.tools
        assert "WebFetch" in agent.tools
        assert "Read" in agent.tools

    def test_uses_opus_model(self):
        agent = create_literature_scout_agent()
        assert agent.model == "claude-opus-4-6"

    def test_prompt_contains_schema(self):
        agent = create_literature_scout_agent()
        assert "entries" in agent.prompt
        assert "key_findings" in agent.prompt
        assert "open_questions" in agent.prompt

    def test_prompt_has_state_placeholder(self):
        agent = create_literature_scout_agent()
        assert "{state_context}" in agent.prompt


class TestCitationAuditorAgent:
    def test_creates_valid_definition(self):
        agent = create_citation_auditor_agent()
        assert isinstance(agent, AgentDefinition)

    def test_has_web_tools(self):
        agent = create_citation_auditor_agent()
        assert "WebSearch" in agent.tools
        assert "WebFetch" in agent.tools
        assert "Read" in agent.tools

    def test_uses_sonnet_model(self):
        """Auditor uses Sonnet for cost-efficient systematic checking."""
        agent = create_citation_auditor_agent()
        assert "sonnet" in agent.model

    def test_prompt_contains_verification_schema(self):
        agent = create_citation_auditor_agent()
        assert "audited_entries" in agent.prompt
        assert "verification_status" in agent.prompt
        assert "fabricated" in agent.prompt

    def test_prompt_has_state_placeholder(self):
        agent = create_citation_auditor_agent()
        assert "{state_context}" in agent.prompt


class TestLiteratureValidatorAgent:
    def test_creates_valid_definition(self):
        agent = create_literature_validator_agent()
        assert isinstance(agent, AgentDefinition)

    def test_has_web_search_tools(self):
        agent = create_literature_validator_agent()
        assert "WebSearch" in agent.tools
        assert "Read" in agent.tools

    def test_uses_opus_model(self):
        """Validator uses opus 4.6 for deep literature validation."""
        agent = create_literature_validator_agent()
        assert agent.model == "claude-opus-4-6"

    def test_prompt_contains_schema(self):
        agent = create_literature_validator_agent()
        assert "consistency_assessment" in agent.prompt
        assert "novel_findings" in agent.prompt
        assert "concerns" in agent.prompt

    def test_prompt_has_state_placeholder(self):
        agent = create_literature_validator_agent()
        assert "{state_context}" in agent.prompt
