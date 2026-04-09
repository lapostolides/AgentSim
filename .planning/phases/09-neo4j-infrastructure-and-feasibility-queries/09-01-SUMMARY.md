---
phase: 09-neo4j-infrastructure-and-feasibility-queries
plan: 01
subsystem: infra
tags: [neo4j, docker, graph-client, degradation, pydantic]

# Dependency graph
requires:
  - phase: 06-knowledge-graph-pydantic-models-and-schema
    provides: SensorNode, schema constants (SCHEMA_CONSTRAINTS, SCHEMA_INDEXES), NodeLabel, RelType
provides:
  - Neo4j Docker lifecycle management (start, stop, status, health check)
  - GraphClient with managed transactions and flat property mapping
  - Graceful degradation decorator for graph operations
  - neo4j>=5.20,<6.0 Python driver dependency
affects: [09-02-seed-pipeline, 09-03-feasibility-query-engine, 09-04-cli-integration]

# Tech tracking
tech-stack:
  added: [neo4j 5.28.x Python driver]
  patterns: [flat property mapping with geo_/temp_/rad_/op_/fs_ prefixes, lazy neo4j import, graceful_graph_op decorator]

key-files:
  created:
    - src/agentsim/knowledge_graph/docker.py
    - src/agentsim/knowledge_graph/client.py
    - src/agentsim/knowledge_graph/degradation.py
    - tests/unit/test_docker.py
    - tests/unit/test_client.py
    - tests/unit/test_degradation.py
  modified:
    - pyproject.toml

key-decisions:
  - "Lazy neo4j import in client.py to avoid numpy/pandas binary incompatibility at import time"
  - "Broad exception catch in graceful_graph_op for neo4j import to handle ValueErrors from binary deps"

patterns-established:
  - "Flat property mapping: nested Pydantic models stored with prefix convention (geo_, temp_, rad_, op_, fs_) in Neo4j"
  - "Lazy driver import: GraphDatabase imported at first use, not module load, enabling mock-based testing"
  - "Docker lifecycle via subprocess list args (never shell=True)"

requirements-completed: [GRAPH-01, GRAPH-03, GRAPH-06]

# Metrics
duration: 8min
completed: 2026-04-09
---

# Phase 09 Plan 01: Neo4j Infrastructure Summary

**Neo4j Docker lifecycle, typed graph client with flat property mapping, and graceful degradation decorator**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-09T16:40:55Z
- **Completed:** 2026-04-09T16:48:34Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Docker lifecycle manager (start/stop/status/health) with persistent volume and stale container cleanup
- GraphClient with execute_read/execute_write managed transactions, MERGE-based idempotent writes, and parameterized Cypher
- Flat property mapping (_sensor_to_props / _record_to_sensor) for SensorNode round-trip through Neo4j
- Graceful degradation decorator catching ServiceUnavailable/ConnectionRefusedError/OSError with fallback values
- 59 unit tests passing with mocked subprocess and neo4j driver

## Task Commits

Each task was committed atomically:

1. **Task 1: Neo4j Docker lifecycle and graceful degradation** - `3daacf7` (feat)
2. **Task 2: Neo4j graph client with managed transactions and flat property mapping** - `b7c7a0e` (feat)

## Files Created/Modified
- `pyproject.toml` - Added neo4j>=5.20,<6.0 dependency
- `src/agentsim/knowledge_graph/docker.py` - Docker lifecycle: start, stop, status, health check, DockerStatus model
- `src/agentsim/knowledge_graph/client.py` - GraphClient with CRUD, flat property mapping, managed transactions
- `src/agentsim/knowledge_graph/degradation.py` - graceful_graph_op decorator, is_graph_available socket check
- `tests/unit/test_docker.py` - 18 tests for Docker lifecycle
- `tests/unit/test_client.py` - 28 tests for GraphClient and property mapping
- `tests/unit/test_degradation.py` - 13 tests for degradation layer

## Decisions Made
- Lazy neo4j import in client.py avoids numpy/pandas binary incompatibility crash at import time (env has incompatible pandas/numpy versions, neo4j optionally imports pandas)
- Broad exception catch (including ValueError) in graceful_graph_op's neo4j import attempt to handle binary dep issues

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy neo4j import to avoid binary incompatibility**
- **Found during:** Task 2 (GraphClient implementation)
- **Issue:** `from neo4j import GraphDatabase` at module level triggered pandas -> numpy ValueError (binary size mismatch) in this environment
- **Fix:** Made GraphDatabase import lazy (deferred to first GraphClient instantiation) with module-level variable that tests can patch
- **Files modified:** src/agentsim/knowledge_graph/client.py
- **Verification:** All 59 tests pass, import succeeds
- **Committed in:** b7c7a0e (Task 2 commit)

**2. [Rule 3 - Blocking] Broadened exception catch in graceful_graph_op**
- **Found during:** Task 2 verification (full test suite run)
- **Issue:** graceful_graph_op's lazy `from neo4j.exceptions import ServiceUnavailable` also triggered the ValueError from pandas/numpy
- **Fix:** Catch Exception (not just ImportError) during neo4j import attempt in the wrapper
- **Files modified:** src/agentsim/knowledge_graph/degradation.py
- **Verification:** All 59 tests pass
- **Committed in:** b7c7a0e (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for the code to work in this environment. No scope creep.

## Issues Encountered
- numpy/pandas binary incompatibility in environment (numpy 2.4.4 vs pandas expecting <1.28.0) causes crash on neo4j import since neo4j optionally imports pandas. Resolved via lazy imports.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all modules fully implemented with real logic.

## Next Phase Readiness
- Docker lifecycle, graph client, and degradation layer ready for seed pipeline (Plan 02)
- GraphClient.ensure_schema() ready to create constraints/indexes from schema.py
- Flat property mapping ready for loader -> Neo4j seeding
- neo4j driver installed and verified

---
*Phase: 09-neo4j-infrastructure-and-feasibility-queries*
*Completed: 2026-04-09*
