"""Unit tests for Neo4j graph client.

Tests use mocked neo4j driver -- no real Neo4j required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from agentsim.knowledge_graph.models import (
    AchievesBoundEdge,
    AlgorithmNode,
    BelongsToEdge,
    CompatibleWithEdge,
    ConfidenceQualifier,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorFamily,
    SensorNode,
    SharesPhysicsEdge,
    TemporalProps,
)
from agentsim.knowledge_graph.client import (
    GraphClient,
    _record_to_sensor,
    _sensor_to_props,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_sensor(name: str = "TestSPAD", family: SensorFamily = SensorFamily.SPAD) -> SensorNode:
    """Create a minimal SensorNode for testing."""
    return SensorNode(
        name=name,
        family=family,
        description="Test sensor",
        geometric=GeometricProps(fov=120.0),
        temporal=TemporalProps(temporal_resolution=50.0),
        radiometric=RadiometricProps(quantum_efficiency=0.3),
        operational=OperationalProps(cost_min_usd=100.0, cost_max_usd=500.0),
        family_specs={
            "dead_time_ns": 20.0,
            "afterpulsing_probability": 0.01,
            "crosstalk_probability": 0.02,
            "fill_factor": 0.5,
            "pde": 0.3,
        },
    )


# ---------------------------------------------------------------------------
# Flat property mapping tests
# ---------------------------------------------------------------------------


class TestSensorToProps:
    """Tests for _sensor_to_props() flat property mapping."""

    def test_top_level_fields(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert props["name"] == "TestSPAD"
        assert props["family"] == "spad"
        assert props["description"] == "Test sensor"

    def test_geometric_prefix(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert "geo_fov" in props
        assert props["geo_fov"] == 120.0

    def test_temporal_prefix(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert "temp_temporal_resolution" in props
        assert props["temp_temporal_resolution"] == 50.0

    def test_radiometric_prefix(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert "rad_quantum_efficiency" in props
        assert props["rad_quantum_efficiency"] == 0.3

    def test_operational_prefix(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert "op_cost_min_usd" in props
        assert props["op_cost_min_usd"] == 100.0

    def test_family_specs_prefix(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        assert "fs_dead_time_ns" in props
        assert props["fs_dead_time_ns"] == 20.0

    def test_none_values_filtered(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        for value in props.values():
            assert value is not None

    def test_no_operational_when_none(self) -> None:
        sensor = SensorNode(
            name="Bare",
            family=SensorFamily.SPAD,
            geometric=GeometricProps(fov=90.0),
            temporal=TemporalProps(),
            radiometric=RadiometricProps(),
            operational=None,
            family_specs={
                "dead_time_ns": 20.0,
                "afterpulsing_probability": 0.01,
                "crosstalk_probability": 0.02,
                "fill_factor": 0.5,
                "pde": 0.3,
            },
        )
        props = _sensor_to_props(sensor)
        op_keys = [k for k in props if k.startswith("op_")]
        assert len(op_keys) == 0


class TestRecordToSensor:
    """Tests for _record_to_sensor() reconstruction from flat dict."""

    def test_roundtrip(self) -> None:
        sensor = _make_sensor()
        props = _sensor_to_props(sensor)
        reconstructed = _record_to_sensor(props)
        assert reconstructed.name == sensor.name
        assert reconstructed.family == sensor.family
        assert reconstructed.geometric.fov == sensor.geometric.fov

    def test_family_enum_from_string(self) -> None:
        props = _sensor_to_props(_make_sensor())
        reconstructed = _record_to_sensor(props)
        assert isinstance(reconstructed.family, SensorFamily)
        assert reconstructed.family == SensorFamily.SPAD

    def test_operational_none_when_no_op_keys(self) -> None:
        sensor = SensorNode(
            name="NoOp",
            family=SensorFamily.SPAD,
            geometric=GeometricProps(fov=90.0),
            temporal=TemporalProps(),
            radiometric=RadiometricProps(),
            operational=None,
            family_specs={
                "dead_time_ns": 20.0,
                "afterpulsing_probability": 0.01,
                "crosstalk_probability": 0.02,
                "fill_factor": 0.5,
                "pde": 0.3,
            },
        )
        props = _sensor_to_props(sensor)
        reconstructed = _record_to_sensor(props)
        assert reconstructed.operational is None


# ---------------------------------------------------------------------------
# GraphClient tests
# ---------------------------------------------------------------------------


class TestGraphClientInit:
    """Tests for GraphClient initialization and context manager."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_creates_driver(self, mock_gdb: MagicMock) -> None:
        client = GraphClient()
        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "agentsim"),
            max_connection_pool_size=50,
            connection_acquisition_timeout=10.0,
        )

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_context_manager_calls_close(self, mock_gdb: MagicMock) -> None:
        with GraphClient() as client:
            pass
        mock_gdb.driver.return_value.close.assert_called_once()

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_close(self, mock_gdb: MagicMock) -> None:
        client = GraphClient()
        client.close()
        mock_gdb.driver.return_value.close.assert_called_once()


class TestEnsureSchema:
    """Tests for ensure_schema()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_runs_all_constraints_and_indexes(self, mock_gdb: MagicMock) -> None:
        from agentsim.knowledge_graph.schema import SCHEMA_CONSTRAINTS, SCHEMA_INDEXES

        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        client.ensure_schema()

        total_stmts = len(SCHEMA_CONSTRAINTS) + len(SCHEMA_INDEXES)
        assert mock_session.run.call_count == total_stmts


class TestCreateSensor:
    """Tests for create_sensor()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_execute_write(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        sensor = _make_sensor()
        result = client.create_sensor(sensor)

        mock_session.execute_write.assert_called_once()
        assert result == sensor

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_merge_not_create(self, mock_gdb: MagicMock) -> None:
        """Verify the tx function uses MERGE."""
        mock_tx = MagicMock()
        props = _sensor_to_props(_make_sensor())
        GraphClient._create_sensor_tx(mock_tx, props)
        cypher = mock_tx.run.call_args[0][0]
        assert "MERGE" in cypher
        assert "CREATE" not in cypher.replace("MERGE", "")

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_parameterized_queries(self, mock_gdb: MagicMock) -> None:
        mock_tx = MagicMock()
        props = _sensor_to_props(_make_sensor())
        GraphClient._create_sensor_tx(mock_tx, props)
        cypher = mock_tx.run.call_args[0][0]
        assert "$name" in cypher
        assert "$props" in cypher


class TestCreateSensorFamily:
    """Tests for create_sensor_family()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_execute_write(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        client.create_sensor_family("spad", display_name="SPAD Array")
        mock_session.execute_write.assert_called_once()


class TestCreateAlgorithm:
    """Tests for create_algorithm()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_execute_write(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        algo = AlgorithmNode(name="backprojection", paradigm="analytic")
        client = GraphClient()
        result = client.create_algorithm(algo)
        mock_session.execute_write.assert_called_once()
        assert result == algo


class TestCreateRelationship:
    """Tests for create_relationship() dispatch."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_shares_physics_edge(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        edge = SharesPhysicsEdge(
            source_family=SensorFamily.SPAD,
            target_family=SensorFamily.CW_TOF,
            shared_principle="photon timing",
        )
        client = GraphClient()
        client.create_relationship(edge)
        mock_session.execute_write.assert_called_once()

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_belongs_to_edge(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        edge = BelongsToEdge(sensor_name="TestSPAD", family=SensorFamily.SPAD)
        client = GraphClient()
        client.create_relationship(edge)
        mock_session.execute_write.assert_called_once()

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_compatible_with_edge(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        edge = CompatibleWithEdge(
            sensor_name="TestSPAD", algorithm_name="backprojection"
        )
        client = GraphClient()
        client.create_relationship(edge)
        mock_session.execute_write.assert_called_once()

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_achieves_bound_edge(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        edge = AchievesBoundEdge(
            sensor_name="TestSPAD",
            task_name="localization",
            bound_value=0.01,
            bound_unit="meter",
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        client = GraphClient()
        client.create_relationship(edge)
        mock_session.execute_write.assert_called_once()


class TestGetSensors:
    """Tests for get_sensors()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_execute_read(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.execute_read.return_value = []
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        result = client.get_sensors()
        mock_session.execute_read.assert_called_once()
        assert result == ()

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_returns_tuple(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.execute_read.return_value = []
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        result = client.get_sensors()
        assert isinstance(result, tuple)


class TestGetSensorByName:
    """Tests for get_sensor_by_name()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_returns_none_when_not_found(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.execute_read.return_value = None
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        result = client.get_sensor_by_name("nonexistent")
        assert result is None


class TestClearAll:
    """Tests for clear_all()."""

    @patch("agentsim.knowledge_graph.client.GraphDatabase")
    def test_uses_execute_write(self, mock_gdb: MagicMock) -> None:
        mock_session = MagicMock()
        mock_gdb.driver.return_value.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_gdb.driver.return_value.session.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = GraphClient()
        client.clear_all()
        mock_session.execute_write.assert_called_once()
