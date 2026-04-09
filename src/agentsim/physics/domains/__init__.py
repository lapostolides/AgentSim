"""Domain knowledge system -- YAML-based physics domain definitions.

Provides lazy loading of domain knowledge files, caching parsed results,
keyword-based domain auto-detection from hypothesis text, and paradigm-level
knowledge loading with sensor catalog support.

The primary entry point is ``load_domain_bundle()`` which scans a
directory-per-domain layout and returns all resources (domain knowledge,
paradigms, sensor classes, sensor profiles, algorithms) as a single
``DomainBundle`` object.

Legacy loaders (``load_domain``, ``load_paradigm``, ``load_sensor_catalog``)
are still available and delegate to the bundle internally.

Usage:
    from agentsim.physics.domains import load_domain_bundle
    bundle = load_domain_bundle("nlos_transient_imaging")

    # Legacy (still works):
    from agentsim.physics.domains import load_domain, detect_domain
    from agentsim.physics.domains import load_paradigm, detect_paradigm, load_sensor_catalog
"""

from __future__ import annotations

import structlog
from pathlib import Path

import yaml

from agentsim.physics.domains.schema import (
    AlgorithmKnowledge,
    DomainBundle,
    DomainKnowledge,
    ParadigmKnowledge,
    SensorCatalog,
    SensorClass,
    SensorProfile,
)

logger = structlog.get_logger()

_DOMAINS_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

_CACHE: dict[str, DomainKnowledge] = {}
_PARADIGM_CACHE: dict[str, ParadigmKnowledge] = {}
_SENSOR_CACHE: SensorCatalog | None = None
_BUNDLE_CACHE: dict[str, DomainBundle] = {}

# Map domain identifiers to flat YAML filenames (legacy layout).
_DOMAIN_FILE_MAP: dict[str, str] = {
    "nlos_transient_imaging": "nlos",
    "lensless_imaging": "lensless_imaging",
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

LENSLESS_KEYWORDS: frozenset[str] = frozenset({
    "lensless",
    "diffuser",
    "diffusercam",
    "coded aperture",
    "psf",
    "mask",
    "computational camera",
    "wiener",
    "deconvolution",
})

# Minimum keyword score to confidently detect a paradigm.
_PARADIGM_DETECT_THRESHOLD = 2


# ---------------------------------------------------------------------------
# YAML loader helper
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return the raw dict."""
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Directory-per-domain loader
# ---------------------------------------------------------------------------


def load_domain_bundle(domain_name: str) -> DomainBundle | None:
    """Load a complete domain from its directory.

    Scans ``{domain_name}/`` for domain.yaml, paradigms/, sensors/,
    sensors/profiles/, and algorithms/. Returns a DomainBundle with
    all resources resolved. Caches on first load.

    Falls back to legacy flat layout if no directory exists.

    Args:
        domain_name: Domain identifier (e.g. "nlos_transient_imaging").

    Returns:
        DomainBundle if found, None otherwise.
    """
    if domain_name in _BUNDLE_CACHE:
        return _BUNDLE_CACHE[domain_name]

    domain_dir = _DOMAINS_DIR / domain_name
    if domain_dir.is_dir() and (domain_dir / "domain.yaml").exists():
        bundle = _load_bundle_from_directory(domain_name, domain_dir)
    else:
        # Fall back to legacy flat layout
        bundle = _load_bundle_from_flat(domain_name)

    if bundle is not None:
        _BUNDLE_CACHE[domain_name] = bundle
        # Populate legacy caches for backward compat
        _CACHE[domain_name] = bundle.domain
        for name, paradigm in bundle.paradigms.items():
            _PARADIGM_CACHE[name] = paradigm
    return bundle


def _load_bundle_from_directory(
    domain_name: str,
    domain_dir: Path,
) -> DomainBundle | None:
    """Load a DomainBundle from the directory-per-domain layout."""
    # 1. Domain knowledge
    raw = _load_yaml(domain_dir / "domain.yaml")
    domain = DomainKnowledge.model_validate(raw)

    # 2. Paradigms
    paradigms: dict[str, ParadigmKnowledge] = {}
    paradigms_dir = domain_dir / "paradigms"
    if paradigms_dir.is_dir():
        for p in sorted(paradigms_dir.glob("*.yaml")):
            pk = ParadigmKnowledge.model_validate(_load_yaml(p))
            paradigms[pk.paradigm] = pk

    # 3. Sensor classes (top-level YAML in sensors/, excluding profiles/)
    #    Also extract inline profiles from each class YAML (new format).
    sensor_classes: dict[str, SensorClass] = {}
    sensor_profiles: dict[str, SensorProfile] = {}
    sensors_dir = domain_dir / "sensors"
    if sensors_dir.is_dir():
        for p in sorted(sensors_dir.glob("*.yaml")):
            raw = _load_yaml(p)
            sc = SensorClass.model_validate(raw)  # Pydantic ignores extra 'profiles' key
            sensor_classes[sc.name] = sc

            # Extract inline profiles from the same YAML (new KG format)
            for profile_data in raw.get("profiles", []):
                sp = SensorProfile.model_validate(profile_data)
                key = sp.name.lower().replace(" ", "")
                sensor_profiles[key] = sp

    # 4. Sensor profiles — prefer inline, fall back to profiles/ directory
    profiles_dir = sensors_dir / "profiles" if sensors_dir.is_dir() else None
    if profiles_dir is not None and profiles_dir.is_dir():
        for p in sorted(profiles_dir.glob("*.yaml")):
            key = p.stem
            if key not in sensor_profiles:  # Don't overwrite inline
                sp = SensorProfile.model_validate(_load_yaml(p))
                sensor_profiles[key] = sp

    # 5. Algorithms
    algorithms: dict[str, AlgorithmKnowledge] = {}
    algos_dir = domain_dir / "algorithms"
    if algos_dir.is_dir():
        for p in sorted(algos_dir.glob("*.yaml")):
            ak = AlgorithmKnowledge.model_validate(_load_yaml(p))
            algorithms[ak.algorithm or p.stem] = ak

    logger.info(
        "domain_bundle_loaded",
        domain=domain_name,
        paradigms=len(paradigms),
        sensor_classes=len(sensor_classes),
        sensor_profiles=len(sensor_profiles),
        algorithms=len(algorithms),
    )

    return DomainBundle(
        domain=domain,
        paradigms=paradigms,
        sensor_classes=sensor_classes,
        sensor_profiles=sensor_profiles,
        algorithms=algorithms,
    )


def _load_bundle_from_flat(domain_name: str) -> DomainBundle | None:
    """Load a DomainBundle from the legacy flat layout (backward compat)."""
    dk = _load_domain_flat(domain_name)
    if dk is None:
        return None

    paradigms: dict[str, ParadigmKnowledge] = {}
    paradigms_dir = _DOMAINS_DIR / "paradigms"
    if paradigms_dir.is_dir():
        for p in sorted(paradigms_dir.glob("*.yaml")):
            pk = ParadigmKnowledge.model_validate(_load_yaml(p))
            if pk.domain == domain_name:
                paradigms[pk.paradigm] = pk

    sensor_profiles: dict[str, SensorProfile] = {}
    catalog = _load_sensor_catalog_flat()
    if catalog is not None:
        sensor_profiles = dict(catalog.sensors)

    return DomainBundle(
        domain=dk,
        paradigms=paradigms,
        sensor_classes={},
        sensor_profiles=sensor_profiles,
        algorithms={},
    )


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------


def get_compatible_algorithms(
    bundle: DomainBundle,
    paradigm: ParadigmKnowledge,
) -> tuple[AlgorithmKnowledge, ...]:
    """Return algorithms compatible with a paradigm."""
    return tuple(
        algo
        for algo in bundle.algorithms.values()
        if paradigm.paradigm in algo.compatible_paradigms
    )


def get_compatible_sensor_classes(
    bundle: DomainBundle,
    paradigm: ParadigmKnowledge,
) -> tuple[SensorClass, ...]:
    """Return sensor classes compatible with a paradigm."""
    if paradigm.compatible_sensor_classes:
        return tuple(
            sc
            for sc in bundle.sensor_classes.values()
            if sc.name in paradigm.compatible_sensor_classes
        )
    # Fall back to matching by sensor_type against compatible_sensor_types
    return tuple(
        sc
        for sc in bundle.sensor_classes.values()
        if sc.sensor_type in paradigm.compatible_sensor_types
    )


# ---------------------------------------------------------------------------
# Legacy loaders (backward compatible)
# ---------------------------------------------------------------------------


def load_domain(domain_name: str) -> DomainKnowledge | None:
    """Load and cache a domain knowledge YAML file.

    Prefers directory-per-domain layout, falls back to flat YAML.
    Returns None if the domain is not found. Caches on first load.

    Args:
        domain_name: Domain identifier (e.g. "nlos_transient_imaging").

    Returns:
        DomainKnowledge if found, None otherwise.
    """
    if domain_name in _CACHE:
        return _CACHE[domain_name]

    bundle = load_domain_bundle(domain_name)
    if bundle is not None:
        return bundle.domain

    # Direct flat lookup as last resort
    return _load_domain_flat(domain_name)


def _load_domain_flat(domain_name: str) -> DomainKnowledge | None:
    """Load domain from legacy flat YAML file."""
    if domain_name in _CACHE:
        return _CACHE[domain_name]

    file_stem = _DOMAIN_FILE_MAP.get(domain_name, domain_name)
    yaml_path = _DOMAINS_DIR / f"{file_stem}.yaml"
    if not yaml_path.exists():
        return None

    raw = _load_yaml(yaml_path)
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
    lensless_score = sum(1 for kw in LENSLESS_KEYWORDS if kw in text_lower)
    if lensless_score >= 2:
        return "lensless_imaging"
    return None


def load_paradigm(paradigm_name: str) -> ParadigmKnowledge | None:
    """Load and cache a paradigm knowledge YAML file.

    Checks bundle cache first, then tries both directory-per-domain
    and legacy flat layout.

    Args:
        paradigm_name: Paradigm identifier (e.g. "relay_wall", "penumbra").

    Returns:
        ParadigmKnowledge if found, None otherwise.
    """
    if paradigm_name in _PARADIGM_CACHE:
        return _PARADIGM_CACHE[paradigm_name]

    # Try loading via bundle (populates _PARADIGM_CACHE)
    for domain_name in _DOMAIN_FILE_MAP:
        bundle = load_domain_bundle(domain_name)
        if bundle is not None and paradigm_name in bundle.paradigms:
            return bundle.paradigms[paradigm_name]

    # Fall back to legacy flat path
    yaml_path = _DOMAINS_DIR / "paradigms" / f"{paradigm_name}.yaml"
    if not yaml_path.exists():
        return None

    raw = _load_yaml(yaml_path)
    paradigm = ParadigmKnowledge.model_validate(raw)
    _PARADIGM_CACHE[paradigm_name] = paradigm
    return paradigm


def detect_paradigm(
    hypothesis_text: str,
    domain: str | None = None,
) -> str | None:
    """Detect paradigm from hypothesis text via keyword matching.

    Scans paradigms from the domain bundle (or legacy paradigms/ directory),
    scores each by keyword overlap, and returns the best match if score >= 2.

    Args:
        hypothesis_text: Raw or formalized hypothesis text.
        domain: Optional domain to filter paradigms.

    Returns:
        Paradigm identifier string or None.
    """
    resolved_domain = domain
    if resolved_domain is None:
        resolved_domain = detect_domain(hypothesis_text)

    # Collect paradigms from bundle or legacy
    paradigms: list[ParadigmKnowledge] = []

    if resolved_domain is not None:
        bundle = load_domain_bundle(resolved_domain)
        if bundle is not None:
            paradigms = list(bundle.paradigms.values())

    # Fall back to legacy flat scanning
    if not paradigms:
        paradigms_dir = _DOMAINS_DIR / "paradigms"
        if paradigms_dir.is_dir():
            for yaml_file in sorted(paradigms_dir.glob("*.yaml")):
                pk = load_paradigm(yaml_file.stem)
                if pk is not None:
                    paradigms.append(pk)

    text_lower = hypothesis_text.lower()
    best_name: str | None = None
    best_score = 0

    for paradigm in paradigms:
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
    """Load sensor catalog — combines profiles from bundle and legacy.

    Returns:
        SensorCatalog if sensors found, None otherwise.
    """
    global _SENSOR_CACHE  # noqa: PLW0603
    if _SENSOR_CACHE is not None:
        return _SENSOR_CACHE

    # Try bundle first
    for domain_name in _DOMAIN_FILE_MAP:
        bundle = load_domain_bundle(domain_name)
        if bundle is not None and bundle.sensor_profiles:
            catalog = SensorCatalog(sensors=bundle.sensor_profiles)
            _SENSOR_CACHE = catalog
            return catalog

    # Fall back to flat
    return _load_sensor_catalog_flat()


def _load_sensor_catalog_flat() -> SensorCatalog | None:
    """Load sensor catalog from legacy flat sensors.yaml."""
    yaml_path = _DOMAINS_DIR / "sensors.yaml"
    if not yaml_path.exists():
        return None

    raw = _load_yaml(yaml_path)
    catalog = SensorCatalog.model_validate(raw)
    return catalog
