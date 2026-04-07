"""Tests for the curated physical constants registry.

Verifies NIST values, computational imaging constants, parameter ranges,
and that all constant units are valid Pint strings.
"""

from __future__ import annotations

import pytest

from agentsim.physics.constants import (
    COMPUTATIONAL_IMAGING,
    PARAMETER_RANGES,
    UNIVERSAL,
    get_parameter_range,
    list_constants,
    list_domains,
    lookup_constant,
)
from agentsim.physics.models import PhysicalConstant, _ureg


# -- UNIVERSAL registry --

class TestUniversalConstants:
    def test_has_at_least_six_entries(self) -> None:
        assert len(UNIVERSAL) >= 6

    def test_speed_of_light(self) -> None:
        c = lookup_constant("speed_of_light")
        assert c is not None
        assert c.magnitude == 299792458.0
        assert c.unit == "meter / second"
        assert c.symbol == "c"

    def test_boltzmann(self) -> None:
        k = lookup_constant("boltzmann")
        assert k is not None
        assert k.magnitude == pytest.approx(1.380649e-23)

    def test_planck(self) -> None:
        h = lookup_constant("planck")
        assert h is not None
        assert h.magnitude == pytest.approx(6.62607015e-34)

    def test_gravitational_acceleration(self) -> None:
        g = lookup_constant("gravitational_acceleration")
        assert g is not None
        assert g.magnitude == pytest.approx(9.80665)

    def test_stefan_boltzmann(self) -> None:
        s = lookup_constant("stefan_boltzmann")
        assert s is not None
        assert s.magnitude == pytest.approx(5.670374419e-8)

    def test_vacuum_permittivity(self) -> None:
        e = lookup_constant("vacuum_permittivity")
        assert e is not None
        assert e.magnitude == pytest.approx(8.8541878128e-12)


# -- COMPUTATIONAL_IMAGING registry --

class TestComputationalImagingConstants:
    def test_solar_irradiance(self) -> None:
        si = lookup_constant("solar_irradiance")
        assert si is not None
        assert si.magnitude == pytest.approx(1361.0)
        assert si.domain == "computational_imaging"

    def test_has_radiometry_entries(self) -> None:
        assert "solar_irradiance" in COMPUTATIONAL_IMAGING
        assert "typical_scene_radiance" in COMPUTATIONAL_IMAGING

    def test_has_geometric_optics_entries(self) -> None:
        assert "typical_focal_length" in COMPUTATIONAL_IMAGING
        assert "typical_f_number" in COMPUTATIONAL_IMAGING

    def test_has_wave_optics_entries(self) -> None:
        assert "visible_min_wavelength" in COMPUTATIONAL_IMAGING
        assert "visible_max_wavelength" in COMPUTATIONAL_IMAGING

    def test_has_sensor_entries(self) -> None:
        assert "typical_pixel_pitch" in COMPUTATIONAL_IMAGING
        assert "typical_read_noise" in COMPUTATIONAL_IMAGING
        assert "typical_full_well" in COMPUTATIONAL_IMAGING


# -- lookup_constant --

class TestLookupConstant:
    def test_nonexistent_returns_none(self) -> None:
        assert lookup_constant("nonexistent") is None

    def test_universal_checked_first(self) -> None:
        c = lookup_constant("speed_of_light")
        assert c is not None
        assert c.domain == "universal"

    def test_imaging_fallback(self) -> None:
        si = lookup_constant("solar_irradiance")
        assert si is not None
        assert si.domain == "computational_imaging"


# -- get_parameter_range --

class TestGetParameterRange:
    def test_wavelength_computational_imaging(self) -> None:
        r = get_parameter_range("wavelength", "computational_imaging")
        assert r is not None
        min_val, max_val, unit = r
        assert min_val == pytest.approx(1e-9)
        assert max_val == pytest.approx(1e-3)
        assert unit == "meter"

    def test_temperature_universal(self) -> None:
        r = get_parameter_range("temperature")
        assert r is not None
        min_val, max_val, unit = r
        assert min_val == pytest.approx(0.0)
        assert unit == "kelvin"

    def test_nonexistent_returns_none(self) -> None:
        assert get_parameter_range("nonexistent") is None

    def test_fallback_to_universal(self) -> None:
        # velocity is in universal, not computational_imaging
        r = get_parameter_range("velocity", "computational_imaging")
        assert r is not None


# -- PARAMETER_RANGES structure --

class TestParameterRanges:
    def test_has_universal_key(self) -> None:
        assert "universal" in PARAMETER_RANGES

    def test_has_computational_imaging_key(self) -> None:
        assert "computational_imaging" in PARAMETER_RANGES

    def test_universal_has_entries(self) -> None:
        assert len(PARAMETER_RANGES["universal"]) >= 4

    def test_computational_imaging_has_entries(self) -> None:
        assert len(PARAMETER_RANGES["computational_imaging"]) >= 5


# -- list_domains and list_constants --

class TestListFunctions:
    def test_list_domains(self) -> None:
        domains = list_domains()
        assert "universal" in domains
        assert "computational_imaging" in domains

    def test_list_constants_all(self) -> None:
        names = list_constants()
        assert "speed_of_light" in names
        assert "solar_irradiance" in names

    def test_list_constants_filtered(self) -> None:
        names = list_constants(domain="universal")
        assert "speed_of_light" in names
        assert "solar_irradiance" not in names


# -- Pint unit validation for all constants --

class TestAllConstantsPintValid:
    @pytest.mark.parametrize(
        "name,constant",
        list(UNIVERSAL.items()) + list(COMPUTATIONAL_IMAGING.items()),
    )
    def test_valid_pint_unit(self, name: str, constant: PhysicalConstant) -> None:
        """Every PhysicalConstant in the registry must have a valid Pint unit."""
        q = _ureg.Quantity(constant.magnitude, constant.unit)
        assert q is not None, f"Failed to create Quantity for {name}"
