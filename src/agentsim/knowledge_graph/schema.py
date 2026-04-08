"""Neo4j graph schema constants for the computational imaging knowledge graph.

Defines node labels, relationship types, uniqueness constraints, and indexes
as Python constants. These are used by the graph client (Phase 9) to create
the database schema and by query builders to reference labels/types safely.
"""

from __future__ import annotations


class NodeLabel:
    """Neo4j node labels for the knowledge graph.

    Plain class with string constants (not enum) per D-07.
    Values match the exact Neo4j label strings used in Cypher queries.
    """

    SENSOR: str = "Sensor"
    SENSOR_FAMILY: str = "SensorFamily"
    ALGORITHM: str = "Algorithm"
    TASK: str = "Task"
    ENVIRONMENT: str = "Environment"


class RelType:
    """Neo4j relationship types for the knowledge graph.

    Plain class with string constants per D-06/D-07.
    Values match the exact Neo4j relationship type strings used in Cypher queries.
    """

    BELONGS_TO: str = "BELONGS_TO"
    COMPATIBLE_WITH: str = "COMPATIBLE_WITH"
    SHARES_PHYSICS: str = "SHARES_PHYSICS"
    ACHIEVES_BOUND: str = "ACHIEVES_BOUND"


ALL_NODE_LABELS: frozenset[str] = frozenset({
    NodeLabel.SENSOR,
    NodeLabel.SENSOR_FAMILY,
    NodeLabel.ALGORITHM,
    NodeLabel.TASK,
    NodeLabel.ENVIRONMENT,
})

ALL_REL_TYPES: frozenset[str] = frozenset({
    RelType.BELONGS_TO,
    RelType.COMPATIBLE_WITH,
    RelType.SHARES_PHYSICS,
    RelType.ACHIEVES_BOUND,
})

SCHEMA_CONSTRAINTS: tuple[str, ...] = (
    "CREATE CONSTRAINT sensor_name IF NOT EXISTS FOR (s:Sensor) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT algo_name IF NOT EXISTS FOR (a:Algorithm) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT task_name IF NOT EXISTS FOR (t:Task) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT family_name IF NOT EXISTS FOR (f:SensorFamily) REQUIRE f.name IS UNIQUE",
    "CREATE CONSTRAINT env_name IF NOT EXISTS FOR (e:Environment) REQUIRE e.name IS UNIQUE",
)

SCHEMA_INDEXES: tuple[str, ...] = (
    "CREATE INDEX sensor_family_idx IF NOT EXISTS FOR (s:Sensor) ON (s.family)",
)
