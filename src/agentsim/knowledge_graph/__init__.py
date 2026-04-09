"""Knowledge graph data models and schema for computational imaging sensors."""

from agentsim.knowledge_graph.models import (
    AchievesBoundEdge,
    AlgorithmNode,
    BelongsToEdge,
    CompatibleWithEdge,
    ConfidenceQualifier,
    ConstraintSatisfaction,
    EnvironmentNode,
    FAMILY_SCHEMAS,
    FeasibilityResult,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorConfig,
    SensorFamily,
    SensorNode,
    SharesPhysicsEdge,
    TaskNode,
    TemporalProps,
)
from agentsim.knowledge_graph.schema import (
    ALL_NODE_LABELS,
    ALL_REL_TYPES,
    NodeLabel,
    RelType,
    SCHEMA_CONSTRAINTS,
    SCHEMA_INDEXES,
)
from agentsim.knowledge_graph.loader import (
    load_family_ranges,
    load_sensors,
)
from agentsim.knowledge_graph.ranges import (
    ParameterRange,
    SensorFamilyRanges,
)
from agentsim.knowledge_graph.units import (
    CANONICAL_UNITS,
    validate_unit,
)
from agentsim.knowledge_graph.crb import (
    ANALYTICAL_FAMILIES,
    CONDITION_THRESHOLD,
    CRBBound,
    CRBResult,
    NUMERICAL_FAMILIES,
    SUPPORTED_FAMILIES,
    SensitivityEntry,
    SensitivityResult,
    compute_analytical_crb,
    compute_crb,
    compute_numerical_crb,
    compute_sensitivity,
    jax_available,
)

# Neo4j-dependent modules -- lazy imports to avoid crashes when neo4j
# driver is not installed or has binary incompatibilities.
try:
    from agentsim.knowledge_graph.client import GraphClient as GraphClient
    from agentsim.knowledge_graph.degradation import (
        graceful_graph_op as graceful_graph_op,
        is_graph_available as is_graph_available,
    )
    from agentsim.knowledge_graph.docker import (
        DockerStatus as DockerStatus,
        start_neo4j as start_neo4j,
        stop_neo4j as stop_neo4j,
        neo4j_status as neo4j_status,
        wait_for_healthy as wait_for_healthy,
    )
    from agentsim.knowledge_graph.seeder import (
        seed_graph as seed_graph,
        SeedResult as SeedResult,
    )
except ImportError:
    pass
