"""Domain knowledge system -- YAML-based physics domain definitions.

Provides lazy loading of domain knowledge files, caching parsed results,
and keyword-based domain auto-detection from hypothesis text.

Usage:
    from agentsim.physics.domains import load_domain, detect_domain

    knowledge = load_domain("nlos_transient_imaging")
    domain = detect_domain("studying NLOS relay wall transient imaging")
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agentsim.physics.domains.schema import DomainKnowledge

_DOMAINS_DIR = Path(__file__).parent
_CACHE: dict[str, DomainKnowledge] = {}

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
