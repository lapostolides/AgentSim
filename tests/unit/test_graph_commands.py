"""Unit tests for CLI graph commands.

Tests use Click's CliRunner and mock all docker/client/seeder functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from agentsim.cli.graph_commands import graph
from agentsim.knowledge_graph.docker import DockerNotAvailableError, DockerStatus
from agentsim.knowledge_graph.seeder import SeedResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# graph --help
# ---------------------------------------------------------------------------


class TestGraphHelp:
    """Test the graph command group help output."""

    def test_help_lists_subcommands(self) -> None:
        result = _runner().invoke(graph, ["--help"])
        assert result.exit_code == 0
        for cmd in ("start", "stop", "status", "seed", "query"):
            assert cmd in result.output


# ---------------------------------------------------------------------------
# graph start
# ---------------------------------------------------------------------------


class TestGraphStart:
    @patch("agentsim.cli.graph_commands.wait_for_healthy")
    @patch("agentsim.cli.graph_commands.start_neo4j")
    def test_start_calls_start_and_wait(self, mock_start, mock_wait) -> None:
        mock_start.return_value = DockerStatus(is_running=True, container_id="abc")
        mock_wait.return_value = DockerStatus(
            is_running=True, container_id="abc", health="healthy"
        )
        result = _runner().invoke(graph, ["start"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_wait.assert_called_once()
        assert "bolt://localhost:7687" in result.output

    @patch("agentsim.cli.graph_commands.start_neo4j")
    def test_start_docker_not_available(self, mock_start) -> None:
        mock_start.side_effect = DockerNotAvailableError("Docker not found")
        result = _runner().invoke(graph, ["start"])
        assert result.exit_code != 0
        assert "Docker" in result.output or "docker" in result.output.lower()

    @patch("agentsim.cli.graph_commands.wait_for_healthy")
    @patch("agentsim.cli.graph_commands.start_neo4j")
    def test_start_timeout_warning(self, mock_start, mock_wait) -> None:
        mock_start.return_value = DockerStatus(is_running=True)
        mock_wait.side_effect = TimeoutError("not healthy")
        result = _runner().invoke(graph, ["start"])
        # Should not crash, just warn
        assert result.exit_code == 0
        assert "not yet healthy" in result.output.lower() or "status" in result.output.lower()


# ---------------------------------------------------------------------------
# graph stop
# ---------------------------------------------------------------------------


class TestGraphStop:
    @patch("agentsim.cli.graph_commands.stop_neo4j")
    def test_stop_calls_stop(self, mock_stop) -> None:
        mock_stop.return_value = DockerStatus(is_running=False)
        result = _runner().invoke(graph, ["stop"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()
        assert "stopped" in result.output.lower()

    @patch("agentsim.cli.graph_commands.stop_neo4j")
    def test_stop_handles_missing_container(self, mock_stop) -> None:
        mock_stop.return_value = DockerStatus(is_running=False)
        result = _runner().invoke(graph, ["stop"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# graph status
# ---------------------------------------------------------------------------


class TestGraphStatus:
    @patch("agentsim.cli.graph_commands.is_graph_available")
    @patch("agentsim.cli.graph_commands.neo4j_status")
    def test_status_shows_running(self, mock_status, mock_avail) -> None:
        mock_status.return_value = DockerStatus(
            is_running=True, container_id="abc", bolt_port=7687, http_port=7474, health="running"
        )
        mock_avail.return_value = True
        result = _runner().invoke(graph, ["status"])
        assert result.exit_code == 0
        assert "running" in result.output.lower()

    @patch("agentsim.cli.graph_commands.is_graph_available")
    @patch("agentsim.cli.graph_commands.neo4j_status")
    def test_status_shows_stopped(self, mock_status, mock_avail) -> None:
        mock_status.return_value = DockerStatus(is_running=False)
        mock_avail.return_value = False
        result = _runner().invoke(graph, ["status"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# graph seed
# ---------------------------------------------------------------------------


class TestGraphSeed:
    @patch("agentsim.cli.graph_commands.seed_graph")
    @patch("agentsim.cli.graph_commands.GraphClient")
    def test_seed_calls_seed_graph(self, mock_client_cls, mock_seed) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_seed.return_value = SeedResult(
            sensors_created=14, families_created=7, edges_created=20, errors=()
        )
        result = _runner().invoke(graph, ["seed"])
        assert result.exit_code == 0
        mock_seed.assert_called_once()
        # force_clean should be False by default
        _, kwargs = mock_seed.call_args
        assert kwargs.get("force_clean") is False or (
            len(mock_seed.call_args[0]) > 1 and mock_seed.call_args[0][1] is False
        ) or "force_clean" not in kwargs
        assert "14" in result.output  # sensors count

    @patch("agentsim.cli.graph_commands.seed_graph")
    @patch("agentsim.cli.graph_commands.GraphClient")
    def test_seed_clean_flag(self, mock_client_cls, mock_seed) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_seed.return_value = SeedResult(
            sensors_created=0, families_created=0, edges_created=0, errors=()
        )
        result = _runner().invoke(graph, ["seed", "--clean"])
        assert result.exit_code == 0
        _, kwargs = mock_seed.call_args
        assert kwargs.get("force_clean") is True

    @patch("agentsim.cli.graph_commands.GraphClient")
    def test_seed_connection_error(self, mock_client_cls) -> None:
        mock_client_cls.side_effect = ConnectionRefusedError("Cannot connect")
        result = _runner().invoke(graph, ["seed"])
        assert result.exit_code != 0 or "connect" in result.output.lower()

    @patch("agentsim.cli.graph_commands.seed_graph")
    @patch("agentsim.cli.graph_commands.GraphClient")
    def test_seed_prints_errors(self, mock_client_cls, mock_seed) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_seed.return_value = SeedResult(
            sensors_created=1, families_created=1, edges_created=0,
            errors=("Failed sensor X",)
        )
        result = _runner().invoke(graph, ["seed"])
        assert "Failed sensor X" in result.output


# ---------------------------------------------------------------------------
# graph query (placeholder)
# ---------------------------------------------------------------------------


class TestGraphQuery:
    def test_query_placeholder_message(self) -> None:
        result = _runner().invoke(graph, ["query", "--task", "localization"])
        assert result.exit_code == 0
        assert "Plan 03" in result.output or "plan 03" in result.output.lower()
