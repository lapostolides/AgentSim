"""Tests for NLOS domain context injection into LLM agent prompts.

Covers format_nlos_physics_context (hypothesis), format_nlos_advisor_context
(physics advisor), and their integration into agent factory functions.
"""

from __future__ import annotations

import pytest

from agentsim.physics.domains import load_domain
from agentsim.physics.domains.schema import DomainKnowledge


@pytest.fixture()
def nlos_domain() -> DomainKnowledge:
    """Load the NLOS domain knowledge from YAML."""
    dk = load_domain("nlos_transient_imaging")
    assert dk is not None
    return dk


# ── Task 1: Hypothesis agent NLOS context ──────────────────────────

class TestFormatNlosPhysicsContext:
    """Tests for format_nlos_physics_context (hypothesis agent)."""

    def test_includes_transient_transport(self, nlos_domain: DomainKnowledge) -> None:
        from agentsim.agents.hypothesis import format_nlos_physics_context

        ctx = format_nlos_physics_context(nlos_domain)
        assert "transient_transport" in ctx

    def test_includes_dimensionless_groups(self, nlos_domain: DomainKnowledge) -> None:
        from agentsim.agents.hypothesis import format_nlos_physics_context

        ctx = format_nlos_physics_context(nlos_domain)
        assert "Dimensionless Groups" in ctx
        # Should contain at least one group name
        assert any(
            dg.name in ctx for dg in nlos_domain.dimensionless_groups
        )

    def test_includes_reconstruction_algorithms(
        self, nlos_domain: DomainKnowledge,
    ) -> None:
        from agentsim.agents.hypothesis import format_nlos_physics_context

        ctx = format_nlos_physics_context(nlos_domain)
        for key in ("lct", "fk_migration", "phasor_fields"):
            if key in nlos_domain.reconstruction_algorithms:
                algo = nlos_domain.reconstruction_algorithms[key]
                assert algo.name in ctx, f"Missing algorithm: {algo.name}"

    def test_includes_geometry_constraints(
        self, nlos_domain: DomainKnowledge,
    ) -> None:
        from agentsim.agents.hypothesis import format_nlos_physics_context

        ctx = format_nlos_physics_context(nlos_domain)
        assert "Geometry Constraints" in ctx

    def test_empty_context_excluded_from_prompt(self) -> None:
        from agentsim.agents.hypothesis import create_hypothesis_agent

        agent = create_hypothesis_agent("test env", physics_context="")
        assert "NLOS Transient Imaging" not in agent.prompt

    def test_non_empty_context_included_in_prompt(self) -> None:
        from agentsim.agents.hypothesis import create_hypothesis_agent

        ctx = "## NLOS Transient Imaging Physics Context\nSome physics."
        agent = create_hypothesis_agent("test env", physics_context=ctx)
        assert "NLOS Transient Imaging Physics Context" in agent.prompt


# ── Task 1: Physics advisor NLOS context ────────────────────────────

class TestFormatNlosAdvisorContext:
    """Tests for format_nlos_advisor_context (physics advisor)."""

    def test_includes_governing_equations_and_params(
        self, nlos_domain: DomainKnowledge,
    ) -> None:
        from agentsim.agents.physics_advisor import format_nlos_advisor_context

        ctx = format_nlos_advisor_context(nlos_domain)
        assert "transient_transport" in ctx or "NLOS" in ctx
        # Should have at least some equation info
        assert "Domain Knowledge" in ctx

    def test_advisor_empty_context_excluded(self) -> None:
        from agentsim.agents.physics_advisor import create_physics_advisor_agent

        agent = create_physics_advisor_agent(domain_knowledge="")
        assert "NLOS" not in agent.prompt or "NLOS Transient" not in agent.prompt

    def test_advisor_non_empty_context_included(self) -> None:
        from agentsim.agents.physics_advisor import create_physics_advisor_agent

        ctx = "### NLOS Transient Imaging Domain Knowledge\nSome knowledge."
        agent = create_physics_advisor_agent(domain_knowledge=ctx)
        assert "NLOS Transient Imaging Domain Knowledge" in agent.prompt


# ---------------------------------------------------------------------------
# Task 2: Analyst agent NLOS context
# ---------------------------------------------------------------------------


class TestFormatNlosAnalysisContext:
    """Tests for format_nlos_analysis_context (analyst agent)."""

    def test_includes_inverse_square_and_temporal_peaks(
        self, nlos_domain: DomainKnowledge,
    ) -> None:
        """Test 1: Returns string with inverse-square falloff and temporal peak locations."""
        from agentsim.agents.analyst import format_nlos_analysis_context

        ctx = format_nlos_analysis_context(nlos_domain)
        assert "inverse-square falloff" in ctx
        assert "temporal peak locations" in ctx.lower() or "Temporal peak" in ctx

    def test_includes_reconstruction_resolution_limits(
        self, nlos_domain: DomainKnowledge,
    ) -> None:
        """Test 2: Includes reconstruction resolution limits."""
        from agentsim.agents.analyst import format_nlos_analysis_context

        ctx = format_nlos_analysis_context(nlos_domain)
        assert "resolution" in ctx.lower()


class TestAnalystAgentNlosSection:
    """Tests for create_analyst_agent with NLOS context."""

    def test_empty_context_no_nlos_section(self) -> None:
        """Test 3: create_analyst_agent with analysis_context='' has no NLOS section."""
        from agentsim.agents.analyst import create_analyst_agent

        agent = create_analyst_agent(analysis_context="")
        assert "NLOS Transient Imaging" not in agent.prompt

    def test_nonempty_context_includes_nlos_section(self) -> None:
        """Test 4: create_analyst_agent with non-empty context includes NLOS section."""
        from agentsim.agents.analyst import create_analyst_agent

        ctx = "## NLOS Transient Imaging Result Validation\nSome validation."
        agent = create_analyst_agent(analysis_context=ctx)
        assert "NLOS Transient Imaging Result Validation" in agent.prompt


# ---------------------------------------------------------------------------
# Task 2: Agent registry with NLOS context
# ---------------------------------------------------------------------------


class TestBuildAgentRegistryNlos:
    """Tests for build_agent_registry with nlos_context parameter."""

    def test_with_domain_context_produces_physics_agents(self) -> None:
        """Test 5: build_agent_registry with domain_context includes physics in agent prompts."""
        from agentsim.orchestrator.agent_registry import build_agent_registry

        domain_ctx = {
            "hypothesis": "## NLOS Transient Imaging Physics Context\nHyp content.",
            "analyst": "## NLOS Transient Imaging Result Validation\nAna content.",
            "advisor": "### NLOS Transient Imaging Domain Knowledge\nAdv content.",
            "scene": "## Physics Constraints for Scene Generation\nScene content.",
        }
        registry = build_agent_registry(domain_context=domain_ctx)
        assert "NLOS Transient Imaging Physics Context" in registry["hypothesis"].prompt
        assert "NLOS Transient Imaging Result Validation" in registry["analyst"].prompt
        assert "NLOS Transient Imaging Domain Knowledge" in registry["physics_advisor"].prompt
        assert "Physics Constraints for Scene Generation" in registry["scene"].prompt

    def test_without_domain_context_backward_compatible(self) -> None:
        """Test 6: build_agent_registry without domain_context produces standard agents."""
        from agentsim.orchestrator.agent_registry import build_agent_registry

        registry = build_agent_registry()
        assert "NLOS Transient Imaging" not in registry["hypothesis"].prompt
        assert "NLOS Transient Imaging" not in registry["analyst"].prompt
