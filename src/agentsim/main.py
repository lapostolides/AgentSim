"""CLI and interactive REPL entrypoint for AgentSim."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
import structlog

from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.orchestrator.runner import run_experiment
from agentsim.state.serialization import serialize_state
from agentsim.utils.logging_config import configure_logging

logger = structlog.get_logger()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """AgentSim — Autonomous hypothesis-driven simulation."""
    configure_logging(verbose=verbose)


@cli.command()
@click.argument("hypothesis")
@click.option("--files", "-f", multiple=True, help="Path to input file (can repeat)")
@click.option("--output", "-o", default="./output", help="Output directory")
@click.option("--max-iterations", "-n", default=5, help="Max experiment iterations")
@click.option("--max-budget", "-b", default=10.0, help="Max budget in USD")
@click.option("--json-output", is_flag=True, help="Output final state as JSON")
def run(
    hypothesis: str,
    files: tuple[str, ...],
    output: str,
    max_iterations: int,
    max_budget: float,
    json_output: bool,
) -> None:
    """Run an experiment from a hypothesis.

    Example:
        agentsim run "Does surface roughness affect reconstruction accuracy?" \\
            -f scene.stl -f config.yaml
    """
    config = OrchestratorConfig(
        max_iterations=max_iterations,
        max_budget_usd=max_budget,
        output_dir=Path(output),
    )

    file_paths = list(files) if files else None

    def on_phase_complete(phase: str, state):
        if not json_output:
            click.echo(f"  [{phase}] status={state.status.value}")

    if not json_output:
        click.echo("AgentSim — Starting experiment")
        click.echo(f"  Hypothesis: {hypothesis[:80]}...")
        click.echo(f"  Files: {list(files) if files else 'none'}")
        click.echo()

    state = asyncio.run(
        run_experiment(
            hypothesis_text=hypothesis,
            file_paths=file_paths,
            config=config,
            on_phase_complete=on_phase_complete,
        )
    )

    if json_output:
        click.echo(serialize_state(state))
    else:
        _print_summary(state)


@cli.command()
@click.option("--output", "-o", default="./output", help="Output directory")
@click.option("--max-budget", "-b", default=10.0, help="Max budget in USD")
def interactive(output: str, max_budget: float) -> None:
    """Start an interactive experiment session.

    Prompts for a hypothesis and lets you steer between phases.
    """
    click.echo("AgentSim Interactive Mode")
    click.echo("=" * 40)
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
            max_iterations=1,  # Single iteration in interactive mode
            max_budget_usd=max_budget,
            output_dir=Path(output),
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
            )
        )

        _print_summary(state)
        click.echo()


def _print_summary(state) -> None:
    """Print a human-readable experiment summary."""
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
