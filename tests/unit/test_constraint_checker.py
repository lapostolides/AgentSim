"""Tests for constraint_checker module -- constraint evaluation and conflict detection."""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.models import (
    ConstraintSatisfaction,
    GeometricProps,
    OperationalProps,
    RadiometricProps,
    SensorFamily,
    SensorNode,
    TemporalProps,
)


# ---------------------------------------------------------------------------
# Fixture sensors
# ---------------------------------------------------------------------------


def _make_spad_sensor() -> SensorNode:
    """A SPAD sensor with well-defined properties for constraint testing."""
    return SensorNode(
        name="TestSPAD",
        family=SensorFamily.SPAD,
        description="Test SPAD array",
        geometric=GeometricProps(
            fov=120.0,
            spatial_resolution=512.0,
            spatial_resolution_unit="pixel",
            working_distance_min=0.5,
            working_distance_max=50.0,
            working_distance_unit="meter",
        ),
        temporal=TemporalProps(
            temporal_resolution=100.0,
            temporal_resolution_unit="picosecond",
            frame_rate=1000.0,
        ),
        radiometric=RadiometricProps(
            quantum_efficiency=0.3,
            dynamic_range_db=90.0,
            noise_floor=0.01,
        ),
        operational=OperationalProps(
            cost_min_usd=5000.0,
            cost_max_usd=15000.0,
            power_w=8.0,
            weight_g=500.0,
        ),
        family_specs={
            "dead_time_ns": 20.0,
            "afterpulsing_probability": 0.01,
            "crosstalk_probability": 0.02,
            "fill_factor": 0.6,
            "pde": 0.25,
        },
    )


def _make_lidar_sensor() -> SensorNode:
    """A mechanical LiDAR sensor with limited temporal resolution."""
    return SensorNode(
        name="TestLiDAR",
        family=SensorFamily.LIDAR_MECHANICAL,
        description="Test mechanical LiDAR",
        geometric=GeometricProps(
            fov=360.0,
            spatial_resolution=None,
            working_distance_min=1.0,
            working_distance_max=200.0,
            working_distance_unit="meter",
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
            cost_min_usd=2000.0,
            cost_max_usd=8000.0,
            power_w=15.0,
            weight_g=800.0,
        ),
        family_specs={
            "scan_rate_rpm": 600.0,
            "angular_resolution_deg": 0.2,
            "max_range_m": 200.0,
        },
    )


def _make_minimal_sensor() -> SensorNode:
    """A sensor with minimal properties (many None values)."""
    return SensorNode(
        name="MinimalRGB",
        family=SensorFamily.RGB,
        description="Minimal RGB camera",
        geometric=GeometricProps(
            fov=60.0,
        ),
        temporal=TemporalProps(),
        radiometric=RadiometricProps(),
        operational=None,
        family_specs={
            "pixel_pitch_um": 3.5,
            "well_depth_electrons": 10000.0,
            "read_noise_electrons": 2.0,
        },
    )


# ---------------------------------------------------------------------------
# check_constraints tests
# ---------------------------------------------------------------------------


class TestCheckConstraints:
    """Tests for check_constraints function."""

    def test_range_constraint_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()
        result = check_constraints(sensor, {"range_m": 10.0})
        assert len(result) == 1
        assert result[0].constraint_name == "range_m"
        assert result[0].satisfied is True
        assert result[0].margin > 0  # headroom

    def test_range_constraint_violated_too_far(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # max 50m
        result = check_constraints(sensor, {"range_m": 100.0})
        assert result[0].satisfied is False
        assert result[0].margin < 0  # deficit

    def test_range_constraint_violated_too_close(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # min 0.5m
        result = check_constraints(sensor, {"range_m": 0.1})
        assert result[0].satisfied is False

    def test_range_constraint_none_working_distance(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_minimal_sensor()  # no working distance
        result = check_constraints(sensor, {"range_m": 10.0})
        assert result[0].satisfied is False
        assert "not specified" in result[0].details

    def test_ambient_light_dark(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()
        result = check_constraints(sensor, {"ambient_light": "dark"})
        assert result[0].satisfied is True

    def test_ambient_light_outdoor_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_lidar_sensor()  # dynamic_range_db=100
        result = check_constraints(sensor, {"ambient_light": "outdoor"})
        assert result[0].satisfied is True
        assert result[0].margin == pytest.approx(20.0)  # 100 - 80

    def test_ambient_light_outdoor_violated(self) -> None:
        """A sensor with low dynamic range fails outdoor constraint."""
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        # Create sensor with dynamic_range_db=50 (below outdoor threshold of 80)
        sensor = SensorNode(
            name="LowDR",
            family=SensorFamily.RGB,
            description="Low DR camera",
            geometric=GeometricProps(fov=60.0),
            temporal=TemporalProps(),
            radiometric=RadiometricProps(dynamic_range_db=50.0),
            operational=None,
            family_specs={
                "pixel_pitch_um": 3.5,
                "well_depth_electrons": 10000.0,
                "read_noise_electrons": 2.0,
            },
        )
        result = check_constraints(sensor, {"ambient_light": "outdoor"})
        assert result[0].satisfied is False
        assert result[0].margin == pytest.approx(-30.0)  # 50 - 80

    def test_ambient_light_none_dynamic_range(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_minimal_sensor()  # no dynamic_range_db
        result = check_constraints(sensor, {"ambient_light": "outdoor"})
        assert result[0].satisfied is True
        assert "not specified" in result[0].details

    def test_temporal_resolution_picosecond_vs_second(self) -> None:
        """Pint must normalize picosecond to second for comparison."""
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # 100 ps
        # Require < 1 nanosecond = 1e-9 seconds
        result = check_constraints(sensor, {"temporal_resolution_s": 1e-9})
        assert result[0].satisfied is True
        assert result[0].margin > 0

    def test_temporal_resolution_violated(self) -> None:
        """Sensor with 5ns cannot satisfy 100ps requirement."""
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_lidar_sensor()  # 5 nanosecond
        # Require < 100 picoseconds = 1e-10 seconds
        result = check_constraints(sensor, {"temporal_resolution_s": 1e-10})
        assert result[0].satisfied is False
        assert result[0].margin < 0

    def test_temporal_resolution_none(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_minimal_sensor()  # no temporal_resolution
        result = check_constraints(sensor, {"temporal_resolution_s": 1e-9})
        assert result[0].satisfied is False
        assert "not specified" in result[0].details

    def test_budget_constraint_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # cost_max_usd=15000
        result = check_constraints(sensor, {"budget_usd": 20000.0})
        assert result[0].satisfied is True
        assert result[0].margin == pytest.approx(5000.0)

    def test_budget_constraint_violated(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # cost_max_usd=15000
        result = check_constraints(sensor, {"budget_usd": 10000.0})
        assert result[0].satisfied is False
        assert result[0].margin == pytest.approx(-5000.0)

    def test_budget_none_operational(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_minimal_sensor()  # no operational
        result = check_constraints(sensor, {"budget_usd": 5000.0})
        assert result[0].satisfied is True
        assert "not specified" in result[0].details

    def test_weight_constraint_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # weight_g=500
        result = check_constraints(sensor, {"weight_g": 1000.0})
        assert result[0].satisfied is True
        assert result[0].margin == pytest.approx(500.0)

    def test_power_constraint_violated(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # power_w=8
        result = check_constraints(sensor, {"power_w": 5.0})
        assert result[0].satisfied is False
        assert result[0].margin == pytest.approx(-3.0)

    def test_spatial_resolution_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()  # spatial_resolution=512
        result = check_constraints(sensor, {"spatial_resolution": 256.0})
        assert result[0].satisfied is True
        assert result[0].margin == pytest.approx(256.0)  # 512 - 256

    def test_spatial_resolution_none(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_lidar_sensor()  # spatial_resolution=None
        result = check_constraints(sensor, {"spatial_resolution": 256.0})
        assert result[0].satisfied is False

    def test_multiple_constraints(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()
        result = check_constraints(sensor, {
            "range_m": 10.0,
            "budget_usd": 20000.0,
            "weight_g": 1000.0,
        })
        assert len(result) == 3
        assert all(s.satisfied for s in result)

    def test_unknown_constraint_skipped(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import check_constraints

        sensor = _make_spad_sensor()
        result = check_constraints(sensor, {"unknown_param": 42})
        assert len(result) == 0  # unknown constraints are skipped


# ---------------------------------------------------------------------------
# feasibility_score tests
# ---------------------------------------------------------------------------


class TestFeasibilityScore:
    """Tests for feasibility_score function."""

    def test_all_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import feasibility_score

        sats = (
            ConstraintSatisfaction(constraint_name="a", satisfied=True, margin=1.0),
            ConstraintSatisfaction(constraint_name="b", satisfied=True, margin=2.0),
        )
        assert feasibility_score(sats) == pytest.approx(1.0)

    def test_half_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import feasibility_score

        sats = (
            ConstraintSatisfaction(constraint_name="a", satisfied=True),
            ConstraintSatisfaction(constraint_name="b", satisfied=False),
        )
        assert feasibility_score(sats) == pytest.approx(0.5)

    def test_none_satisfied(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import feasibility_score

        sats = (
            ConstraintSatisfaction(constraint_name="a", satisfied=False),
        )
        assert feasibility_score(sats) == pytest.approx(0.0)

    def test_empty(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import feasibility_score

        assert feasibility_score(()) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# detect_conflicts tests
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    """Tests for detect_conflicts function."""

    def test_no_conflict_when_feasible(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import detect_conflicts

        sensors = (_make_spad_sensor(), _make_lidar_sensor())
        result = detect_conflicts({"range_m": 10.0}, sensors)
        assert result is None

    def test_conflict_detected_impossible_constraints(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import detect_conflicts

        sensors = (_make_spad_sensor(), _make_lidar_sensor())
        # Range 1000m exceeds both sensors, budget $10 is too low for both
        result = detect_conflicts(
            {"range_m": 1000.0, "budget_usd": 10.0},
            sensors,
        )
        assert result is not None
        assert len(result.conflicting_constraints) > 0
        assert result.closest_sensor in ("TestSPAD", "TestLiDAR")
        assert "No sensor satisfies" in result.reason

    def test_conflict_reports_closest_sensor(self) -> None:
        from agentsim.knowledge_graph.constraint_checker import detect_conflicts

        sensors = (_make_spad_sensor(), _make_lidar_sensor())
        # LiDAR satisfies budget + weight but not range (2/3 satisfied)
        # SPAD satisfies budget but not range or weight (1/3 satisfied)
        # So LiDAR should be the closest sensor
        result = detect_conflicts(
            {"range_m": 500.0, "budget_usd": 50000.0, "weight_g": 600.0},
            sensors,
        )
        assert result is not None
        # LiDAR: budget OK, weight NOT (800 > 600), range NOT -> 1/3
        # SPAD: budget OK, weight OK (500 <= 600), range NOT -> 2/3
        # SPAD is closer here
        assert result.closest_sensor == "TestSPAD"

    def test_no_conflict_empty_sensors(self) -> None:
        """Empty sensor list produces a conflict (no sensor can satisfy)."""
        from agentsim.knowledge_graph.constraint_checker import detect_conflicts

        result = detect_conflicts({"range_m": 10.0}, ())
        assert result is not None
