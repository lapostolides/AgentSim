# Hook System

> Claude Agent SDK hooks for audit logging and operation validation during agent execution.

## Files

### __init__.py
Empty package init.

### audit_hook.py
Creates PostToolUse hooks for experiment traceability.

- `create_audit_hooks()` -- Returns a `HookMatcher` dict that logs every tool use to `/tmp/agentsim_audit.log` with a UTC timestamp. Matches all tools (`tool_name="*"`).
- `build_audit_log_path(experiment_id, output_dir)` -- Constructs the audit log file path for a specific experiment.

### validation_hook.py
Creates PreToolUse hooks that block dangerous shell commands.

- `create_validation_hooks()` -- Returns a `HookMatcher` dict that intercepts Bash tool calls and checks the command against `BLOCKED_PATTERNS`. Blocks: `rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, fork bombs, `shutdown`, `reboot`, and piped curl/wget to shell.
- Implementation: A Python one-liner reads the tool input JSON from stdin, checks for pattern matches, and outputs `{"decision": "deny", "reason": ...}` or `{"decision": "allow"}`.

## Key Patterns

- **Agent SDK integration**: Uses `HookMatcher` from `claude_agent_sdk.types` to register pre/post tool-use handlers.
- **Defense in depth**: Validation hooks prevent agents from executing destructive operations even if their prompts don't explicitly forbid them.
- **Audit trail**: Every tool invocation is logged for reproducibility and debugging.

## Dependencies

- **Depends on**: `claude_agent_sdk.types` (HookMatcher), `structlog`.
- **Depended on by**: `orchestrator.runner` or `main.py` (registers hooks when building agent configurations).
