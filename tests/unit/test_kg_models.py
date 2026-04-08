"""Tests for knowledge graph Pydantic models.

Covers SensorFamily enum, property groups with unit validation,
SensorNode with family_specs validation, edge models, and FeasibilityResult.
"""

from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# SensorFamily enum
# ---------------------------------------------------------------------------


class TestSensorFamily:
    def test_member_count(self) -> None:
        assert len(SensorFamily) == 14

    def test_spad_value(self) -> None:
        assert SensorFamily.SPAD.value == "spad"

    def test_all_values_are_strings(self) -> None:
        for member in SensorFamily:
            assert isinstance(member.value, str)


# ---------------------------------------------------------------------------
# GeometricProps
# ---------------------------------------------------------------------------


class TestGeometricProps:
    def test_valid_construction(self) -> None:
        props = GeometricProps(fov=90.0, fov_unit="degree")
        assert props.fov == 90.0
        assert props.fov_unit == "degree"

    def test_wrong_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="meter"):
            GeometricProps(fov=90.0, fov_unit="meter")

    def test_optional_fields_default_none(self) -> None:
        props = GeometricProps(fov=120.0)
        assert props.spatial_resolution is None
        assert props.depth_of_field is None
        assert props.working_distance_min is None


# ---------------------------------------------------------------------------
# TemporalProps
# ---------------------------------------------------------------------------


class TestTemporalProps:
    def test_valid_construction(self) -> None:
        props = TemporalProps(exposure_time=0.001, exposure_time_unit="second")
        assert props.exposure_time == 0.001

    def test_wrong_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="degree"):
            TemporalProps(exposure_time=0.001, exposure_time_unit="degree")

    def test_frame_rate_unit_validation(self) -> None:
        props = TemporalProps(frame_rate=30.0, frame_rate_unit="hertz")
        assert props.frame_rate == 30.0


# ---------------------------------------------------------------------------
# RadiometricProps
# ---------------------------------------------------------------------------


class TestRadiometricProps:
    def test_valid_construction(self) -> None:
        props = RadiometricProps(
            quantum_efficiency=0.5, quantum_efficiency_unit="dimensionless"
        )
        assert props.quantum_efficiency == 0.5

    def test_optional_fields(self) -> None:
        props = RadiometricProps()
        assert props.dynamic_range_db is None
        assert props.noise_floor is None


# ---------------------------------------------------------------------------
# OperationalProps
# ---------------------------------------------------------------------------


class TestOperationalProps:
    def test_construction(self) -> None:
        props = OperationalProps(cost_min_usd=100.0, cost_max_usd=5000.0)
        assert props.cost_min_usd == 100.0
        assert props.cost_max_usd == 5000.0

    def test_defaults(self) -> None:
        props = OperationalProps()
        assert props.power_w is None
        assert props.form_factor == ""


# ---------------------------------------------------------------------------
# SensorNode + FAMILY_SCHEMAS
# ---------------------------------------------------------------------------


def _make_spad_family_specs() -> dict[str, float | str]:
    return {
        "dead_time_ns": 50.0,
        "afterpulsing_probability": 0.01,
        "crosstalk_probability": 0.02,
        "fill_factor": 0.5,
        "pde": 0.3,
    }


def _make_minimal_sensor_node(
    family: SensorFamily = SensorFamily.SPAD,
    family_specs: dict[str, float | str] | None = None,
) -> SensorNode:
    """Helper to construct a SensorNode with minimal required fields."""
    if family_specs is None:
        family_specs = _make_spad_family_specs()
    return SensorNode(
        name="test_sensor",
        family=family,
        geometric=GeometricProps(fov=90.0),
        temporal=TemporalProps(),
        radiometric=RadiometricProps(),
        family_specs=family_specs,
    )


class TestSensorNode:
    def test_valid_spad(self) -> None:
        node = _make_minimal_sensor_node()
        assert node.name == "test_sensor"
        assert node.family == SensorFamily.SPAD

    def test_missing_family_spec_raises(self) -> None:
        incomplete_specs = {"dead_time_ns": 50.0}  # missing other required keys
        with pytest.raises(ValueError, match="afterpulsing_probability"):
            _make_minimal_sensor_node(family_specs=incomplete_specs)

    def test_family_schemas_completeness(self) -> None:
        assert set(SensorFamily) == set(FAMILY_SCHEMAS.keys())


# ---------------------------------------------------------------------------
# Edge models
# ---------------------------------------------------------------------------


class TestEdgeModels:
    def test_shares_physics_edge_frozen(self) -> None:
        edge = SharesPhysicsEdge(
            source_family=SensorFamily.SPAD,
            target_family=SensorFamily.CW_TOF,
            shared_principle="time_of_flight",
        )
        with pytest.raises(Exception):
            edge.shared_principle = "changed"  # type: ignore[misc]

    def test_compatible_with_edge_frozen(self) -> None:
        edge = CompatibleWithEdge(
            sensor_name="spad_sensor",
            algorithm_name="nlos_recon",
        )
        assert edge.sensor_name == "spad_sensor"
        with pytest.raises(Exception):
            edge.sensor_name = "changed"  # type: ignore[misc]

    def test_algorithm_node_frozen(self) -> None:
        node = AlgorithmNode(name="phasor_field", paradigm="nlos")
        assert node.name == "phasor_field"
        assert node.paradigm == "nlos"
        with pytest.raises(Exception):
            node.name = "changed"  # type: ignore[misc]

    def test_task_node_frozen(self) -> None:
        node = TaskNode(name="depth_estimation", description="Estimate depth map")
        assert node.name == "depth_estimation"
        assert node.constraints == ()

    def test_environment_node_frozen(self) -> None:
        node = EnvironmentNode(name="indoor_lab", constraints=("no_sunlight",))
        assert node.name == "indoor_lab"
        assert node.constraints == ("no_sunlight",)

    def test_belongs_to_edge(self) -> None:
        edge = BelongsToEdge(sensor_name="spad_1", family=SensorFamily.SPAD)
        assert edge.family == SensorFamily.SPAD

    def test_achieves_bound_edge(self) -> None:
        edge = AchievesBoundEdge(
            sensor_name="spad_1",
            task_name="depth_estimation",
            bound_value=0.01,
            bound_unit="meter",
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        assert edge.confidence == ConfidenceQualifier.ANALYTICAL


# ---------------------------------------------------------------------------
# FeasibilityResult + SensorConfig
# ---------------------------------------------------------------------------


class TestFeasibilityResult:
    def test_construction(self) -> None:
        config = SensorConfig(
            sensor_name="spad_1",
            sensor_family=SensorFamily.SPAD,
            algorithm_name="phasor_field",
            crb_bound=0.01,
            crb_unit="meter",
            confidence=ConfidenceQualifier.ANALYTICAL,
            rank=1,
            feasibility_score=0.95,
        )
        result = FeasibilityResult(
            query_text="map cave at 1cm resolution",
            detected_task="3d_reconstruction",
            ranked_configs=(config,),
            total_count=10,
            pruned_count=9,
        )
        assert len(result.ranked_configs) == 1
        assert result.ranked_configs[0].sensor_name == "spad_1"
        assert result.pruned_count == 9

    def test_sensor_config_with_constraints(self) -> None:
        cs = ConstraintSatisfaction(
            constraint_name="max_range",
            satisfied=True,
            margin=5.0,
            unit="meter",
        )
        config = SensorConfig(
            sensor_name="lidar_1",
            sensor_family=SensorFamily.LIDAR_MECHANICAL,
            algorithm_name="point_cloud_icp",
            constraint_satisfaction=(cs,),
        )
        assert len(config.constraint_satisfaction) == 1
        assert config.constraint_satisfaction[0].satisfied is True


# ---------------------------------------------------------------------------
# Frozen immutability check across all models
# ---------------------------------------------------------------------------


class TestAllModelsFrozen:
    def test_geometric_props_frozen(self) -> None:
        props = GeometricProps(fov=90.0)
        with pytest.raises(Exception):
            props.fov = 100.0  # type: ignore[misc]

    def test_temporal_props_frozen(self) -> None:
        props = TemporalProps()
        with pytest.raises(Exception):
            props.exposure_time = 1.0  # type: ignore[misc]

    def test_radiometric_props_frozen(self) -> None:
        props = RadiometricProps()
        with pytest.raises(Exception):
            props.quantum_efficiency = 0.9  # type: ignore[misc]

    def test_operational_props_frozen(self) -> None:
        props = OperationalProps()
        with pytest.raises(Exception):
            props.cost_min_usd = 999.0  # type: ignore[misc]

    def test_sensor_node_frozen(self) -> None:
        node = _make_minimal_sensor_node()
        with pytest.raises(Exception):
            node.name = "changed"  # type: ignore[misc]

    def test_feasibility_result_frozen(self) -> None:
        result = FeasibilityResult(query_text="test")
        with pytest.raises(Exception):
            result.query_text = "changed"  # type: ignore[misc]

    def test_constraint_satisfaction_frozen(self) -> None:
        cs = ConstraintSatisfaction(constraint_name="test", satisfied=True)
        with pytest.raises(Exception):
            cs.satisfied = False  # type: ignore[misc]
