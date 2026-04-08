"""Tests for Neo4j graph schema constants."""

from __future__ import annotations

from agentsim.knowledge_graph.schema import (
    ALL_NODE_LABELS,
    ALL_REL_TYPES,
    SCHEMA_CONSTRAINTS,
    SCHEMA_INDEXES,
    NodeLabel,
    RelType,
)


class TestNodeLabels:
    """Tests for NodeLabel constants."""

    def test_node_labels(self) -> None:
        assert NodeLabel.SENSOR == "Sensor"
        assert NodeLabel.SENSOR_FAMILY == "SensorFamily"
        assert NodeLabel.ALGORITHM == "Algorithm"
        assert NodeLabel.TASK == "Task"
        assert NodeLabel.ENVIRONMENT == "Environment"


class TestRelTypes:
    """Tests for RelType constants."""

    def test_rel_types(self) -> None:
        assert RelType.BELONGS_TO == "BELONGS_TO"
        assert RelType.COMPATIBLE_WITH == "COMPATIBLE_WITH"
        assert RelType.SHARES_PHYSICS == "SHARES_PHYSICS"
        assert RelType.ACHIEVES_BOUND == "ACHIEVES_BOUND"


class TestAllNodeLabels:
    """Tests for ALL_NODE_LABELS frozenset."""

    def test_all_node_labels_completeness(self) -> None:
        expected = frozenset({"Sensor", "SensorFamily", "Algorithm", "Task", "Environment"})
        assert ALL_NODE_LABELS == expected

    def test_all_node_labels_count(self) -> None:
        assert len(ALL_NODE_LABELS) == 5


class TestAllRelTypes:
    """Tests for ALL_REL_TYPES frozenset."""

    def test_all_rel_types_completeness(self) -> None:
        expected = frozenset({
            "BELONGS_TO", "COMPATIBLE_WITH", "SHARES_PHYSICS", "ACHIEVES_BOUND",
        })
        assert ALL_REL_TYPES == expected

    def test_all_rel_types_count(self) -> None:
        assert len(ALL_REL_TYPES) == 4


class TestSchemaConstraints:
    """Tests for SCHEMA_CONSTRAINTS Cypher statements."""

    def test_schema_constraints_are_tuple(self) -> None:
        assert isinstance(SCHEMA_CONSTRAINTS, tuple)

    def test_schema_constraints_all_start_with_create(self) -> None:
        for constraint in SCHEMA_CONSTRAINTS:
            assert constraint.startswith("CREATE CONSTRAINT"), (
                f"Constraint does not start with 'CREATE CONSTRAINT': {constraint}"
            )

    def test_schema_constraints_sensor_name_uniqueness(self) -> None:
        sensor_constraints = [c for c in SCHEMA_CONSTRAINTS if "Sensor" in c and "name" in c]
        assert len(sensor_constraints) >= 1, "Missing sensor name uniqueness constraint"

    def test_schema_constraints_count(self) -> None:
        assert len(SCHEMA_CONSTRAINTS) == 5


class TestSchemaIndexes:
    """Tests for SCHEMA_INDEXES Cypher statements."""

    def test_schema_indexes_are_tuple(self) -> None:
        assert isinstance(SCHEMA_INDEXES, tuple)

    def test_schema_indexes_all_start_with_create(self) -> None:
        for index in SCHEMA_INDEXES:
            assert index.startswith("CREATE INDEX"), (
                f"Index does not start with 'CREATE INDEX': {index}"
            )

    def test_schema_indexes_count(self) -> None:
        assert len(SCHEMA_INDEXES) == 1
