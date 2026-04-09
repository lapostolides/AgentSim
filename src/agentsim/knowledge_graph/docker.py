"""Docker lifecycle management for the Neo4j knowledge graph container.

Provides start, stop, status, and health-check functions using subprocess
calls to the Docker CLI. No docker-py dependency required.
"""

from __future__ import annotations

import socket
import subprocess
import time

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEO4J_CONTAINER: str = "agentsim-neo4j"
NEO4J_IMAGE: str = "neo4j:5-community"
NEO4J_VOLUME: str = "agentsim-neo4j-data"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DockerStatus(BaseModel, frozen=True):
    """Frozen status of the Neo4j Docker container."""

    is_running: bool
    container_id: str = ""
    bolt_port: int = 7687
    http_port: int = 7474
    health: str = "unknown"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DockerNotAvailableError(Exception):
    """Raised when the Docker CLI is not available."""


# ---------------------------------------------------------------------------
# Lifecycle functions
# ---------------------------------------------------------------------------


def start_neo4j(
    bolt_port: int = 7687,
    http_port: int = 7474,
    password: str = "agentsim",
) -> DockerStatus:
    """Start a Neo4j Docker container, returning its status.

    Checks for an existing container first. Removes stale containers
    before creating a new one. Uses a persistent Docker volume for data.

    Args:
        bolt_port: Host port mapped to Neo4j Bolt protocol.
        http_port: Host port mapped to Neo4j HTTP browser.
        password: Neo4j authentication password (user is always 'neo4j').

    Returns:
        DockerStatus with container details.

    Raises:
        DockerNotAvailableError: If Docker CLI is not installed or accessible.
        subprocess.CalledProcessError: If container creation fails.
    """
    # Check Docker availability
    info_result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if info_result.returncode != 0:
        raise DockerNotAvailableError(
            "Docker not available. Ensure Docker is installed and your user "
            "has permission to run it."
        )

    # Check for existing container
    inspect_result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", NEO4J_CONTAINER],
        capture_output=True,
        text=True,
    )
    if inspect_result.returncode == 0 and "running" in inspect_result.stdout:
        logger.info("neo4j_already_running", container=NEO4J_CONTAINER)
        return DockerStatus(
            is_running=True,
            container_id=NEO4J_CONTAINER,
            bolt_port=bolt_port,
            http_port=http_port,
            health="running",
        )

    # Remove stale container (ignore errors if it doesn't exist)
    subprocess.run(
        ["docker", "rm", "-f", NEO4J_CONTAINER],
        capture_output=True,
    )

    # Start new container
    run_result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", NEO4J_CONTAINER,
            "-p", f"{bolt_port}:7687",
            "-p", f"{http_port}:7474",
            "-v", f"{NEO4J_VOLUME}:/data",
            "-e", f"NEO4J_AUTH=neo4j/{password}",
            "--restart", "unless-stopped",
            NEO4J_IMAGE,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    container_id = run_result.stdout.strip()
    logger.info("neo4j_started", container_id=container_id, bolt_port=bolt_port)
    return DockerStatus(
        is_running=True,
        container_id=container_id,
        bolt_port=bolt_port,
        http_port=http_port,
        health="starting",
    )


def stop_neo4j() -> DockerStatus:
    """Stop and remove the Neo4j Docker container.

    Handles the case where the container may not exist gracefully.

    Returns:
        DockerStatus with is_running=False.
    """
    try:
        subprocess.run(
            ["docker", "stop", NEO4J_CONTAINER],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        logger.debug("neo4j_stop_skipped", reason="container not running or not found")

    try:
        subprocess.run(
            ["docker", "rm", NEO4J_CONTAINER],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        logger.debug("neo4j_rm_skipped", reason="container not found")

    logger.info("neo4j_stopped", container=NEO4J_CONTAINER)
    return DockerStatus(is_running=False)


def neo4j_status() -> DockerStatus:
    """Query the current status of the Neo4j Docker container.

    Returns:
        DockerStatus reflecting the container state.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", NEO4J_CONTAINER],
            capture_output=True,
            text=True,
            check=True,
        )
        state = result.stdout.strip()
        is_running = state == "running"
        return DockerStatus(
            is_running=is_running,
            container_id=NEO4J_CONTAINER,
            health=state,
        )
    except subprocess.CalledProcessError:
        return DockerStatus(is_running=False)


def wait_for_healthy(
    bolt_port: int = 7687,
    timeout_s: float = 30.0,
    poll_interval_s: float = 1.0,
) -> DockerStatus:
    """Poll the Bolt port until Neo4j accepts connections.

    Args:
        bolt_port: Port to check for Bolt protocol readiness.
        timeout_s: Maximum seconds to wait before raising TimeoutError.
        poll_interval_s: Seconds between connection attempts.

    Returns:
        DockerStatus with health="healthy" when ready.

    Raises:
        TimeoutError: If Neo4j does not become ready within timeout_s.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", bolt_port), timeout=2.0):
                logger.info("neo4j_healthy", bolt_port=bolt_port)
                return DockerStatus(
                    is_running=True,
                    container_id=NEO4J_CONTAINER,
                    bolt_port=bolt_port,
                    health="healthy",
                )
        except (ConnectionRefusedError, OSError):
            time.sleep(poll_interval_s)
    raise TimeoutError(f"Neo4j not healthy after {timeout_s}s on port {bolt_port}")
