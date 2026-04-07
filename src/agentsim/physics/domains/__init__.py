"""Domain knowledge system -- YAML-based physics domain definitions.

Provides lazy loading of domain knowledge files, caching parsed results,
keyword-based domain auto-detection from hypothesis text, and paradigm-level
knowledge loading with sensor catalog support.

Usage:
    from agentsim.physics.domains import load_domain, detect_domain
    from agentsim.physics.domains import load_paradigm, detect_paradigm, load_sensor_catalog

    knowledge = load_domain("nlos_transient_imaging")
    domain = detect_domain("studying NLOS relay wall transient imaging")
    paradigm = load_paradigm("relay_wall")
    detected = detect_paradigm("relay wall confocal NLOS imaging")
    catalog = load_sensor_catalog()
"""

from __future__ import annotations

import structlog
from pathlib import Path

import yaml

from agentsim.physics.domains.schema import (
    DomainKnowledge,
    ParadigmKnowledge,
    SensorCatalog,
)

logger = structlog.get_logger()

_DOMAINS_DIR = Path(__file__).parent
_CACHE: dict[str, DomainKnowledge] = {}
_PARADIGM_CACHE: dict[str, ParadigmKnowledge] = {}
_SENSOR_CACHE: SensorCatalog | None = None

# Map domain identifiers to YAML filenames when they differ.
_DOMAIN_FILE_MAP: dict[str, str] = {
    "nlos_transient_imaging": "nlos",
}

NLOS_KEYWORDS: frozenset[str] = frozenset({
    "nlos",
    "non-line-of-sight",
    "transient",
    "relay wall",
    "spad",
    "time-of-flight",
    "three-bounce",
    "hidden object",
    "confocal",
    "light cone transform",
    "lct",
    "f-k migration",
    "phasor field",
    "reconstruction",
})

# Minimum keyword score to confidently detect a paradigm.
_PARADIGM_DETECT_THRESHOLD = 2


def load_domain(domain_name: str) -> DomainKnowledge | None:
    """Load and cache a domain knowledge YAML file.

    Looks for the corresponding YAML file in the domains directory,
    using ``_DOMAIN_FILE_MAP`` for name-to-filename translation.
    Returns None if the file does not exist. Caches on first load.

    Args:
        domain_name: Domain identifier (e.g. "nlos_transient_imaging").

    Returns:
        DomainKnowledge if found, None otherwise.
    """
    if domain_name in _CACHE:
        return _CACHE[domain_name]

    file_stem = _DOMAIN_FILE_MAP.get(domain_name, domain_name)
    yaml_path = _DOMAINS_DIR / f"{file_stem}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    knowledge = DomainKnowledge.model_validate(raw)
    _CACHE[domain_name] = knowledge
    return knowledge


def detect_domain(hypothesis_text: str, parameters: dict | None = None) -> str | None:
    """Detect physics domain from hypothesis text via keyword matching.

    Returns the domain identifier if 2+ keywords match. Returns None
    if no domain is confidently detected.

    Args:
        hypothesis_text: Raw or formalized hypothesis text.
        parameters: Optional parameter dict (reserved for future use).

    Returns:
        Domain identifier string or None.
    """
    text_lower = hypothesis_text.lower()
    nlos_score = sum(1 for kw in NLOS_KEYWORDS if kw in text_lower)
    if nlos_score >= 2:
        return "nlos_transient_imaging"
    # Future: ptychography, lensless, coded_aperture detection
    return None


# ---------------------------------------------------------------------------
# Paradigm-level loaders (Phase 02.1 Plan 02)
# ---------------------------------------------------------------------------


def load_paradigm(paradigm_name: str) -> ParadigmKnowledge | None:
    """Load and cache a paradigm knowledge YAML file.

    Looks for a YAML file at ``paradigms/{paradigm_name}.yaml`` within
    the domains directory. Returns None if the file does not exist.
    Caches on first successful load.

    Args:
        paradigm_name: Paradigm identifier (e.g. "relay_wall", "penumbra").

    Returns:
        ParadigmKnowledge if found, None otherwise.
    """
    if paradigm_name in _PARADIGM_CACHE:
        return _PARADIGM_CACHE[paradigm_name]

    yaml_path = _DOMAINS_DIR / "paradigms" / f"{paradigm_name}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    paradigm = ParadigmKnowledge.model_validate(raw)
    _PARADIGM_CACHE[paradigm_name] = paradigm
    return paradigm


def detect_paradigm(
    hypothesis_text: str,
    domain: str | None = None,
) -> str | None:
    """Detect paradigm from hypothesis text via keyword matching.

    Scans all paradigm YAML files in the paradigms/ directory, scores
    each by keyword overlap with the hypothesis text, and returns the
    paradigm with the highest score if it meets the threshold (2+).

    If ``domain`` is not provided, calls ``detect_domain`` first to
    narrow the search to paradigms belonging to a detected domain.

    Args:
        hypothesis_text: Raw or formalized hypothesis text.
        domain: Optional domain to filter paradigms (e.g. "nlos_transient_imaging").

    Returns:
        Paradigm identifier string or None.
    """
    resolved_domain = domain
    if resolved_domain is None:
        resolved_domain = detect_domain(hypothesis_text)

    paradigms_dir = _DOMAINS_DIR / "paradigms"
    if not paradigms_dir.exists():
        return None

    text_lower = hypothesis_text.lower()
    best_name: str | None = None
    best_score = 0

    for yaml_file in sorted(paradigms_dir.glob("*.yaml")):
        paradigm = load_paradigm(yaml_file.stem)
        if paradigm is None:
            continue
        # Filter by domain only when a domain constraint is known
        if resolved_domain is not None and paradigm.domain != resolved_domain:
            continue

        score = sum(1 for kw in paradigm.keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_name = paradigm.paradigm

    if best_score >= _PARADIGM_DETECT_THRESHOLD:
        return best_name
    return None


def load_sensor_catalog() -> SensorCatalog | None:
    """Load and cache the sensor catalog from sensors.yaml.

    Looks for ``sensors.yaml`` in the domains directory. Returns None
    if the file does not exist. Caches on first successful load.

    Returns:
        SensorCatalog if found, None otherwise.
    """
    global _SENSOR_CACHE  # noqa: PLW0603
    if _SENSOR_CACHE is not None:
        return _SENSOR_CACHE

    yaml_path = _DOMAINS_DIR / "sensors.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    catalog = SensorCatalog.model_validate(raw)
    _SENSOR_CACHE = catalog
    return catalog
