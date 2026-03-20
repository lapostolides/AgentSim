"""Validation hook — prevents dangerous operations during simulation.

PreToolUse hook that blocks potentially destructive operations
that agents might attempt during scene generation or execution.
"""

from __future__ import annotations

import structlog
from claude_agent_sdk.types import HookMatcher

logger = structlog.get_logger()

# Patterns that should be blocked in Bash tool calls
BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=",
    ":(){",  # fork bomb
    "shutdown",
    "reboot",
    "curl.*| sh",
    "curl.*| bash",
    "wget.*| sh",
    "wget.*| bash",
]


def create_validation_hooks() -> dict[str, list[HookMatcher]]:
    """Create hook matchers for operation validation.

    Blocks dangerous shell commands that agents might try to execute.
    """
    return {
        "PreToolUse": [
            HookMatcher(
                tool_name="Bash",
                command=(
                    'python3 -c "'
                    "import sys, json; "
                    "inp = json.load(sys.stdin); "
                    "cmd = inp.get('tool_input', {}).get('command', ''); "
                    f"blocked = {BLOCKED_PATTERNS!r}; "
                    "matches = [p for p in blocked if p in cmd]; "
                    "print(json.dumps("
                    "{'decision': 'deny', 'reason': f'Blocked: {matches[0]}'}"
                    " if matches else {'decision': 'allow'}"
                    "))"
                    '"'
                ),
            ),
        ],
    }
