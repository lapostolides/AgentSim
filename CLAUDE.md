# AgentSim

Autonomous hypothesis-driven simulation system for scientific research.

## Project Structure

- `src/agentsim/` — Main package
  - `state/` — Frozen Pydantic models and pure transition functions
  - `agents/` — Agent definitions and prompt templates
  - `orchestrator/` — Experiment loop and agent registry
  - `mcp_discovery/` — MCP backend discovery and capability schema
  - `hooks/` — Audit and validation hooks
  - `utils/` — File handling, logging
- `mcp_servers/` — Reference MCP server implementations
- `tests/` — Unit, integration, and E2E tests

## Key Principles

- All state models are frozen (immutable). Never mutate state — return new instances.
- Agents discover simulation backends dynamically via MCP.
- Domain-agnostic — not tied to any specific simulation domain.
- Tests required for every module. TDD workflow: RED → GREEN → REFACTOR.

## Commands

- `pip install -e ".[dev]"` — Install in development mode
- `pytest` — Run all tests
- `pytest tests/unit/` — Run unit tests only
- `agentsim run "hypothesis"` — Run an experiment
- `agentsim interactive` — Start interactive REPL
