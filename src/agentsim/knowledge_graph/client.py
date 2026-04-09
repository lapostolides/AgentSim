"""Neo4j graph client with managed transactions and flat property mapping.

Wraps the official neo4j Python driver with connection pooling, typed
CRUD operations returning frozen Pydantic models, and flat property
mapping with prefixed keys (geo_, temp_, rad_, op_, fs_).
"""

from __future__ import annotations

from typing import Any

import structlog

from agentsim.knowledge_graph.models import (
    AchievesBoundEdge,
    AlgorithmNode,
    BelongsToEdge,
    CompatibleWithEdge,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorFamily,
    SensorNode,
    SharesPhysicsEdge,
    TemporalProps,
)
from agentsim.knowledge_graph.schema import SCHEMA_CONSTRAINTS, SCHEMA_INDEXES

logger = structlog.get_logger()


def _get_graph_database() -> Any:  # noqa: ANN401
    """Lazily import neo4j.GraphDatabase to avoid import-time crashes.

    The neo4j driver optionally imports pandas which may trigger numpy
    binary incompatibility on some environments. Deferring the import
    allows the module to be loaded and tested with mocks.
    """
    from neo4j import GraphDatabase  # noqa: PLC0415

    return GraphDatabase


# Module-level reference that tests can patch.
# On first real use, _get_graph_database() provides the real class.
GraphDatabase: Any = None  # noqa: F811


# ---------------------------------------------------------------------------
# Flat property mapping helpers
# ---------------------------------------------------------------------------


def _sensor_to_props(sensor: SensorNode) -> dict[str, Any]:
    """Flatten a SensorNode into Neo4j-compatible flat properties.

    Uses prefixes: geo_, temp_, rad_, op_, fs_ for nested property groups.
    Filters out None values since Neo4j rejects None as a property value.

    Args:
        sensor: The sensor node to flatten.

    Returns:
        Dictionary of flat properties suitable for Neo4j SET.
    """
    props: dict[str, Any] = {
        "name": sensor.name,
        "family": sensor.family.value,
        "description": sensor.description,
    }

    # Geometric properties with geo_ prefix
    for k, v in sensor.geometric.model_dump().items():
        props[f"geo_{k}"] = v

    # Temporal properties with temp_ prefix
    for k, v in sensor.temporal.model_dump().items():
        props[f"temp_{k}"] = v

    # Radiometric properties with rad_ prefix
    for k, v in sensor.radiometric.model_dump().items():
        props[f"rad_{k}"] = v

    # Operational properties with op_ prefix (skip if None)
    if sensor.operational is not None:
        for k, v in sensor.operational.model_dump().items():
            props[f"op_{k}"] = v

    # Family-specific specs with fs_ prefix
    for k, v in sensor.family_specs.items():
        props[f"fs_{k}"] = v

    # Filter out None values -- Neo4j rejects None as property values
    return {k: v for k, v in props.items() if v is not None}


def _record_to_sensor(record: dict[str, Any]) -> SensorNode:
    """Reconstruct a SensorNode from flat Neo4j properties.

    Splits prefixed keys back into nested property group models.

    Args:
        record: Flat dictionary from a Neo4j node.

    Returns:
        Reconstructed frozen SensorNode.
    """
    geo_data = {k[4:]: v for k, v in record.items() if k.startswith("geo_")}
    temp_data = {k[5:]: v for k, v in record.items() if k.startswith("temp_")}
    rad_data = {k[4:]: v for k, v in record.items() if k.startswith("rad_")}
    op_data = {k[3:]: v for k, v in record.items() if k.startswith("op_")}
    fs_data = {k[3:]: v for k, v in record.items() if k.startswith("fs_")}

    return SensorNode(
        name=record["name"],
        family=SensorFamily(record["family"]),
        description=record.get("description", ""),
        geometric=GeometricProps(**geo_data),
        temporal=TemporalProps(**temp_data),
        radiometric=RadiometricProps(**rad_data),
        operational=OperationalProps(**op_data) if op_data else None,
        family_specs=fs_data,
    )


# ---------------------------------------------------------------------------
# GraphClient
# ---------------------------------------------------------------------------


class GraphClient:
    """Neo4j graph client with managed transactions and typed results.

    Uses the official neo4j Python driver with connection pooling and
    automatic retry via execute_read/execute_write managed transactions.

    Usage::

        with GraphClient() as client:
            client.ensure_schema()
            client.create_sensor(sensor_node)
            sensors = client.get_sensors(family=SensorFamily.SPAD)
    """

    def __init__(
        self,
        bolt_uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] = ("neo4j", "agentsim"),
    ) -> None:
        """Initialize the graph client with a neo4j driver.

        Args:
            bolt_uri: Bolt protocol URI for Neo4j.
            auth: Tuple of (username, password).
        """
        global GraphDatabase  # noqa: PLW0603
        if GraphDatabase is None:
            GraphDatabase = _get_graph_database()
        self._driver = GraphDatabase.driver(
            bolt_uri,
            auth=auth,
            max_connection_pool_size=50,
            connection_acquisition_timeout=10.0,
        )

    def close(self) -> None:
        """Close the underlying neo4j driver and release connections."""
        self._driver.close()

    def __enter__(self) -> GraphClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -----------------------------------------------------------------------
    # Schema management
    # -----------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create uniqueness constraints and indexes (idempotent).

        Runs all SCHEMA_CONSTRAINTS and SCHEMA_INDEXES statements.
        Safe to call multiple times due to IF NOT EXISTS clauses.
        """
        with self._driver.session() as session:
            for stmt in SCHEMA_CONSTRAINTS:
                session.run(stmt)
            for stmt in SCHEMA_INDEXES:
                session.run(stmt)
        logger.info("schema_ensured", constraints=len(SCHEMA_CONSTRAINTS),
                     indexes=len(SCHEMA_INDEXES))

    # -----------------------------------------------------------------------
    # Sensor CRUD
    # -----------------------------------------------------------------------

    def create_sensor(self, sensor: SensorNode) -> SensorNode:
        """Create or update a sensor node in the graph via MERGE.

        Args:
            sensor: Frozen SensorNode to persist.

        Returns:
            The input sensor (unchanged, frozen).
        """
        props = _sensor_to_props(sensor)
        with self._driver.session() as session:
            session.execute_write(self._create_sensor_tx, props)
        logger.debug("sensor_created", name=sensor.name)
        return sensor

    @staticmethod
    def _create_sensor_tx(tx: Any, props: dict[str, Any]) -> None:  # noqa: ANN401
        """Transaction function for MERGE sensor node."""
        tx.run(
            "MERGE (s:Sensor {name: $name}) SET s += $props",
            name=props["name"],
            props=props,
        )

    # -----------------------------------------------------------------------
    # SensorFamily CRUD
    # -----------------------------------------------------------------------

    def create_sensor_family(
        self,
        name: str,
        display_name: str = "",
        props: dict[str, Any] | None = None,
    ) -> None:
        """Create or update a SensorFamily node via MERGE.

        Args:
            name: Family identifier (e.g. "spad").
            display_name: Human-readable name (e.g. "SPAD Array").
            props: Optional additional properties (range data, etc.).
        """
        merged_props = {"name": name, "display_name": display_name}
        if props:
            merged_props.update(props)
        with self._driver.session() as session:
            session.execute_write(self._create_family_tx, merged_props)
        logger.debug("sensor_family_created", name=name)

    @staticmethod
    def _create_family_tx(tx: Any, props: dict[str, Any]) -> None:  # noqa: ANN401
        """Transaction function for MERGE sensor family node."""
        tx.run(
            "MERGE (f:SensorFamily {name: $name}) SET f += $props",
            name=props["name"],
            props=props,
        )

    # -----------------------------------------------------------------------
    # Algorithm CRUD
    # -----------------------------------------------------------------------

    def create_algorithm(self, algo: AlgorithmNode) -> AlgorithmNode:
        """Create or update an algorithm node via MERGE.

        Args:
            algo: Frozen AlgorithmNode to persist.

        Returns:
            The input algorithm (unchanged, frozen).
        """
        props = algo.model_dump()
        with self._driver.session() as session:
            session.execute_write(self._create_algorithm_tx, props)
        logger.debug("algorithm_created", name=algo.name)
        return algo

    @staticmethod
    def _create_algorithm_tx(tx: Any, props: dict[str, Any]) -> None:  # noqa: ANN401
        """Transaction function for MERGE algorithm node."""
        tx.run(
            "MERGE (a:Algorithm {name: $name}) SET a += $props",
            name=props["name"],
            props=props,
        )

    # -----------------------------------------------------------------------
    # Relationship CRUD
    # -----------------------------------------------------------------------

    def create_relationship(self, edge: Any) -> None:  # noqa: ANN401
        """Create a typed relationship via MERGE, dispatching on edge type.

        Args:
            edge: One of SharesPhysicsEdge, BelongsToEdge,
                  CompatibleWithEdge, or AchievesBoundEdge.

        Raises:
            TypeError: If edge type is not recognized.
        """
        with self._driver.session() as session:
            if isinstance(edge, SharesPhysicsEdge):
                session.execute_write(
                    self._create_shares_physics_tx,
                    edge.source_family.value,
                    edge.target_family.value,
                    edge.shared_principle,
                    edge.coupling_note,
                )
            elif isinstance(edge, BelongsToEdge):
                session.execute_write(
                    self._create_belongs_to_tx,
                    edge.sensor_name,
                    edge.family.value,
                )
            elif isinstance(edge, CompatibleWithEdge):
                session.execute_write(
                    self._create_compatible_with_tx,
                    edge.sensor_name,
                    edge.algorithm_name,
                    edge.paradigm,
                    edge.quality_level,
                )
            elif isinstance(edge, AchievesBoundEdge):
                session.execute_write(
                    self._create_achieves_bound_tx,
                    edge.sensor_name,
                    edge.task_name,
                    edge.bound_value,
                    edge.bound_unit,
                    edge.confidence.value,
                )
            else:
                raise TypeError(f"Unknown edge type: {type(edge).__name__}")

    @staticmethod
    def _create_shares_physics_tx(
        tx: Any,  # noqa: ANN401
        source: str,
        target: str,
        principle: str,
        note: str,
    ) -> None:
        tx.run(
            "MATCH (a:SensorFamily {name: $source}), (b:SensorFamily {name: $target}) "
            "MERGE (a)-[r:SHARES_PHYSICS {shared_principle: $principle}]->(b) "
            "SET r.coupling_note = $note",
            source=source,
            target=target,
            principle=principle,
            note=note,
        )

    @staticmethod
    def _create_belongs_to_tx(
        tx: Any, sensor_name: str, family_name: str  # noqa: ANN401
    ) -> None:
        tx.run(
            "MATCH (s:Sensor {name: $sensor_name}), "
            "(f:SensorFamily {name: $family_name}) "
            "MERGE (s)-[:BELONGS_TO]->(f)",
            sensor_name=sensor_name,
            family_name=family_name,
        )

    @staticmethod
    def _create_compatible_with_tx(
        tx: Any,  # noqa: ANN401
        sensor_name: str,
        algorithm_name: str,
        paradigm: str,
        quality_level: str,
    ) -> None:
        tx.run(
            "MATCH (s:Sensor {name: $sensor_name}), "
            "(a:Algorithm {name: $algorithm_name}) "
            "MERGE (s)-[r:COMPATIBLE_WITH]->(a) "
            "SET r.paradigm = $paradigm, r.quality_level = $quality_level",
            sensor_name=sensor_name,
            algorithm_name=algorithm_name,
            paradigm=paradigm,
            quality_level=quality_level,
        )

    @staticmethod
    def _create_achieves_bound_tx(
        tx: Any,  # noqa: ANN401
        sensor_name: str,
        task_name: str,
        bound_value: float,
        bound_unit: str,
        confidence: str,
    ) -> None:
        tx.run(
            "MATCH (s:Sensor {name: $sensor_name}), (t:Task {name: $task_name}) "
            "MERGE (s)-[r:ACHIEVES_BOUND]->(t) "
            "SET r.bound_value = $bound_value, r.bound_unit = $bound_unit, "
            "r.confidence = $confidence",
            sensor_name=sensor_name,
            task_name=task_name,
            bound_value=bound_value,
            bound_unit=bound_unit,
            confidence=confidence,
        )

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def get_sensors(self, family: SensorFamily | None = None) -> tuple[SensorNode, ...]:
        """Retrieve sensor nodes from the graph.

        Args:
            family: Optional filter by sensor family.

        Returns:
            Tuple of frozen SensorNode instances.
        """
        with self._driver.session() as session:
            records = session.execute_read(self._get_sensors_tx, family)
        if not records:
            return ()
        return tuple(records)

    @staticmethod
    def _get_sensors_tx(
        tx: Any, family: SensorFamily | None  # noqa: ANN401
    ) -> list[SensorNode]:
        if family is not None:
            result = tx.run(
                "MATCH (s:Sensor) WHERE s.family = $family RETURN s",
                family=family.value,
            )
        else:
            result = tx.run("MATCH (s:Sensor) RETURN s")
        return [_record_to_sensor(dict(record["s"])) for record in result]

    def get_sensor_by_name(self, name: str) -> SensorNode | None:
        """Retrieve a single sensor by name.

        Args:
            name: Exact sensor name to match.

        Returns:
            SensorNode if found, None otherwise.
        """
        with self._driver.session() as session:
            result = session.execute_read(self._get_sensor_by_name_tx, name)
        return result

    @staticmethod
    def _get_sensor_by_name_tx(tx: Any, name: str) -> SensorNode | None:  # noqa: ANN401
        result = tx.run(
            "MATCH (s:Sensor {name: $name}) RETURN s",
            name=name,
        )
        record = result.single()
        if record is None:
            return None
        return _record_to_sensor(dict(record["s"]))

    # -----------------------------------------------------------------------
    # Destructive operations
    # -----------------------------------------------------------------------

    def clear_all(self) -> None:
        """Delete all nodes and relationships from the graph."""
        with self._driver.session() as session:
            session.execute_write(self._clear_all_tx)
        logger.info("graph_cleared")

    @staticmethod
    def _clear_all_tx(tx: Any) -> None:  # noqa: ANN401
        tx.run("MATCH (n) DETACH DELETE n")
