"""Tests for Mitsuba 3 + mitransient availability detection and context formatting."""

from __future__ import annotations

from agentsim.physics.mitsuba_detection import (
    format_mitsuba_scene_context,
    has_mitsuba_transient,
)
from agentsim.state.models import AvailablePackage, EnvironmentInfo


def _make_env(*package_names: str) -> EnvironmentInfo:
    """Create an EnvironmentInfo with the given package names."""
    packages = tuple(
        AvailablePackage(name=name, version="1.0.0", import_name=name)
        for name in package_names
    )
    return EnvironmentInfo(packages=packages, python_version="3.12.1")


class TestHasMitsubaTransient:
    """Tests for has_mitsuba_transient detection function."""

    def test_both_present_returns_true(self) -> None:
        env = _make_env("mitsuba", "mitransient", "numpy")
        assert has_mitsuba_transient(env) is True

    def test_only_mitsuba_returns_false(self) -> None:
        env = _make_env("mitsuba", "numpy")
        assert has_mitsuba_transient(env) is False

    def test_only_mitransient_returns_false(self) -> None:
        env = _make_env("mitransient", "numpy")
        assert has_mitsuba_transient(env) is False

    def test_neither_present_returns_false(self) -> None:
        env = _make_env("numpy", "scipy")
        assert has_mitsuba_transient(env) is False

    def test_empty_packages_returns_false(self) -> None:
        env = EnvironmentInfo(packages=(), python_version="3.12.1")
        assert has_mitsuba_transient(env) is False


class TestFormatMitsubaSceneContext:
    """Tests for format_mitsuba_scene_context output."""

    def test_mitsuba_path_contains_mitsuba3(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "Mitsuba 3" in context

    def test_mitsuba_path_contains_mitransient(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "mitransient" in context

    def test_mitsuba_path_contains_llvm_ad_rgb(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "llvm_ad_rgb" in context

    def test_mitsuba_path_contains_np_save(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "np.save" in context

    def test_mitsuba_path_import_order_variant_before_mitransient(self) -> None:
        """Pitfall 2: mi.set_variant must come before import mitransient."""
        context = format_mitsuba_scene_context(has_mitsuba=True)
        variant_pos = context.index("mi.set_variant")
        mitransient_pos = context.index("import mitransient")
        assert variant_pos < mitransient_pos, (
            "mi.set_variant must appear before import mitransient"
        )

    def test_mitsuba_path_contains_set_variant_warning(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "do NOT" in context or "do not" in context.lower()

    def test_mitsuba_path_contains_spp_256(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=True)
        assert "spp" in context.lower() or "256" in context

    def test_numpy_path_contains_numpy(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=False)
        assert "numpy" in context.lower() or "Numpy" in context

    def test_numpy_path_contains_approximate(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=False)
        assert "approximate" in context.lower()

    def test_numpy_path_contains_npy(self) -> None:
        context = format_mitsuba_scene_context(has_mitsuba=False)
        assert ".npy" in context


class TestDiscoveryIntegration:
    """Test that mitransient is in KNOWN_SIMULATION_PACKAGES."""

    def test_mitransient_in_known_packages(self) -> None:
        from agentsim.environment.discovery import KNOWN_SIMULATION_PACKAGES

        assert "mitransient" in KNOWN_SIMULATION_PACKAGES
        assert KNOWN_SIMULATION_PACKAGES["mitransient"] == "mitransient"
