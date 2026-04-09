"""Unit tests for Neo4j Docker lifecycle management.

Tests use mocked subprocess calls -- no real Docker required.
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, call, patch

import pytest

from agentsim.knowledge_graph.docker import (
    DockerNotAvailableError,
    DockerStatus,
    NEO4J_CONTAINER,
    NEO4J_IMAGE,
    NEO4J_VOLUME,
    neo4j_status,
    start_neo4j,
    stop_neo4j,
    wait_for_healthy,
)


class TestDockerStatus:
    """DockerStatus frozen Pydantic model tests."""

    def test_defaults(self) -> None:
        status = DockerStatus(is_running=False)
        assert status.is_running is False
        assert status.container_id == ""
        assert status.bolt_port == 7687
        assert status.http_port == 7474
        assert status.health == "unknown"

    def test_frozen(self) -> None:
        status = DockerStatus(is_running=True, container_id="abc123")
        with pytest.raises(Exception):
            status.is_running = False  # type: ignore[misc]

    def test_custom_ports(self) -> None:
        status = DockerStatus(is_running=True, bolt_port=17687, http_port=17474)
        assert status.bolt_port == 17687
        assert status.http_port == 17474


class TestConstants:
    """Verify module-level constants."""

    def test_container_name(self) -> None:
        assert NEO4J_CONTAINER == "agentsim-neo4j"

    def test_image(self) -> None:
        assert NEO4J_IMAGE == "neo4j:5-community"

    def test_volume(self) -> None:
        assert NEO4J_VOLUME == "agentsim-neo4j-data"


class TestStartNeo4j:
    """Tests for start_neo4j()."""

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_docker_not_available(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        with pytest.raises(DockerNotAvailableError):
            start_neo4j()

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_already_running(self, mock_run: MagicMock) -> None:
        # docker info succeeds
        info_result = MagicMock(returncode=0)
        # docker inspect returns running
        inspect_result = MagicMock(returncode=0, stdout="running\n")
        mock_run.side_effect = [info_result, inspect_result]

        result = start_neo4j()
        assert result.is_running is True
        assert result.container_id == NEO4J_CONTAINER

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_start_new_container(self, mock_run: MagicMock) -> None:
        info_result = MagicMock(returncode=0)
        inspect_result = MagicMock(returncode=1)  # no existing container
        rm_result = MagicMock(returncode=0)
        run_result = MagicMock(returncode=0, stdout="abc123def\n")
        mock_run.side_effect = [info_result, inspect_result, rm_result, run_result]

        result = start_neo4j()
        assert result.is_running is True
        assert result.container_id == "abc123def"

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_uses_volume_mount(self, mock_run: MagicMock) -> None:
        info_result = MagicMock(returncode=0)
        inspect_result = MagicMock(returncode=1)
        rm_result = MagicMock(returncode=0)
        run_result = MagicMock(returncode=0, stdout="abc\n")
        mock_run.side_effect = [info_result, inspect_result, rm_result, run_result]

        start_neo4j()
        # The docker run call is the 4th call
        docker_run_call = mock_run.call_args_list[3]
        cmd_args = docker_run_call[0][0]
        assert "-v" in cmd_args
        vol_idx = cmd_args.index("-v")
        assert cmd_args[vol_idx + 1] == f"{NEO4J_VOLUME}:/data"

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_no_shell_true(self, mock_run: MagicMock) -> None:
        info_result = MagicMock(returncode=0)
        inspect_result = MagicMock(returncode=1)
        rm_result = MagicMock(returncode=0)
        run_result = MagicMock(returncode=0, stdout="abc\n")
        mock_run.side_effect = [info_result, inspect_result, rm_result, run_result]

        start_neo4j()
        for c in mock_run.call_args_list:
            assert c.kwargs.get("shell") is not True


class TestStopNeo4j:
    """Tests for stop_neo4j()."""

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_stop_returns_not_running(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        result = stop_neo4j()
        assert result.is_running is False

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_stop_calls_stop_and_rm(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        stop_neo4j()
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == ["docker", "stop", NEO4J_CONTAINER]
        assert calls[1][0][0] == ["docker", "rm", NEO4J_CONTAINER]


class TestNeo4jStatus:
    """Tests for neo4j_status()."""

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_running(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="running\n")
        result = neo4j_status()
        assert result.is_running is True

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_not_running(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="exited\n")
        result = neo4j_status()
        assert result.is_running is False

    @patch("agentsim.knowledge_graph.docker.subprocess.run")
    def test_no_container(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "docker")
        result = neo4j_status()
        assert result.is_running is False


class TestWaitForHealthy:
    """Tests for wait_for_healthy()."""

    @patch("agentsim.knowledge_graph.docker.socket.create_connection")
    def test_immediate_healthy(self, mock_conn: MagicMock) -> None:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = wait_for_healthy(bolt_port=7687, timeout_s=5.0)
        assert result.is_running is True
        assert result.health == "healthy"

    @patch("agentsim.knowledge_graph.docker.time.sleep")
    @patch("agentsim.knowledge_graph.docker.time.monotonic")
    @patch("agentsim.knowledge_graph.docker.socket.create_connection")
    def test_timeout_raises(
        self, mock_conn: MagicMock, mock_mono: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_conn.side_effect = ConnectionRefusedError("refused")
        # Time progresses past deadline
        mock_mono.side_effect = [0.0, 0.5, 1.5, 2.5, 3.5]
        with pytest.raises(TimeoutError, match="Neo4j not healthy"):
            wait_for_healthy(bolt_port=7687, timeout_s=3.0, poll_interval_s=1.0)
