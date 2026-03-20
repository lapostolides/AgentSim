"""JSON serialization helpers for experiment state.

Handles roundtrip serialization of frozen Pydantic models,
used to pass state between agent phases as prompt content.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from agentsim.state.models import ExperimentState

T = TypeVar("T", bound=BaseModel)


def serialize_state(state: ExperimentState) -> str:
    """Serialize experiment state to JSON string for agent prompts."""
    return state.model_dump_json(indent=2)


def deserialize_state(json_str: str) -> ExperimentState:
    """Deserialize JSON string back to ExperimentState."""
    return ExperimentState.model_validate_json(json_str)


def serialize_model(model: BaseModel) -> str:
    """Serialize any Pydantic model to JSON string."""
    return model.model_dump_json(indent=2)


def deserialize_model(json_str: str, model_class: type[T]) -> T:
    """Deserialize JSON string to a specific Pydantic model type."""
    return model_class.model_validate_json(json_str)


def state_to_prompt_context(state: ExperimentState, max_length: int = 50_000) -> str:
    """Format state as a context block for agent prompts.

    Truncates if the serialized state exceeds max_length to
    prevent context window overflow in long experiments.
    """
    serialized = serialize_state(state)
    if len(serialized) <= max_length:
        return f"<experiment_state>\n{serialized}\n</experiment_state>"

    # Truncate by keeping essential fields and summarizing the rest
    data = json.loads(serialized)
    essential_keys = {
        "id", "status", "iteration", "raw_hypothesis", "hypothesis",
        "plan", "literature_context",
    }
    truncated = {k: v for k, v in data.items() if k in essential_keys}
    truncated["_truncated"] = True
    truncated["_total_scenes"] = len(data.get("scenes", []))
    truncated["_total_results"] = len(data.get("execution_results", []))
    truncated["_total_evaluations"] = len(data.get("evaluations", []))

    # Keep only the latest analysis
    analyses = data.get("analyses", [])
    if analyses:
        truncated["latest_analysis"] = analyses[-1]

    compact = json.dumps(truncated, indent=2, default=str)
    return f"<experiment_state truncated=\"true\">\n{compact}\n</experiment_state>"
