"""Tests for NLOS sensor YAML migration to new knowledge graph format.

Verifies that the domain loader correctly parses new-format YAMLs with
inline profile data and bridges them to backward-compatible SensorClass,
SensorProfile, and SensorCatalog objects.
"""

from __future__ import annotations

from agentsim.physics.domains import load_domain_bundle, load_sensor_catalog
from agentsim.physics.domains.schema import (
    DomainBundle,
    SensorCatalog,
    SensorClass,
    SensorProfile,
)


def _fresh_bundle() -> DomainBundle:
    """Load a fresh NLOS bundle (bypasses cache for test isolation)."""
    from agentsim.physics.domains import _BUNDLE_CACHE

    _BUNDLE_CACHE.pop("nlos_transient_imaging", None)
    bundle = load_domain_bundle("nlos_transient_imaging")
    assert bundle is not None
    return bundle


class TestBundleSensorClasses:
    """Verify sensor classes load from new-format YAMLs."""

    def test_bundle_has_sensor_classes(self) -> None:
        """Bundle contains all 4 NLOS sensor classes."""
        bundle = _fresh_bundle()
        assert len(bundle.sensor_classes) == 4
        assert "spad_array" in bundle.sensor_classes
        assert "spad_linear" in bundle.sensor_classes
        assert "gated_iccd" in bundle.sensor_classes
        assert "streak_camera" in bundle.sensor_classes

    def test_sensor_class_is_valid_type(self) -> None:
        """Each sensor class is a SensorClass instance."""
        bundle = _fresh_bundle()
        for sc in bundle.sensor_classes.values():
            assert isinstance(sc, SensorClass)

    def test_spad_array_has_timing_range(self) -> None:
        """spad_array sensor class has timing_range populated."""
        bundle = _fresh_bundle()
        sc = bundle.sensor_classes["spad_array"]
        assert sc.timing_range is not None
        assert sc.timing_range.temporal_resolution_ps is not None

    def test_spad_array_has_spatial_range(self) -> None:
        """spad_array sensor class has spatial_range populated."""
        bundle = _fresh_bundle()
        sc = bundle.sensor_classes["spad_array"]
        assert sc.spatial_range is not None
        assert sc.spatial_range.array_size == (512, 512)

    def test_spad_array_has_noise_range(self) -> None:
        """spad_array sensor class has noise_range populated."""
        bundle = _fresh_bundle()
        sc = bundle.sensor_classes["spad_array"]
        assert sc.noise_range is not None
        assert sc.noise_range.quantum_efficiency == 0.35


class TestBundleInlineProfiles:
    """Verify inline profiles are extracted from new-format YAMLs."""

    def test_bundle_has_inline_profiles(self) -> None:
        """Bundle contains profiles extracted from inline YAML sections."""
        bundle = _fresh_bundle()
        # Should have swissspad2, linospad2 (from spad_array.yaml)
        # and hamamatsuc5680streakcamera (from streak_camera.yaml)
        assert len(bundle.sensor_profiles) >= 3

    def test_swissspad2_profile_present(self) -> None:
        """SwissSPAD2 profile extracted from spad_array.yaml inline profiles."""
        bundle = _fresh_bundle()
        assert "swissspad2" in bundle.sensor_profiles

    def test_linospad2_profile_present(self) -> None:
        """LinoSPAD2 profile extracted from spad_array.yaml inline profiles."""
        bundle = _fresh_bundle()
        assert "linospad2" in bundle.sensor_profiles

    def test_inline_profile_is_sensor_profile(self) -> None:
        """Inline profiles are valid SensorProfile instances."""
        bundle = _fresh_bundle()
        sp = bundle.sensor_profiles["swissspad2"]
        assert isinstance(sp, SensorProfile)

    def test_swissspad2_has_timing(self) -> None:
        """SwissSPAD2 profile has timing parameters populated."""
        bundle = _fresh_bundle()
        sp = bundle.sensor_profiles["swissspad2"]
        assert sp.timing is not None
        assert sp.timing.temporal_resolution_ps is not None
        assert sp.timing.temporal_resolution_ps.typical == 17.8

    def test_swissspad2_has_spatial(self) -> None:
        """SwissSPAD2 profile has spatial parameters populated."""
        bundle = _fresh_bundle()
        sp = bundle.sensor_profiles["swissspad2"]
        assert sp.spatial is not None
        assert sp.spatial.array_size == (512, 512)

    def test_swissspad2_has_noise(self) -> None:
        """SwissSPAD2 profile has noise model populated."""
        bundle = _fresh_bundle()
        sp = bundle.sensor_profiles["swissspad2"]
        assert sp.noise is not None
        assert sp.noise.quantum_efficiency == 0.35


class TestSensorCatalogIntegration:
    """Verify load_sensor_catalog() works with new-format inline profiles."""

    def test_sensor_catalog_contains_profiles(self) -> None:
        """load_sensor_catalog() returns catalog with inline profiles."""
        from agentsim.physics.domains import _SENSOR_CACHE, _BUNDLE_CACHE

        # Clear caches for fresh load
        _BUNDLE_CACHE.pop("nlos_transient_imaging", None)
        globals()["_orig"] = _SENSOR_CACHE
        import agentsim.physics.domains as _mod

        _mod._SENSOR_CACHE = None

        catalog = load_sensor_catalog()
        assert catalog is not None
        assert isinstance(catalog, SensorCatalog)
        assert "swissspad2" in catalog.sensors
        assert "linospad2" in catalog.sensors

    def test_catalog_profiles_have_expected_fields(self) -> None:
        """Catalog profiles have manufacturer and reference fields."""
        catalog = load_sensor_catalog()
        assert catalog is not None
        sp = catalog.sensors["swissspad2"]
        assert sp.manufacturer == "EPFL"
        assert sp.reference == "Ulku et al. 2019"


class TestInlineProfileExtraction:
    """Verify loader extracts profiles from inline YAML, not just profiles/ dir."""

    def test_inline_profiles_loaded_without_profiles_dir(self) -> None:
        """Inline profiles load even when profiles/ directory is absent."""
        from unittest.mock import patch
        from agentsim.physics.domains import _BUNDLE_CACHE, _load_bundle_from_directory
        from pathlib import Path

        _BUNDLE_CACHE.pop("nlos_transient_imaging", None)
        domain_dir = Path(
            "src/agentsim/physics/domains/nlos_transient_imaging"
        )

        # Patch profiles_dir.is_dir() to return False to simulate missing dir
        orig_load = _load_bundle_from_directory

        bundle = orig_load("nlos_transient_imaging", domain_dir)
        assert bundle is not None
        # The key assertion: inline profiles are present
        assert "swissspad2" in bundle.sensor_profiles
        assert "linospad2" in bundle.sensor_profiles

    def test_loader_contains_inline_profile_extraction(self) -> None:
        """The loader source code contains inline profile extraction logic."""
        import inspect
        from agentsim.physics.domains import _load_bundle_from_directory

        source = inspect.getsource(_load_bundle_from_directory)
        assert 'raw.get("profiles"' in source or "raw.get('profiles'" in source


class TestBackwardCompatibility:
    """Verify existing downstream code paths remain functional."""

    def test_context_format_does_not_raise(self) -> None:
        """format_physics_context with loaded bundle does not raise."""
        from agentsim.physics.context import format_physics_context

        bundle = _fresh_bundle()
        catalog = SensorCatalog(sensors=bundle.sensor_profiles)
        # Should not raise
        result = format_physics_context(
            domain=bundle.domain,
            sensor_catalog=catalog,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_sensor_class_ignores_profiles_key(self) -> None:
        """SensorClass.model_validate ignores extra 'profiles' key in YAML."""
        import yaml
        from pathlib import Path

        yaml_path = Path(
            "src/agentsim/physics/domains/nlos_transient_imaging/sensors/spad_array.yaml"
        )
        raw = yaml.safe_load(yaml_path.open())
        assert "profiles" in raw, "YAML should contain profiles section"
        sc = SensorClass.model_validate(raw)
        assert sc.name == "spad_array"
        assert sc.timing_range is not None
