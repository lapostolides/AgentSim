"""Click command group for Neo4j knowledge graph lifecycle management.

Exposes ``agentsim graph start|stop|status|seed|query`` subcommands
for managing the Docker container, seeding sensor data, and running
feasibility queries.
"""

from __future__ import annotations

import click
import structlog

from agentsim.knowledge_graph.client import GraphClient
from agentsim.knowledge_graph.degradation import is_graph_available
from agentsim.knowledge_graph.docker import (
    DockerNotAvailableError,
    neo4j_status,
    start_neo4j,
    stop_neo4j,
    wait_for_healthy,
)
from agentsim.knowledge_graph.seeder import seed_graph

logger = structlog.get_logger()


@click.group()
def graph() -> None:
    """Manage the Neo4j knowledge graph."""


@graph.command()
@click.option("--port", default=7687, type=int, help="Bolt protocol port (default 7687)")
@click.option("--password", default="agentsim", help="Neo4j password (default 'agentsim')")
def start(port: int, password: str) -> None:
    """Start the Neo4j Docker container."""
    try:
        start_neo4j(bolt_port=port, password=password)
    except DockerNotAvailableError:
        click.echo(
            "Error: Docker not found. Install Docker to use the knowledge graph.",
            err=True,
        )
        raise SystemExit(1)

    try:
        wait_for_healthy(bolt_port=port, timeout_s=30.0)
        click.echo(f"Neo4j started -- bolt://localhost:{port}")
        click.echo("Browser: http://localhost:7474")
    except TimeoutError:
        click.echo(
            "Warning: Neo4j container started but not yet healthy. "
            "Try 'agentsim graph status' in a few seconds.",
            err=True,
        )


@graph.command()
def stop() -> None:
    """Stop and remove the Neo4j Docker container."""
    stop_neo4j()
    click.echo("Neo4j stopped.")


@graph.command()
def status() -> None:
    """Show the current Neo4j container status."""
    docker_state = neo4j_status()
    bolt_available = is_graph_available()

    click.echo("Container: agentsim-neo4j")
    click.echo(f"Running:   {docker_state.is_running}")
    click.echo(f"Health:    {docker_state.health}")
    click.echo(f"Bolt port: {docker_state.bolt_port}")
    click.echo(f"HTTP port: {docker_state.http_port}")
    click.echo(f"Bolt reachable: {bolt_available}")


@graph.command()
@click.option("--clean", is_flag=True, default=False, help="Wipe graph before seeding")
def seed(clean: bool) -> None:
    """Seed the knowledge graph from sensor YAML files."""
    try:
        with GraphClient() as client:
            result = seed_graph(client, force_clean=clean)
    except (ConnectionRefusedError, OSError) as exc:
        click.echo(
            "Error: Cannot connect to Neo4j. Try 'agentsim graph start' first.",
            err=True,
        )
        logger.debug("seed_connection_error", error=str(exc))
        raise SystemExit(1)

    click.echo(
        f"Seeded: {result.sensors_created} sensors, "
        f"{result.families_created} families, "
        f"{result.edges_created} edges"
    )
    if result.errors:
        click.echo(f"\nErrors ({len(result.errors)}):")
        for error in result.errors:
            click.echo(f"  - {error}")


@graph.command()
@click.option("--task", required=True, type=str, help="Downstream task description")
@click.option(
    "--constraint", multiple=True, type=str,
    help="Environment constraint (key=value, repeatable)",
)
def query(task: str, constraint: tuple[str, ...]) -> None:
    """Run a feasibility query against the knowledge graph (placeholder)."""
    click.echo("Feasibility query engine available after Plan 03 execution.")
