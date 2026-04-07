"""Tests for domain knowledge loader with caching and auto-detection."""

from __future__ import annotations

from agentsim.physics.domains import NLOS_KEYWORDS, detect_domain, load_domain
from agentsim.physics.domains import detect_paradigm, load_paradigm, load_sensor_catalog
from agentsim.physics.domains.schema import ParadigmKnowledge, SensorCatalog


class TestLoadDomain:
    """Test domain YAML loading and caching."""

    def test_load_nlos_returns_domain_knowledge(self) -> None:
        """Test 1: load_domain returns DomainKnowledge with correct domain."""
        dk = load_domain("nlos_transient_imaging")
        assert dk is not None
        assert dk.domain == "nlos_transient_imaging"

    def test_load_nonexistent_returns_none(self) -> None:
        """Test 2: load_domain returns None for unknown domain."""
        result = load_domain("nonexistent_domain")
        assert result is None

    def test_load_domain_caches(self) -> None:
        """Test 3: Second call returns same cached object (identity)."""
        dk1 = load_domain("nlos_transient_imaging")
        dk2 = load_domain("nlos_transient_imaging")
        assert dk1 is dk2

    def test_load_domain_has_governing_equations(self) -> None:
        """Test 9: Loaded domain has non-empty governing_equations."""
        dk = load_domain("nlos_transient_imaging")
        assert dk is not None
        assert len(dk.governing_equations) > 0

    def test_load_domain_has_otoole_2018(self) -> None:
        """Test 10: Loaded domain has otoole_2018 in published_parameter_index."""
        dk = load_domain("nlos_transient_imaging")
        assert dk is not None
        assert "otoole_2018" in dk.published_parameter_index


class TestDetectDomain:
    """Test keyword-based domain auto-detection."""

    def test_detect_nlos_from_hypothesis(self) -> None:
        """Test 4: Detect NLOS from hypothesis with multiple keywords."""
        result = detect_domain("investigating NLOS transient imaging with relay wall")
        assert result == "nlos_transient_imaging"

    def test_detect_returns_none_for_unrelated(self) -> None:
        """Test 5: Returns None for non-NLOS hypothesis."""
        result = detect_domain("generic fluid dynamics simulation")
        assert result is None

    def test_single_keyword_not_enough(self) -> None:
        """Test 6: Single NLOS keyword returns None (threshold is 2+)."""
        result = detect_domain("studying transient phenomena in heat transfer")
        assert result is None

    def test_detect_multiple_keywords(self) -> None:
        """Test 7: Three keywords triggers detection."""
        result = detect_domain("confocal SPAD time-of-flight")
        assert result == "nlos_transient_imaging"


class TestNLOSKeywords:
    """Test NLOS_KEYWORDS frozenset."""

    def test_keywords_is_frozenset(self) -> None:
        """Test 8: NLOS_KEYWORDS is a frozenset with expected members."""
        assert isinstance(NLOS_KEYWORDS, frozenset)
        assert "nlos" in NLOS_KEYWORDS
        assert "relay wall" in NLOS_KEYWORDS
        assert "spad" in NLOS_KEYWORDS
        assert "transient" in NLOS_KEYWORDS


# ---------------------------------------------------------------------------
# Paradigm loader tests (Phase 02.1 Plan 02)
# ---------------------------------------------------------------------------


class TestLoadParadigm:
    """Test paradigm YAML loading and caching."""

    def test_load_relay_wall_returns_paradigm_knowledge(self) -> None:
        """Test 1: load_paradigm('relay_wall') returns ParadigmKnowledge."""
        pk = load_paradigm("relay_wall")
        assert pk is not None
        assert isinstance(pk, ParadigmKnowledge)
        assert pk.paradigm == "relay_wall"

    def test_load_penumbra_returns_paradigm_knowledge(self) -> None:
        """Test 2: load_paradigm('penumbra') returns ParadigmKnowledge."""
        pk = load_paradigm("penumbra")
        assert pk is not None
        assert isinstance(pk, ParadigmKnowledge)
        assert pk.paradigm == "penumbra"

    def test_load_nonexistent_returns_none(self) -> None:
        """Test 3: load_paradigm('nonexistent') returns None."""
        result = load_paradigm("nonexistent")
        assert result is None

    def test_load_paradigm_caches(self) -> None:
        """Test 4: Second call returns same cached object."""
        pk1 = load_paradigm("relay_wall")
        pk2 = load_paradigm("relay_wall")
        assert pk1 is pk2

    def test_relay_wall_has_validation_rules(self) -> None:
        """Relay wall paradigm has validation rules."""
        pk = load_paradigm("relay_wall")
        assert pk is not None
        assert len(pk.validation_rules) > 0


class TestDetectParadigm:
    """Test keyword-based paradigm auto-detection."""

    def test_detect_relay_wall(self) -> None:
        """Test 5: detect_paradigm identifies relay wall from hypothesis."""
        result = detect_paradigm("studying relay wall confocal NLOS imaging")
        assert result == "relay_wall"

    def test_detect_penumbra(self) -> None:
        """Test 6: detect_paradigm identifies penumbra from hypothesis."""
        result = detect_paradigm("penumbra shadow imaging around occluder edge")
        assert result == "penumbra"

    def test_detect_unrelated_returns_none(self) -> None:
        """Test 7: detect_paradigm returns None for unrelated text."""
        result = detect_paradigm("unrelated physics topic without keywords")
        assert result is None

    def test_detect_with_domain_filter(self) -> None:
        """Test 8: detect_paradigm with domain filters to NLOS paradigms."""
        result = detect_paradigm(
            "studying relay wall confocal three-bounce imaging",
            domain="nlos_transient_imaging",
        )
        assert result == "relay_wall"


class TestLoadSensorCatalog:
    """Test sensor catalog loading and caching."""

    def test_load_sensor_catalog_returns_catalog(self) -> None:
        """Test 9: load_sensor_catalog returns SensorCatalog with 3+ sensors."""
        catalog = load_sensor_catalog()
        assert catalog is not None
        assert isinstance(catalog, SensorCatalog)
        assert len(catalog.sensors) >= 3

    def test_load_sensor_catalog_caches(self) -> None:
        """Test 10: Second call returns same cached object."""
        cat1 = load_sensor_catalog()
        cat2 = load_sensor_catalog()
        assert cat1 is cat2


class TestRegressions:
    """Regression tests: existing functions still work after adding paradigm support."""

    def test_load_domain_still_works(self) -> None:
        """Test 11: Existing load_domain still returns DomainKnowledge."""
        dk = load_domain("nlos_transient_imaging")
        assert dk is not None
        assert dk.domain == "nlos_transient_imaging"

    def test_detect_domain_still_works(self) -> None:
        """Test 12: Existing detect_domain still works."""
        result = detect_domain("investigating NLOS transient imaging with relay wall")
        assert result == "nlos_transient_imaging"
