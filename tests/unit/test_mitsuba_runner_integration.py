"""Integration tests for Mitsuba detection wired into the runner pipeline.

Verifies that the runner detects Mitsuba availability after environment
discovery and injects appropriate context into the agent registry, so
the scene agent prompt receives either Mitsuba template instructions
or numpy fallback guidance.
"""

from __future__ import annotations

from agentsim.physics.mitsuba_detection import (
    format_mitsuba_scene_context,
    has_mitsuba_transient,
)
from agentsim.orchestrator.agent_registry import build_agent_registry
from agentsim.state.models import AvailablePackage, EnvironmentInfo


def _make_env(*package_names: str) -> EnvironmentInfo:
    """Create a minimal EnvironmentInfo with the given package names."""
    return EnvironmentInfo(
        packages=tuple(AvailablePackage(name=n) for n in package_names),
        python_version="3.12.1",
    )


class TestHasMitsubaTransient:
    """Tests for has_mitsuba_transient detection function."""

    def test_both_packages_available(self) -> None:
        env = _make_env("numpy", "mitsuba", "mitransient")
        assert has_mitsuba_transient(env) is True

    def test_mitsuba_only(self) -> None:
        env = _make_env("numpy", "mitsuba")
        assert has_mitsuba_transient(env) is False

    def test_mitransient_only(self) -> None:
        env = _make_env("numpy", "mitransient")
        assert has_mitsuba_transient(env) is False

    def test_neither_available(self) -> None:
        env = _make_env("numpy", "scipy")
        assert has_mitsuba_transient(env) is False


class TestFormatMitsubaSceneContext:
    """Tests for format_mitsuba_scene_context output."""

    def test_mitsuba_available_returns_nonempty(self) -> None:
        result = format_mitsuba_scene_context(True)
        assert len(result) > 0

    def test_numpy_fallback_returns_nonempty(self) -> None:
        result = format_mitsuba_scene_context(False)
        assert len(result) > 0

    def test_mitsuba_context_mentions_mitsuba(self) -> None:
        result = format_mitsuba_scene_context(True)
        assert "Mitsuba" in result or "mitsuba" in result

    def test_numpy_context_mentions_numpy(self) -> None:
        result = format_mitsuba_scene_context(False)
        assert "numpy" in result.lower()

    def test_numpy_context_mentions_approximate(self) -> None:
        result = format_mitsuba_scene_context(False)
        assert "approximate" in result.lower()


class TestAgentRegistryMitsubaContext:
    """Tests that build_agent_registry passes mitsuba_context to scene agent."""

    def test_mitsuba_context_in_scene_prompt(self) -> None:
        env = _make_env("numpy", "mitsuba", "mitransient")
        mitsuba_ctx = format_mitsuba_scene_context(True)
        agents = build_agent_registry(
            environment=env,
            mitsuba_context=mitsuba_ctx,
        )
        scene_agent = agents["scene"]
        assert "Mitsuba" in scene_agent.prompt

    def test_numpy_fallback_in_scene_prompt(self) -> None:
        env = _make_env("numpy")
        numpy_ctx = format_mitsuba_scene_context(False)
        agents = build_agent_registry(
            environment=env,
            mitsuba_context=numpy_ctx,
        )
        scene_agent = agents["scene"]
        assert "approximate" in scene_agent.prompt.lower()

    def test_empty_mitsuba_context_default(self) -> None:
        """build_agent_registry works without mitsuba_context (backward compat)."""
        env = _make_env("numpy")
        agents = build_agent_registry(environment=env)
        scene_agent = agents["scene"]
        assert "Rendering Engine Context" in scene_agent.prompt

    def test_mitsuba_context_separate_from_domain_context(self) -> None:
        """mitsuba_context does not overwrite domain_context['scene']."""
        env = _make_env("numpy", "mitsuba", "mitransient")
        domain_ctx = {"scene": "DOMAIN_SCENE_PHYSICS"}
        mitsuba_ctx = format_mitsuba_scene_context(True)
        agents = build_agent_registry(
            environment=env,
            domain_context=domain_ctx,
            mitsuba_context=mitsuba_ctx,
        )
        scene_agent = agents["scene"]
        assert "DOMAIN_SCENE_PHYSICS" in scene_agent.prompt
        assert "Mitsuba" in scene_agent.prompt


class TestEndToEndDetectionFlow:
    """Tests the full detection -> context -> registry flow."""

    def test_full_flow_mitsuba(self) -> None:
        env = _make_env("numpy", "mitsuba", "mitransient")
        available = has_mitsuba_transient(env)
        ctx = format_mitsuba_scene_context(available)
        agents = build_agent_registry(environment=env, mitsuba_context=ctx)
        assert "Mitsuba 3" in agents["scene"].prompt

    def test_full_flow_no_mitsuba(self) -> None:
        env = _make_env("numpy", "scipy")
        available = has_mitsuba_transient(env)
        ctx = format_mitsuba_scene_context(available)
        agents = build_agent_registry(environment=env, mitsuba_context=ctx)
        assert "Numpy Approximate" in agents["scene"].prompt
