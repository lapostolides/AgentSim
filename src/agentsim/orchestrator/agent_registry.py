"""Agent registry — builds AgentDefinitions based on environment.

The registry constructs agent definitions with knowledge of what
Python packages are available, so agents can write code that uses them.
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

from agentsim.agents.analyst import create_analyst_agent
from agentsim.agents.citation_auditor import create_citation_auditor_agent
from agentsim.agents.evaluator import create_evaluator_agent
from agentsim.agents.executor import create_executor_agent
from agentsim.agents.hypothesis import create_hypothesis_agent
from agentsim.agents.literature_scout import create_literature_scout_agent
from agentsim.agents.literature_validator import create_literature_validator_agent
from agentsim.agents.physics_advisor import create_physics_advisor_agent
from agentsim.agents.scene import create_scene_agent
from agentsim.environment.discovery import format_environment_for_prompt
from agentsim.state.models import EnvironmentInfo


def build_agent_registry(
    environment: EnvironmentInfo | None = None,
) -> dict[str, AgentDefinition]:
    """Build the complete agent registry.

    Args:
        environment: Discovered environment info (available packages).

    Returns:
        Dictionary mapping agent names to their AgentDefinitions,
        suitable for passing to ClaudeAgentOptions.agents.
    """
    env_str = (
        format_environment_for_prompt(environment)
        if environment
        else "No environment info available. Probe with `python3 -c 'import <pkg>'` as needed."
    )

    return {
        "literature_scout": create_literature_scout_agent(),
        "citation_auditor": create_citation_auditor_agent(),
        "hypothesis": create_hypothesis_agent(env_str),
        "scene": create_scene_agent(env_str),
        "physics_advisor": create_physics_advisor_agent(),
        "executor": create_executor_agent(),
        "evaluator": create_evaluator_agent(),
        "analyst": create_analyst_agent(),
        "literature_validator": create_literature_validator_agent(),
    }


def get_agent_names() -> list[str]:
    """Return the canonical ordered list of agent phase names."""
    return [
        "literature_scout",
        "citation_auditor",
        "hypothesis",
        "scene",
        "physics_advisor",
        "executor",
        "evaluator",
        "analyst",
        "literature_validator",
    ]
