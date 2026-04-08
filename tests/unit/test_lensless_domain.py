"""Tests for lensless imaging domain detection, loading, and compatibility."""

from __future__ import annotations

import pytest

from agentsim.physics.domains import (
    detect_domain,
    detect_paradigm,
    get_compatible_algorithms,
    get_compatible_sensor_classes,
    load_domain_bundle,
)


class TestDetectDomain:
    """Domain detection via keyword matching."""

    def test_lensless_diffuser_imaging(self) -> None:
        result = detect_domain("lensless diffuser imaging")
        assert result == "lensless_imaging"

    def test_diffusercam_psf_reconstruction(self) -> None:
        result = detect_domain("diffusercam psf reconstruction")
        assert result == "lensless_imaging"

    def test_nlos_relay_wall_no_regression(self) -> None:
        result = detect_domain("relay wall NLOS")
        assert result == "nlos_transient_imaging"

    def test_unrelated_hypothesis_returns_none(self) -> None:
        result = detect_domain("unrelated hypothesis about fluid dynamics")
        assert result is None


class TestDetectParadigm:
    """Paradigm detection for lensless imaging."""

    def test_diffusercam_paradigm(self) -> None:
        result = detect_paradigm(
            "diffusercam lensless",
            domain="lensless_imaging",
        )
        assert result == "diffusercam"


class TestLoadDomainBundle:
    """Loading and querying the lensless imaging bundle."""

    @pytest.fixture()
    def bundle(self):
        b = load_domain_bundle("lensless_imaging")
        assert b is not None
        return b

    def test_paradigm_transfer_functions(self, bundle) -> None:
        paradigm = bundle.paradigms["diffusercam"]
        assert len(paradigm.transfer_functions) >= 2

    def test_algorithm_compatible_paradigms(self, bundle) -> None:
        algo = bundle.algorithms["wiener_deconv"]
        assert "diffusercam" in algo.compatible_paradigms

    def test_get_compatible_algorithms(self, bundle) -> None:
        paradigm = bundle.paradigms["diffusercam"]
        algos = get_compatible_algorithms(bundle, paradigm)
        algo_names = [a.algorithm for a in algos]
        assert "wiener_deconv" in algo_names

    def test_get_compatible_sensor_classes(self, bundle) -> None:
        paradigm = bundle.paradigms["diffusercam"]
        sensors = get_compatible_sensor_classes(bundle, paradigm)
        sensor_names = [s.name for s in sensors]
        assert "cmos_array" in sensor_names
