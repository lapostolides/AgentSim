"""Tests for paradigm-agnostic Pydantic schema models.

Tests cover: TransferFunction, ValidationRule, ParadigmKnowledge,
TimingParameters, SpatialParameters, NoiseModel, OperationalMode,
SensorProfile, SensorCatalog, ReconstructionAlgorithmV2, and
YAML file validation for paradigm/sensor data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentsim.physics.domains.schema import (
    DomainKnowledge,
    NoiseModel,
    OperationalMode,
    ParameterRange,
    ParadigmKnowledge,
    ReconstructionAlgorithmV2,
    SensorCatalog,
    SensorProfile,
    SpatialParameters,
    TimingParameters,
    TransferFunction,
    ValidationRule,
)


class TestTransferFunction:
    """Test TransferFunction model validation."""

    def test_validates_with_all_fields(self) -> None:
        """Test 1: TransferFunction validates with typical input."""
        tf = TransferFunction.model_validate({
            "input": "temporal_resolution_ps",
            "output": "spatial_resolution_m",
            "relationship": "linear",
            "formula": "c * dt / 2",
        })
        assert tf.input == "temporal_resolution_ps"
        assert tf.output == "spatial_resolution_m"
        assert tf.relationship == "linear"
        assert tf.formula == "c * dt / 2"

    def test_is_frozen(self) -> None:
        """TransferFunction is immutable."""
        tf = TransferFunction(
            input="a", output="b", relationship="linear",
        )
        with pytest.raises(Exception):
            tf.input = "c"  # type: ignore[misc]


class TestValidationRule:
    """Test ValidationRule model validation."""

    def test_python_check_validates(self) -> None:
        """Test 2: ValidationRule validates as python_check."""
        rule = ValidationRule.model_validate({
            "name": "three_bounce_geometry",
            "type": "python_check",
            "module": "agentsim.physics.checks.nlos_geometry",
            "function": "check_three_bounce_geometry",
        })
        assert rule.type == "python_check"
        assert rule.module == "agentsim.physics.checks.nlos_geometry"
        assert rule.function == "check_three_bounce_geometry"

    def test_range_check_validates(self) -> None:
        """Test 3: ValidationRule validates as range_check."""
        rule = ValidationRule.model_validate({
            "name": "wall_size_range",
            "type": "range_check",
            "parameter": "relay_wall_size",
            "min": 0.1,
            "max": 10.0,
            "severity": "error",
        })
        assert rule.type == "range_check"
        assert rule.parameter == "relay_wall_size"
        assert rule.min == 0.1
        assert rule.max == 10.0
        assert rule.severity == "error"

    def test_is_frozen(self) -> None:
        """ValidationRule is immutable."""
        rule = ValidationRule(name="test", type="range_check")
        with pytest.raises(Exception):
            rule.name = "other"  # type: ignore[misc]


class TestParadigmKnowledge:
    """Test ParadigmKnowledge model validation."""

    def test_complete_relay_wall_paradigm(self) -> None:
        """Test 4: ParadigmKnowledge validates a complete relay-wall paradigm."""
        data = {
            "paradigm": "relay_wall",
            "domain": "nlos_transient_imaging",
            "version": "1.0",
            "description": "Classic relay-wall NLOS",
            "keywords": ["relay wall", "three-bounce", "confocal"],
            "compatible_sensor_types": ["spad", "streak_camera"],
            "geometry_constraints": {
                "relay_wall": {
                    "min_size_m": 0.1,
                    "max_size_m": 10.0,
                    "typical_size_m": 2.0,
                    "surface": "Lambertian diffuse",
                },
                "sensor_to_wall_distance": {
                    "min_m": 0.1,
                    "max_m": 100.0,
                    "typical_m": 1.5,
                },
            },
            "validation_rules": [
                {
                    "name": "three_bounce_geometry",
                    "type": "python_check",
                    "module": "agentsim.physics.checks.nlos_geometry",
                    "function": "check_three_bounce_geometry",
                },
            ],
            "transfer_functions": [
                {
                    "input": "temporal_resolution_ps",
                    "output": "spatial_resolution_m",
                    "relationship": "linear",
                    "formula": "c * dt / 2",
                },
            ],
        }
        pk = ParadigmKnowledge.model_validate(data)
        assert pk.paradigm == "relay_wall"
        assert pk.domain == "nlos_transient_imaging"
        assert len(pk.keywords) == 3
        assert len(pk.compatible_sensor_types) == 2
        assert "relay_wall" in pk.geometry_constraints
        assert len(pk.validation_rules) == 1
        assert len(pk.transfer_functions) == 1

    def test_is_frozen(self) -> None:
        """ParadigmKnowledge is immutable."""
        pk = ParadigmKnowledge(paradigm="test", domain="test")
        with pytest.raises(Exception):
            pk.paradigm = "other"  # type: ignore[misc]


class TestSensorModels:
    """Test sensor-related model validation."""

    def test_timing_spatial_noise_operational(self) -> None:
        """Test 5: TimingParameters, SpatialParameters, NoiseModel, OperationalMode validate."""
        timing = TimingParameters.model_validate({
            "temporal_resolution_ps": {"min": 17.8, "max": 17.8, "typical": 17.8},
            "jitter_fwhm_ps": {"min": 50, "max": 100, "typical": 70},
            "dead_time_ns": {"min": 5, "max": 25, "typical": 10},
        })
        assert timing.temporal_resolution_ps is not None
        assert timing.temporal_resolution_ps.typical == 17.8

        spatial = SpatialParameters.model_validate({
            "array_size": [512, 512],
            "pixel_pitch_um": 16.38,
            "fill_factor": 0.105,
        })
        assert spatial.array_size == (512, 512)
        assert spatial.pixel_pitch_um == 16.38

        noise = NoiseModel.model_validate({
            "dark_count_rate_hz": 100,
            "afterpulsing_probability": 0.003,
            "crosstalk_probability": 0.01,
            "quantum_efficiency": 0.35,
        })
        assert noise.dark_count_rate_hz == 100
        assert noise.quantum_efficiency == 0.35

        mode = OperationalMode.model_validate({
            "name": "time_gated",
            "timing_constraints": {"gate_width_ns": 10.0},
            "description": "Gated mode",
        })
        assert mode.name == "time_gated"

    def test_sensor_profile_swissspad2(self) -> None:
        """SensorProfile validates SwissSPAD2 data."""
        data = {
            "name": "SwissSPAD2",
            "sensor_type": "spad",
            "manufacturer": "EPFL",
            "reference": "Ulku et al. 2019",
            "timing": {
                "temporal_resolution_ps": {"min": 17.8, "max": 17.8, "typical": 17.8},
                "jitter_fwhm_ps": {"min": 50, "max": 100, "typical": 70},
                "dead_time_ns": {"min": 5, "max": 25, "typical": 10},
            },
            "spatial": {
                "array_size": [512, 512],
                "pixel_pitch_um": 16.38,
                "fill_factor": 0.105,
            },
            "noise": {
                "dark_count_rate_hz": 100,
                "quantum_efficiency": 0.35,
            },
            "operational_modes": [
                {"name": "time_gated", "timing_constraints": {"gate_width_ns": 10.0}},
            ],
            "transfer_functions": [
                {
                    "input": "temporal_resolution_ps",
                    "output": "depth_resolution_m",
                    "relationship": "linear",
                    "formula": "c * dt / 2",
                },
            ],
        }
        sp = SensorProfile.model_validate(data)
        assert sp.name == "SwissSPAD2"
        assert sp.sensor_type == "spad"
        assert sp.timing.temporal_resolution_ps is not None

    def test_all_sensor_models_frozen(self) -> None:
        """Test 8: All new sensor models are frozen (immutable)."""
        timing = TimingParameters()
        with pytest.raises(Exception):
            timing.gate_width_ns = None  # type: ignore[misc]

        spatial = SpatialParameters(array_size=(1, 1), pixel_pitch_um=1.0)
        with pytest.raises(Exception):
            spatial.fill_factor = 0.5  # type: ignore[misc]

        noise = NoiseModel()
        with pytest.raises(Exception):
            noise.dark_count_rate_hz = 1.0  # type: ignore[misc]

        mode = OperationalMode(name="test")
        with pytest.raises(Exception):
            mode.name = "other"  # type: ignore[misc]


class TestSensorCatalog:
    """Test SensorCatalog model validation."""

    def test_catalog_with_three_sensors(self) -> None:
        """Test 6: SensorCatalog validates with 3 sensor entries."""
        timing_data = {
            "temporal_resolution_ps": {"min": 1, "max": 100, "typical": 10},
        }
        spatial_data = {"array_size": [64, 64], "pixel_pitch_um": 10.0}
        sensor_template = {
            "name": "Sensor",
            "sensor_type": "spad",
            "timing": timing_data,
            "spatial": spatial_data,
        }

        catalog_data = {
            "sensors": {
                "sensor_a": {**sensor_template, "name": "SensorA"},
                "sensor_b": {**sensor_template, "name": "SensorB"},
                "sensor_c": {**sensor_template, "name": "SensorC"},
            },
        }
        catalog = SensorCatalog.model_validate(catalog_data)
        assert len(catalog.sensors) == 3
        assert "sensor_a" in catalog.sensors
        assert catalog.sensors["sensor_a"].name == "SensorA"

    def test_is_frozen(self) -> None:
        """SensorCatalog is immutable."""
        catalog = SensorCatalog()
        with pytest.raises(Exception):
            catalog.sensors = {}  # type: ignore[misc]


class TestReconstructionAlgorithmV2:
    """Test ReconstructionAlgorithmV2 model validation."""

    def test_v2_with_structured_fields(self) -> None:
        """ReconstructionAlgorithmV2 validates with extended fields."""
        data = {
            "name": "Light Cone Transform",
            "reference": "O'Toole et al. 2018",
            "requires_confocal": True,
            "input_requirements": [
                {"confocal_scanning": True, "min_scan_points": 16},
            ],
            "output_characteristics": [
                "Spatial resolution limited by relay wall sampling",
            ],
            "transfer_functions": [
                {
                    "input": "temporal_resolution",
                    "output": "depth_resolution",
                    "relationship": "linear",
                    "formula": "c * dt / 2",
                    "coupling_strength": "strong",
                },
            ],
        }
        alg = ReconstructionAlgorithmV2.model_validate(data)
        assert alg.name == "Light Cone Transform"
        assert len(alg.input_requirements) == 1
        assert len(alg.output_characteristics) == 1
        assert len(alg.transfer_functions) == 1

    def test_is_frozen(self) -> None:
        """ReconstructionAlgorithmV2 is immutable."""
        alg = ReconstructionAlgorithmV2(name="test")
        with pytest.raises(Exception):
            alg.name = "other"  # type: ignore[misc]


class TestBackwardCompatibility:
    """Test that existing DomainKnowledge still works."""

    def test_domain_knowledge_still_validates(self) -> None:
        """Test 7: Existing DomainKnowledge validates minimal data."""
        data = {"domain": "test", "version": "1.0"}
        dk = DomainKnowledge.model_validate(data)
        assert dk.domain == "test"
        assert dk.geometry_constraints is None
        assert dk.sensor_parameters is None


# ---------------------------------------------------------------------------
# YAML file validation tests (Task 2)
# ---------------------------------------------------------------------------

_DOMAINS_DIR = Path(__file__).resolve().parents[2] / "src" / "agentsim" / "physics" / "domains"
_PARADIGMS_DIR = _DOMAINS_DIR / "paradigms"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its parsed content."""
    with open(path) as f:
        return yaml.safe_load(f)


class TestRelayWallYaml:
    """Test relay_wall.yaml validates against ParadigmKnowledge."""

    def test_relay_wall_yaml_validates(self) -> None:
        """Load relay_wall.yaml and validate as ParadigmKnowledge."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert pk.paradigm == "relay_wall"
        assert pk.domain == "nlos_transient_imaging"

    def test_relay_wall_has_validation_rules(self) -> None:
        """Relay-wall paradigm has >= 4 validation_rules."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert len(pk.validation_rules) >= 4

    def test_relay_wall_has_transfer_functions(self) -> None:
        """Relay-wall paradigm has >= 10 transfer_functions (SNR, resolution, geometry)."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert len(pk.transfer_functions) >= 10

    def test_relay_wall_transfer_function_categories(self) -> None:
        """Relay-wall transfer functions cover SNR, resolution, and geometry."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        outputs = {tf.output for tf in pk.transfer_functions}
        # SNR category
        assert "signal_intensity" in outputs or "snr" in outputs
        # Resolution category
        assert "angular_resolution_rad" in outputs
        # Geometry category
        assert "laser_spot_size_m" in outputs or "depth_ambiguity_m" in outputs

    def test_relay_wall_has_geometry_constraints(self) -> None:
        """Relay-wall paradigm has geometry_constraints with relay_wall key."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert "relay_wall" in pk.geometry_constraints
        assert "sensor_to_wall_distance" in pk.geometry_constraints

    def test_relay_wall_has_published_baselines(self) -> None:
        """Relay-wall paradigm has published_baselines."""
        raw = _load_yaml(_PARADIGMS_DIR / "relay_wall.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert len(pk.published_baselines) >= 2


class TestPenumbraYaml:
    """Test penumbra.yaml validates against ParadigmKnowledge."""

    def test_penumbra_yaml_validates(self) -> None:
        """Load penumbra.yaml and validate as ParadigmKnowledge."""
        raw = _load_yaml(_PARADIGMS_DIR / "penumbra.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert pk.paradigm == "penumbra"
        assert pk.domain == "nlos_transient_imaging"

    def test_penumbra_has_geometry_constraints(self) -> None:
        """Penumbra paradigm has aperture and occluder constraints."""
        raw = _load_yaml(_PARADIGMS_DIR / "penumbra.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert "aperture" in pk.geometry_constraints
        assert "occluder_to_wall_distance" in pk.geometry_constraints

    def test_penumbra_has_validation_rules(self) -> None:
        """Penumbra paradigm has >= 2 validation_rules."""
        raw = _load_yaml(_PARADIGMS_DIR / "penumbra.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert len(pk.validation_rules) >= 2

    def test_penumbra_has_transfer_functions(self) -> None:
        """Penumbra paradigm has >= 6 transfer_functions (optical, SNR, geometry)."""
        raw = _load_yaml(_PARADIGMS_DIR / "penumbra.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        assert len(pk.transfer_functions) >= 6

    def test_penumbra_transfer_function_categories(self) -> None:
        """Penumbra transfer functions cover SNR and geometry-specific couplings."""
        raw = _load_yaml(_PARADIGMS_DIR / "penumbra.yaml")
        pk = ParadigmKnowledge.model_validate(raw)
        outputs = {tf.output for tf in pk.transfer_functions}
        assert "signal_intensity" in outputs  # SNR
        assert "magnification" in outputs  # penumbra-specific
        assert "penumbra_width_m" in outputs  # penumbra-specific


class TestSensorsYaml:
    """Test sensors.yaml validates against SensorCatalog."""

    def test_sensors_yaml_validates(self) -> None:
        """Load sensors.yaml and validate as SensorCatalog."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        assert len(catalog.sensors) >= 3

    def test_sensors_has_three_profiles(self) -> None:
        """SensorCatalog has swissspad2, linospad2, and streak_camera."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        assert "swissspad2" in catalog.sensors
        assert "linospad2" in catalog.sensors
        assert "streak_camera" in catalog.sensors

    def test_swissspad2_has_all_categories(self) -> None:
        """SwissSPAD2 profile has timing, spatial, noise, and operational_modes."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        sensor = catalog.sensors["swissspad2"]
        assert sensor.timing.temporal_resolution_ps is not None
        assert sensor.spatial.array_size == (512, 512)
        assert sensor.noise is not None
        assert len(sensor.operational_modes) >= 1

    def test_streak_camera_has_timing(self) -> None:
        """Streak camera has sub-picosecond temporal resolution."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        sensor = catalog.sensors["streak_camera"]
        assert sensor.timing.temporal_resolution_ps is not None
        assert sensor.timing.temporal_resolution_ps.min < 1.0

    def test_sensors_have_hardware_transfer_functions(self) -> None:
        """Each sensor has >= 3 transfer functions (depth + hardware-specific)."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        for name, sensor in catalog.sensors.items():
            assert len(sensor.transfer_functions) >= 3, (
                f"Sensor {name} has {len(sensor.transfer_functions)} transfer_functions, expected >= 3"
            )

    def test_spad_sensors_have_pile_up_transfer_function(self) -> None:
        """SPAD sensors have dead_time -> max_count_rate transfer function."""
        raw = _load_yaml(_DOMAINS_DIR / "sensors.yaml")
        catalog = SensorCatalog.model_validate(raw)
        for name in ("swissspad2", "linospad2"):
            sensor = catalog.sensors[name]
            inputs = {tf.input for tf in sensor.transfer_functions}
            assert "dead_time_ns" in inputs, f"SPAD {name} missing dead_time transfer function"


class TestNlosYamlV2:
    """Test refactored nlos.yaml (v2.0) validates as DomainKnowledge."""

    def test_nlos_yaml_v2_validates(self) -> None:
        """Load refactored nlos.yaml and validate as DomainKnowledge."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        dk = DomainKnowledge.model_validate(raw)
        assert dk.domain == "nlos_transient_imaging"
        assert dk.version == "2.0"

    def test_nlos_yaml_no_geometry_constraints(self) -> None:
        """Refactored nlos.yaml does NOT contain geometry_constraints."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        assert "geometry_constraints" not in raw

    def test_nlos_yaml_no_sensor_parameters(self) -> None:
        """Refactored nlos.yaml does NOT contain sensor_parameters."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        assert "sensor_parameters" not in raw

    def test_nlos_yaml_has_domain_transfer_functions(self) -> None:
        """nlos.yaml has domain-level transfer functions shared across paradigms."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        dk = DomainKnowledge.model_validate(raw)
        assert len(dk.transfer_functions) >= 3
        inputs = {tf.input for tf in dk.transfer_functions}
        assert "background_ambient_lux" in inputs
        assert "laser_repetition_rate_hz" in inputs

    def test_nlos_yaml_retains_equations(self) -> None:
        """Refactored nlos.yaml retains governing_equations."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        dk = DomainKnowledge.model_validate(raw)
        eq_names = {eq.name for eq in dk.governing_equations}
        assert "transient_transport" in eq_names

    def test_nlos_yaml_retains_algorithms(self) -> None:
        """Refactored nlos.yaml retains reconstruction_algorithms."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        dk = DomainKnowledge.model_validate(raw)
        assert "lct" in dk.reconstruction_algorithms
        assert "fk_migration" in dk.reconstruction_algorithms
        assert "phasor_fields" in dk.reconstruction_algorithms

    def test_nlos_yaml_retains_published_index(self) -> None:
        """Refactored nlos.yaml retains published_parameter_index."""
        raw = _load_yaml(_DOMAINS_DIR / "nlos.yaml")
        dk = DomainKnowledge.model_validate(raw)
        assert len(dk.published_parameter_index) >= 4
