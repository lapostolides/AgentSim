"""Tests for domain knowledge loader with caching and auto-detection."""

from __future__ import annotations

from agentsim.physics.domains import NLOS_KEYWORDS, detect_domain, load_domain


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
