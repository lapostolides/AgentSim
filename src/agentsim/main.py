"""CLI and interactive REPL entrypoint for AgentSim."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

from agentsim.cli.gates import CliInterventionHandler
from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.orchestrator.gates import ALL_CHECKPOINTS, GateCheckpoint
from agentsim.orchestrator.runner import run_experiment
from agentsim.state.serialization import serialize_state
from agentsim.utils.logging_config import configure_logging

logger = structlog.get_logger()

_GATE_CHOICES = ["all", "none"] + [c.value for c in GateCheckpoint]


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _validate_api_key() -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise click.ClickException(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
    if not key.startswith("sk-ant-"):
        raise click.ClickException(
            "ANTHROPIC_API_KEY does not look valid (expected 'sk-ant-...' prefix). "
            "Check your .env file."
        )


def _resolve_checkpoints(gates: tuple[str, ...]) -> frozenset[str]:
    """Resolve --gates options to a frozenset of checkpoint names."""
    if "none" in gates:
        return frozenset()
    if "all" in gates or not gates:
        return ALL_CHECKPOINTS
    return frozenset(gates)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """AgentSim — Autonomous hypothesis-driven simulation."""
    _load_env()
    configure_logging(verbose=verbose)


@cli.command()
@click.argument("hypothesis")
@click.option("--files", "-f", multiple=True, help="Path to input file (can repeat)")
@click.option("--output", "-o", default="./output", help="Output directory")
@click.option("--max-iterations", "-n", default=5, help="Max experiment iterations")
@click.option("--max-budget", "-b", default=10.0, help="Max budget in USD")
@click.option("--json-output", is_flag=True, help="Output final state as JSON")
@click.option(
    "--gates", "-g", multiple=True, type=click.Choice(_GATE_CHOICES, case_sensitive=False),
    help="Intervention gates to enable (default: all). Use 'none' for autonomous mode.",
)
def run(
    hypothesis: str,
    files: tuple[str, ...],
    output: str,
    max_iterations: int,
    max_budget: float,
    json_output: bool,
    gates: tuple[str, ...],
) -> None:
    """Run an experiment from a hypothesis.

    Human intervention gates are enabled by default. Pass --gates none
    for fully autonomous execution.

    Example:
        agentsim run "Does surface roughness affect reconstruction accuracy?" \\
            -f scene.stl -f config.yaml

        agentsim run "My hypothesis" --gates none   # autonomous mode
        agentsim run "My hypothesis" -g post_hypothesis -g scene_visualization
    """
    _validate_api_key()

    checkpoints = _resolve_checkpoints(gates)
    handler = CliInterventionHandler() if checkpoints else None

    config = OrchestratorConfig(
        max_iterations=max_iterations,
        max_budget_usd=max_budget,
        output_dir=Path(output),
        intervention_checkpoints=checkpoints,
    )

    file_paths = list(files) if files else None

    def on_phase_complete(phase: str, state):
        if not json_output:
            click.echo(f"  [{phase}] status={state.status.value}")

    if not json_output:
        mode = "interactive" if checkpoints else "autonomous"
        click.echo(f"AgentSim — Starting experiment ({mode} mode)")
        click.echo(f"  Hypothesis: {hypothesis[:80]}...")
        click.echo(f"  Files: {list(files) if files else 'none'}")
        if checkpoints:
            click.echo(f"  Gates: {', '.join(sorted(checkpoints))}")
        click.echo()

    state = asyncio.run(
        run_experiment(
            hypothesis_text=hypothesis,
            file_paths=file_paths,
            config=config,
            on_phase_complete=on_phase_complete,
            intervention_handler=handler,
        )
    )

    if json_output:
        click.echo(serialize_state(state))
    else:
        _print_summary(state)


@cli.command()
@click.option("--output", "-o", default="./output", help="Output directory")
@click.option("--max-budget", "-b", default=10.0, help="Max budget in USD")
@click.option(
    "--gates", "-g", multiple=True, type=click.Choice(_GATE_CHOICES, case_sensitive=False),
    help="Intervention gates (default: all).",
)
def interactive(output: str, max_budget: float, gates: tuple[str, ...]) -> None:
    """Start an interactive experiment session.

    All intervention gates are enabled by default. The pipeline pauses
    at each checkpoint so you can review, edit, or redirect.
    """
    _validate_api_key()

    checkpoints = _resolve_checkpoints(gates)
    handler = CliInterventionHandler() if checkpoints else None

    click.echo("AgentSim Interactive Mode")
    click.echo("=" * 40)
    if checkpoints:
        click.echo(f"Gates enabled: {', '.join(sorted(checkpoints))}")
    click.echo("Type your hypothesis, or 'quit' to exit.\n")

    while True:
        hypothesis = click.prompt("Hypothesis", type=str)
        if hypothesis.lower() in ("quit", "exit", "q"):
            click.echo("Goodbye!")
            break

        # Collect optional files
        files: list[str] = []
        while True:
            file_path = click.prompt(
                "Add file (or press Enter to skip)",
                default="",
                show_default=False,
            )
            if not file_path:
                break
            if Path(file_path).exists():
                files.append(file_path)
                click.echo(f"  Added: {file_path}")
            else:
                click.echo(f"  File not found: {file_path}")

        config = OrchestratorConfig(
            max_iterations=1,
            max_budget_usd=max_budget,
            output_dir=Path(output),
            intervention_checkpoints=checkpoints,
        )

        def on_phase_complete(phase: str, state):
            click.echo(f"\n  Phase [{phase}] complete — status: {state.status.value}")
            if phase == "analyst" and state.analyses:
                latest = state.analyses[-1]
                click.echo(f"  Findings: {latest.findings}")
                click.echo(f"  Confidence: {latest.confidence}")
                if latest.next_experiments:
                    click.echo(f"  Suggested next: {latest.next_experiments}")

        click.echo("\nRunning experiment...")
        state = asyncio.run(
            run_experiment(
                hypothesis_text=hypothesis,
                file_paths=files or None,
                config=config,
                on_phase_complete=on_phase_complete,
                intervention_handler=handler,
            )
        )

        _print_summary(state)
        click.echo()


def _print_summary(state) -> None:
    click.echo("\n" + "=" * 40)
    click.echo("EXPERIMENT SUMMARY")
    click.echo("=" * 40)
    click.echo(f"  ID: {state.id}")
    click.echo(f"  Status: {state.status.value}")
    click.echo(f"  Iterations: {state.iteration}")

    if state.hypothesis:
        click.echo(f"\n  Hypothesis: {state.hypothesis.formalized or state.hypothesis.raw_text}")

    if state.scenes:
        click.echo(f"\n  Scenes generated: {len(state.scenes)}")

    if state.execution_results:
        successes = sum(1 for r in state.execution_results if r.status == "success")
        click.echo(f"  Executions: {successes}/{len(state.execution_results)} successful")

    if state.analyses:
        latest = state.analyses[-1]
        click.echo(f"\n  Latest Analysis:")
        click.echo(f"    Confidence: {latest.confidence:.0%}")
        click.echo(f"    Supports hypothesis: {latest.supports_hypothesis}")
        for finding in latest.findings:
            click.echo(f"    - {finding}")

    if state.errors:
        click.echo(f"\n  Errors: {len(state.errors)}")
        for error in state.errors:
            click.echo(f"    ! {error}")

    click.echo()


if __name__ == "__main__":
    cli()
