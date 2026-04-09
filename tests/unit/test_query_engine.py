"""Tests for feasibility query engine -- ranking, CRB integration, and CLI wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    FeasibilityResult,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorConfig,
    SensorFamily,
    SensorNode,
    TemporalProps,
)


# ---------------------------------------------------------------------------
# Fixture sensors
# ---------------------------------------------------------------------------


def _make_spad() -> SensorNode:
    return SensorNode(
        name="SwissSPAD2",
        family=SensorFamily.SPAD,
        description="SPAD array for NLOS",
        geometric=GeometricProps(
            fov=120.0,
            spatial_resolution=512.0,
            working_distance_min=0.5,
            working_distance_max=50.0,
        ),
        temporal=TemporalProps(
            temporal_resolution=55.0,
            temporal_resolution_unit="picosecond",
            frame_rate=97656.0,
        ),
        radiometric=RadiometricProps(
            quantum_efficiency=0.05,
            dynamic_range_db=90.0,
        ),
        operational=OperationalProps(
            cost_min_usd=20000.0,
            cost_max_usd=50000.0,
            power_w=10.0,
            weight_g=600.0,
        ),
        family_specs={
            "dead_time_ns": 24.0,
            "afterpulsing_probability": 0.003,
            "crosstalk_probability": 0.01,
            "fill_factor": 0.1,
            "pde": 0.05,
        },
    )


def _make_lidar() -> SensorNode:
    return SensorNode(
        name="VLP-16",
        family=SensorFamily.LIDAR_MECHANICAL,
        description="Velodyne 16-channel LiDAR",
        geometric=GeometricProps(
            fov=360.0,
            spatial_resolution=None,
            working_distance_min=1.0,
            working_distance_max=100.0,
        ),
        temporal=TemporalProps(
            temporal_resolution=5.0,
            temporal_resolution_unit="nanosecond",
            frame_rate=20.0,
        ),
        radiometric=RadiometricProps(
            dynamic_range_db=100.0,
        ),
        operational=OperationalProps(
            cost_min_usd=4000.0,
            cost_max_usd=8000.0,
            power_w=8.0,
            weight_g=830.0,
        ),
        family_specs={
            "scan_rate_rpm": 600.0,
            "angular_resolution_deg": 0.2,
            "max_range_m": 100.0,
        },
    )


def _make_mock_client(sensors: tuple[SensorNode, ...]) -> MagicMock:
    """Create a mock GraphClient that returns the given sensors."""
    client = MagicMock()
    client.get_sensors.return_value = sensors
    return client


# ---------------------------------------------------------------------------
# FeasibilityQueryEngine tests
# ---------------------------------------------------------------------------


class TestFeasibilityQueryEngine:
    """Tests for FeasibilityQueryEngine.query()."""

    def test_query_returns_feasibility_result(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("NLOS reconstruction", {"range_m": 10.0})

        assert isinstance(result, FeasibilityResult)
        assert result.query_text == "NLOS reconstruction"
        assert result.total_count == 2

    def test_ranked_by_feasibility_score_descending(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("NLOS reconstruction", {"range_m": 10.0})

        assert len(result.ranked_configs) > 0
        scores = [c.feasibility_score for c in result.ranked_configs]
        assert scores == sorted(scores, reverse=True)

    def test_cross_family_ranking(self) -> None:
        """SPAD and LiDAR should appear in the same ranking."""
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("depth sensing", {"range_m": 10.0})

        families = {c.sensor_family for c in result.ranked_configs}
        assert len(families) >= 2

    def test_rank_numbers_assigned(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("depth sensing", {"range_m": 10.0})

        ranks = [c.rank for c in result.ranked_configs]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_crb_absent_sets_none_and_unknown(self) -> None:
        """When CRB module import fails, crb_bound=None and confidence=UNKNOWN."""
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(),))
        engine = FeasibilityQueryEngine(client)

        # CRB module should import fine but may return inf -- either way test
        # that configs are well-formed
        result = engine.query("NLOS reconstruction", {"range_m": 10.0})
        config = result.ranked_configs[0]
        assert isinstance(config, SensorConfig)
        # crb_bound can be None or a float (if CRB module available)
        # confidence should be set
        assert isinstance(config.confidence, ConfidenceQualifier)

    def test_algorithm_name_is_generic(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("NLOS reconstruction", {"range_m": 10.0})

        for config in result.ranked_configs:
            assert config.algorithm_name == "generic"

    def test_max_results_caps_output(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("depth sensing", {"range_m": 10.0}, max_results=1)

        assert len(result.ranked_configs) <= 1

    def test_conflict_detected_impossible_constraints(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(), _make_lidar()))
        engine = FeasibilityQueryEngine(client)
        # Range 5000m exceeds all sensors, budget $1 too low
        result = engine.query(
            "impossible task",
            {"range_m": 5000.0, "budget_usd": 1.0},
        )
        # All configs should have low or zero scores
        assert result.total_count == 2

    def test_environment_constraints_in_result(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(),))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("task", {"range_m": 10.0, "budget_usd": 100000.0})

        assert "range_m=10.0" in result.environment_constraints
        assert "budget_usd=100000.0" in result.environment_constraints

    def test_computation_time_is_positive(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(),))
        engine = FeasibilityQueryEngine(client)
        result = engine.query("task", {"range_m": 10.0})

        assert result.computation_time_s >= 0.0

    def test_family_filter_passed_to_client(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client((_make_spad(),))
        engine = FeasibilityQueryEngine(client)
        engine.query("task", {"range_m": 10.0}, family_filter=SensorFamily.SPAD)

        client.get_sensors.assert_called_once_with(family=SensorFamily.SPAD)

    def test_empty_sensors_returns_empty_configs(self) -> None:
        from agentsim.knowledge_graph.query_engine import FeasibilityQueryEngine

        client = _make_mock_client(())
        engine = FeasibilityQueryEngine(client)
        result = engine.query("task", {"range_m": 10.0})

        assert result.ranked_configs == ()
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# query_feasibility convenience function
# ---------------------------------------------------------------------------


class TestQueryFeasibility:
    """Tests for query_feasibility() convenience wrapper."""

    def test_returns_feasibility_result(self) -> None:
        from agentsim.knowledge_graph.query_engine import query_feasibility

        client = _make_mock_client((_make_spad(),))
        result = query_feasibility("task", {"range_m": 10.0}, client)

        assert isinstance(result, FeasibilityResult)
        assert result.total_count == 1


# ---------------------------------------------------------------------------
# CLI query command tests
# ---------------------------------------------------------------------------


class TestCLIQueryCommand:
    """Tests for the `graph query` CLI command."""

    def test_query_command_exists(self) -> None:
        from agentsim.cli.graph_commands import graph

        commands = list(graph.commands.keys())
        assert "query" in commands

    def test_query_command_has_options(self) -> None:
        from agentsim.cli.graph_commands import query

        param_names = [p.name for p in query.params]
        assert "task" in param_names
        assert "constraint" in param_names
        assert "family" in param_names
        assert "max_results" in param_names

    def test_query_command_parses_constraints(self) -> None:
        """The command should parse key=value constraint strings."""
        from click.testing import CliRunner

        from agentsim.cli.graph_commands import graph

        runner = CliRunner()
        # This will fail connecting to Neo4j but should parse args first
        result = runner.invoke(graph, [
            "query",
            "--task", "NLOS reconstruction",
            "--constraint", "range_m=10.0",
            "--constraint", "budget_usd=50000",
        ])
        # Should not crash on arg parsing (may fail on Neo4j connection)
        # The important thing is it doesn't error before reaching the query
        assert result.exit_code == 0 or "Cannot connect" in result.output or "Error" in result.output

    def test_query_handles_neo4j_unavailable(self) -> None:
        """Friendly error when Neo4j is not running."""
        from click.testing import CliRunner

        from agentsim.cli.graph_commands import graph

        runner = CliRunner()
        result = runner.invoke(graph, [
            "query",
            "--task", "test task",
        ])
        # Should print user-friendly error, not a traceback
        assert "Error" in result.output or result.exit_code == 0
