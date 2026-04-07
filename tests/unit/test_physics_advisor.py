"""Tests for the physics advisor agent and consultation logging.

Verifies AgentDefinition creation, prompt content, consultation helpers,
and JSONL logging.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentsim.physics.models import (
    ConsultationLogEntry,
    PhysicsConsultationSummary,
    PhysicsGuidance,
    PhysicsQuery,
)


# ---------------------------------------------------------------------------
# Physics advisor agent tests
# ---------------------------------------------------------------------------


def test_create_physics_advisor_agent_returns_agent_definition():
    """create_physics_advisor_agent() returns AgentDefinition with model='sonnet'."""
    from agentsim.agents.physics_advisor import create_physics_advisor_agent

    agent = create_physics_advisor_agent()
    assert agent.model == "sonnet"
    assert agent.description


def test_advisor_prompt_contains_anti_hallucination():
    """AgentDefinition prompt instructs agent to never 'recall' constants."""
    from agentsim.agents.physics_advisor import create_physics_advisor_agent

    agent = create_physics_advisor_agent()
    assert "NEVER" in agent.prompt
    assert "recall" in agent.prompt


def test_advisor_prompt_contains_constants():
    """AgentDefinition prompt contains the constants registry content."""
    from agentsim.agents.physics_advisor import create_physics_advisor_agent

    agent = create_physics_advisor_agent()
    assert "speed_of_light" in agent.prompt
    assert "boltzmann" in agent.prompt


def test_advisor_prompt_has_runtime_placeholders():
    """Prompt has {query_context} and {state_context} for runtime substitution."""
    from agentsim.agents.physics_advisor import create_physics_advisor_agent

    agent = create_physics_advisor_agent()
    assert "{query_context}" in agent.prompt
    assert "{state_context}" in agent.prompt


# ---------------------------------------------------------------------------
# Consultation helper tests
# ---------------------------------------------------------------------------


def test_build_advisor_prompt_includes_query_fields():
    """_build_advisor_prompt includes query type, context, and parameters."""
    from agentsim.physics.consultation import _build_advisor_prompt

    query = PhysicsQuery(
        query_type="parameter_plausibility",
        context="Check if 500K temperature is reasonable",
        parameters={"name": "temperature", "value": 500, "unit": "kelvin"},
    )
    prompt = _build_advisor_prompt(query, "experiment state here")
    assert "parameter_plausibility" in prompt
    assert "500K temperature" in prompt
    assert "experiment state here" in prompt


def test_parse_guidance_valid_json():
    """_parse_guidance handles valid JSON response."""
    from agentsim.physics.consultation import _parse_guidance

    valid_json = json.dumps({
        "domain_detected": "thermodynamics",
        "confidence": 0.95,
        "recommendations": ["Use Fourier law"],
        "warnings": [],
        "governing_equations": ["dT/dt = alpha * d2T/dx2"],
    })
    guidance = _parse_guidance(valid_json)
    assert guidance.domain_detected == "thermodynamics"
    assert guidance.confidence == 0.95
    assert len(guidance.recommendations) == 1


def test_parse_guidance_malformed_returns_default():
    """_parse_guidance handles malformed response gracefully."""
    from agentsim.physics.consultation import _parse_guidance

    guidance = _parse_guidance("This is not JSON at all {{{")
    assert guidance.domain_detected == "unknown"
    assert guidance.confidence == 0.0
    assert len(guidance.warnings) > 0  # Should note parse failure


def test_parse_guidance_code_fence():
    """_parse_guidance extracts JSON from code fences."""
    from agentsim.physics.consultation import _parse_guidance

    response = '```json\n{"domain_detected": "optics", "confidence": 0.8}\n```'
    guidance = _parse_guidance(response)
    assert guidance.domain_detected == "optics"


# ---------------------------------------------------------------------------
# Consultation logging tests
# ---------------------------------------------------------------------------


def test_append_consultation_log_creates_file(tmp_path: Path):
    """_append_consultation_log creates JSONL file if it doesn't exist."""
    from agentsim.physics.consultation import _append_consultation_log

    entry = ConsultationLogEntry(
        query=PhysicsQuery(
            query_type="test",
            context="test context",
        ),
        response=PhysicsGuidance(domain_detected="test_domain", confidence=0.5),
        domain="test_domain",
        confidence=0.5,
    )
    _append_consultation_log(tmp_path, entry)

    log_file = tmp_path / "physics_consultations.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["domain"] == "test_domain"


def test_append_consultation_log_appends_entries(tmp_path: Path):
    """_append_consultation_log appends multiple entries to same file."""
    from agentsim.physics.consultation import _append_consultation_log

    for i in range(3):
        entry = ConsultationLogEntry(
            query=PhysicsQuery(query_type="test", context=f"context {i}"),
            response=PhysicsGuidance(domain_detected=f"domain_{i}"),
            domain=f"domain_{i}",
            confidence=float(i) / 3,
        )
        _append_consultation_log(tmp_path, entry)

    log_file = tmp_path / "physics_consultations.jsonl"
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# Consultation summary tests
# ---------------------------------------------------------------------------


def test_update_consultation_summary_from_none():
    """_update_consultation_summary creates new summary from None."""
    from agentsim.physics.consultation import _update_consultation_summary

    entry = ConsultationLogEntry(
        query=PhysicsQuery(query_type="test", context="ctx"),
        response=PhysicsGuidance(
            domain_detected="fluids",
            warnings=("high Reynolds",),
        ),
        domain="fluids",
        confidence=0.9,
    )
    summary = _update_consultation_summary(None, entry)
    assert summary.total_consultations == 1
    assert "fluids" in summary.domains_consulted
    assert summary.total_warnings == 1


def test_update_consultation_summary_increments():
    """_update_consultation_summary increments counts correctly."""
    from agentsim.physics.consultation import _update_consultation_summary

    existing = PhysicsConsultationSummary(
        total_consultations=2,
        domains_consulted=("fluids",),
        total_warnings=1,
    )
    entry = ConsultationLogEntry(
        query=PhysicsQuery(query_type="test", context="ctx"),
        response=PhysicsGuidance(
            domain_detected="optics",
            warnings=("diffraction limit", "aberration"),
        ),
        domain="optics",
        confidence=0.8,
    )
    summary = _update_consultation_summary(existing, entry)
    assert summary.total_consultations == 3
    assert "fluids" in summary.domains_consulted
    assert "optics" in summary.domains_consulted
    assert summary.total_warnings == 3


def test_update_consultation_summary_no_duplicate_domains():
    """_update_consultation_summary does not duplicate existing domains."""
    from agentsim.physics.consultation import _update_consultation_summary

    existing = PhysicsConsultationSummary(
        total_consultations=1,
        domains_consulted=("fluids",),
    )
    entry = ConsultationLogEntry(
        query=PhysicsQuery(query_type="test", context="ctx"),
        response=PhysicsGuidance(domain_detected="fluids"),
        domain="fluids",
        confidence=0.9,
    )
    summary = _update_consultation_summary(existing, entry)
    assert summary.total_consultations == 2
    assert summary.domains_consulted.count("fluids") == 1
