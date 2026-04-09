"""Unit tests for the YAML-to-Neo4j seed pipeline.

Tests use a mock GraphClient to verify seed_graph orchestration logic
without requiring a running Neo4j instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from agentsim.knowledge_graph.models import (
    AlgorithmNode,
    BelongsToEdge,
    SensorFamily,
    SharesPhysicsEdge,
)
from agentsim.knowledge_graph.seeder import (
    SHARED_PHYSICS_EDGES,
    SeedResult,
    seed_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    """Create a mock GraphClient with all required methods."""
    client = MagicMock()
    client.ensure_schema = MagicMock()
    client.clear_all = MagicMock()
    client.create_sensor = MagicMock()
    client.create_sensor_family = MagicMock()
    client.create_relationship = MagicMock()
    client.create_algorithm = MagicMock()
    return client


# ---------------------------------------------------------------------------
# SeedResult model tests
# ---------------------------------------------------------------------------


class TestSeedResult:
    """Tests for the frozen SeedResult model."""

    def test_seed_result_frozen(self) -> None:
        result = SeedResult(sensors_created=5, families_created=3, edges_created=10, errors=())
        with pytest.raises(Exception):
            result.sensors_created = 99  # type: ignore[misc]

    def test_seed_result_defaults(self) -> None:
        result = SeedResult(sensors_created=0, families_created=0, edges_created=0, errors=())
        assert result.sensors_created == 0
        assert result.errors == ()


# ---------------------------------------------------------------------------
# SHARED_PHYSICS_EDGES constant tests
# ---------------------------------------------------------------------------


class TestSharedPhysicsEdges:
    """Tests for the SHARED_PHYSICS_EDGES constant (D-09 deep domain research)."""

    def test_is_tuple_of_edges(self) -> None:
        assert isinstance(SHARED_PHYSICS_EDGES, tuple)
        for edge in SHARED_PHYSICS_EDGES:
            assert isinstance(edge, SharesPhysicsEdge)

    def test_minimum_eight_edges(self) -> None:
        """Plan specifies at least 8 shared-physics pairs."""
        assert len(SHARED_PHYSICS_EDGES) >= 8

    def test_all_have_principle_and_note(self) -> None:
        for edge in SHARED_PHYSICS_EDGES:
            assert edge.shared_principle, f"Edge {edge} missing shared_principle"
            assert edge.coupling_note, f"Edge {edge} missing coupling_note"

    def test_known_pairs_present(self) -> None:
        """Verify specific domain pairs from D-09 are present."""
        pairs = {(e.source_family, e.target_family) for e in SHARED_PHYSICS_EDGES}
        # SPAD <-> CW_TOF
        assert (SensorFamily.SPAD, SensorFamily.CW_TOF) in pairs or \
               (SensorFamily.CW_TOF, SensorFamily.SPAD) in pairs
        # LIDAR_MECHANICAL <-> LIDAR_SOLID_STATE
        assert (SensorFamily.LIDAR_MECHANICAL, SensorFamily.LIDAR_SOLID_STATE) in pairs or \
               (SensorFamily.LIDAR_SOLID_STATE, SensorFamily.LIDAR_MECHANICAL) in pairs
        # CODED_APERTURE <-> LENSLESS
        assert (SensorFamily.CODED_APERTURE, SensorFamily.LENSLESS) in pairs or \
               (SensorFamily.LENSLESS, SensorFamily.CODED_APERTURE) in pairs

    def test_no_self_edges(self) -> None:
        for edge in SHARED_PHYSICS_EDGES:
            assert edge.source_family != edge.target_family, (
                f"Self-edge found: {edge.source_family}"
            )


# ---------------------------------------------------------------------------
# seed_graph orchestration tests
# ---------------------------------------------------------------------------


class TestSeedGraph:
    """Tests for seed_graph function orchestration."""

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_ensure_schema_called_before_creates(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """ensure_schema() MUST be called before any create calls (Pitfall 1)."""
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        call_order: list[str] = []
        client.ensure_schema.side_effect = lambda: call_order.append("ensure_schema")
        client.create_sensor.side_effect = lambda s: call_order.append("create_sensor")
        client.create_sensor_family.side_effect = (
            lambda **kw: call_order.append("create_sensor_family")
        )
        client.create_relationship.side_effect = (
            lambda e: call_order.append("create_relationship")
        )
        client.create_algorithm.side_effect = lambda a: call_order.append("create_algorithm")

        seed_graph(client)

        assert call_order[0] == "ensure_schema", (
            "ensure_schema must be called first"
        )

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_load_sensors_called(self, mock_load_sensors, mock_load_ranges) -> None:
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()
        seed_graph(client)
        mock_load_sensors.assert_called_once()

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_load_family_ranges_called(self, mock_load_sensors, mock_load_ranges) -> None:
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()
        seed_graph(client)
        mock_load_ranges.assert_called_once()

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_create_sensor_called_per_sensor(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """create_sensor called once per loaded sensor."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorNode,
            TemporalProps,
        )

        sensors = (
            SensorNode(
                name="test_spad",
                family=SensorFamily.SPAD,
                geometric=GeometricProps(fov=90.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "dead_time_ns": 20.0,
                    "afterpulsing_probability": 0.01,
                    "crosstalk_probability": 0.02,
                    "fill_factor": 0.5,
                    "pde": 0.3,
                },
            ),
        )
        mock_load_sensors.return_value = sensors
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        result = seed_graph(client)

        assert client.create_sensor.call_count == 1
        assert result.sensors_created == 1

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_create_sensor_family_per_unique_family(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """create_sensor_family called once per unique family from sensors."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorNode,
            TemporalProps,
        )

        sensors = (
            SensorNode(
                name="s1",
                family=SensorFamily.SPAD,
                geometric=GeometricProps(fov=90.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "dead_time_ns": 20.0,
                    "afterpulsing_probability": 0.01,
                    "crosstalk_probability": 0.02,
                    "fill_factor": 0.5,
                    "pde": 0.3,
                },
            ),
            SensorNode(
                name="s2",
                family=SensorFamily.SPAD,
                geometric=GeometricProps(fov=90.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "dead_time_ns": 20.0,
                    "afterpulsing_probability": 0.01,
                    "crosstalk_probability": 0.02,
                    "fill_factor": 0.5,
                    "pde": 0.3,
                },
            ),
        )
        mock_load_sensors.return_value = sensors
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        result = seed_graph(client)

        # Two sensors in same family => one family node
        assert client.create_sensor_family.call_count == 1
        assert result.families_created == 1

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_belongs_to_edges_created(self, mock_load_sensors, mock_load_ranges) -> None:
        """A BELONGS_TO edge is created for each sensor."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorNode,
            TemporalProps,
        )

        sensors = (
            SensorNode(
                name="s1",
                family=SensorFamily.RGB,
                geometric=GeometricProps(fov=60.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "pixel_pitch_um": 3.0,
                    "well_depth_electrons": 10000.0,
                    "read_noise_electrons": 2.0,
                },
            ),
        )
        mock_load_sensors.return_value = sensors
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        seed_graph(client)

        # Check that create_relationship was called with a BelongsToEdge
        belongs_to_calls = [
            c for c in client.create_relationship.call_args_list
            if isinstance(c[0][0], BelongsToEdge)
        ]
        assert len(belongs_to_calls) == 1
        edge = belongs_to_calls[0][0][0]
        assert edge.sensor_name == "s1"
        assert edge.family == SensorFamily.RGB

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_shares_physics_edges_created(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """All SHARED_PHYSICS_EDGES are created via create_relationship."""
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        seed_graph(client)

        shares_calls = [
            c for c in client.create_relationship.call_args_list
            if isinstance(c[0][0], SharesPhysicsEdge)
        ]
        assert len(shares_calls) == len(SHARED_PHYSICS_EDGES)

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_individual_sensor_error_does_not_abort(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """An error on one sensor should not abort the entire seed."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorNode,
            TemporalProps,
        )

        sensors = (
            SensorNode(
                name="good",
                family=SensorFamily.RGB,
                geometric=GeometricProps(fov=60.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "pixel_pitch_um": 3.0,
                    "well_depth_electrons": 10000.0,
                    "read_noise_electrons": 2.0,
                },
            ),
            SensorNode(
                name="bad",
                family=SensorFamily.RGB,
                geometric=GeometricProps(fov=60.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "pixel_pitch_um": 3.0,
                    "well_depth_electrons": 10000.0,
                    "read_noise_electrons": 2.0,
                },
            ),
        )
        mock_load_sensors.return_value = sensors
        mock_load_ranges.return_value = {}
        client = _make_mock_client()
        # Second create_sensor raises
        client.create_sensor.side_effect = [None, Exception("Neo4j error")]

        result = seed_graph(client)

        assert result.sensors_created == 1
        assert len(result.errors) == 1
        assert "bad" in result.errors[0]

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_clear_all_not_called_by_default(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        seed_graph(client, force_clean=False)

        client.clear_all.assert_not_called()

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_clear_all_called_when_force_clean(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        seed_graph(client, force_clean=True)

        client.clear_all.assert_called_once()

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_generic_algorithm_placeholder_created(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        mock_load_sensors.return_value = ()
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        seed_graph(client)

        client.create_algorithm.assert_called_once()
        algo = client.create_algorithm.call_args[0][0]
        assert isinstance(algo, AlgorithmNode)
        assert algo.name == "generic"

    @patch("agentsim.knowledge_graph.seeder.load_family_ranges")
    @patch("agentsim.knowledge_graph.seeder.load_sensors")
    def test_seed_result_counts_accurate(
        self, mock_load_sensors, mock_load_ranges
    ) -> None:
        """SeedResult counts match actual operations."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorNode,
            TemporalProps,
        )

        sensors = (
            SensorNode(
                name="s1",
                family=SensorFamily.SPAD,
                geometric=GeometricProps(fov=90.0),
                temporal=TemporalProps(),
                radiometric=RadiometricProps(),
                family_specs={
                    "dead_time_ns": 20.0,
                    "afterpulsing_probability": 0.01,
                    "crosstalk_probability": 0.02,
                    "fill_factor": 0.5,
                    "pde": 0.3,
                },
            ),
        )
        mock_load_sensors.return_value = sensors
        mock_load_ranges.return_value = {}
        client = _make_mock_client()

        result = seed_graph(client)

        assert result.sensors_created == 1
        assert result.families_created == 1
        # edges = 1 BELONGS_TO + len(SHARED_PHYSICS_EDGES)
        assert result.edges_created == 1 + len(SHARED_PHYSICS_EDGES)
        assert result.errors == ()
