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

        agent = create_hypothesis_agent("test env", nlos_physics_context="")
        assert "NLOS Transient Imaging" not in agent.prompt

    def test_non_empty_context_included_in_prompt(self) -> None:
        from agentsim.agents.hypothesis import create_hypothesis_agent

        ctx = "## NLOS Transient Imaging Physics Context\nSome physics."
        agent = create_hypothesis_agent("test env", nlos_physics_context=ctx)
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

        agent = create_physics_advisor_agent(nlos_domain_knowledge="")
        assert "NLOS" not in agent.prompt or "NLOS Transient" not in agent.prompt

    def test_advisor_non_empty_context_included(self) -> None:
        from agentsim.agents.physics_advisor import create_physics_advisor_agent

        ctx = "### NLOS Transient Imaging Domain Knowledge\nSome knowledge."
        agent = create_physics_advisor_agent(nlos_domain_knowledge=ctx)
        assert "NLOS Transient Imaging Domain Knowledge" in agent.prompt
