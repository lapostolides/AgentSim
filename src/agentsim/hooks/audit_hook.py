"""Audit hook — logs all tool calls for experiment traceability."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from claude_agent_sdk.types import HookMatcher

logger = structlog.get_logger()


def create_audit_hooks() -> dict[str, list[HookMatcher]]:
    """Create hook matchers for audit logging.

    Logs every tool use (PostToolUse) for experiment traceability.
    This creates a complete audit trail of what the agents did.
    """
    return {
        "PostToolUse": [
            HookMatcher(
                tool_name="*",
                command=(
                    'echo "AUDIT: tool_use at '
                    f'{datetime.now(timezone.utc).isoformat()}'
                    '" >> /tmp/agentsim_audit.log'
                ),
            ),
        ],
    }


def build_audit_log_path(experiment_id: str, output_dir: str = "./output") -> str:
    """Build the audit log file path for an experiment."""
    return f"{output_dir}/{experiment_id}_audit.log"
