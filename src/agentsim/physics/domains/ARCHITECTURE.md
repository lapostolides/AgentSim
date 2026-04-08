# Domain Knowledge System

> YAML-based physics domain definitions with lazy loading, caching, keyword-based auto-detection, and a directory-per-domain file layout.

## Files

### __init__.py
Package entry point with all loaders and detectors. Key public API:

- `load_domain_bundle(domain_name)` -- Primary loader. Returns a `DomainBundle` containing domain knowledge, paradigms, sensor classes, sensor profiles, and algorithms. Cached on first load.
- `load_domain(domain_name)` -- Legacy loader, returns `DomainKnowledge` only.
- `detect_domain(hypothesis_text)` -- Keyword matching against `NLOS_KEYWORDS` and `LENSLESS_KEYWORDS`. Returns domain identifier if 2+ keywords match.
- `detect_paradigm(hypothesis_text, domain)` -- Scores paradigms by keyword overlap against hypothesis text. Returns best match if score >= 2.
- `load_paradigm(paradigm_name)` -- Loads a single paradigm by name.
- `load_sensor_catalog()` -- Loads sensor profiles from bundle or legacy flat file.
- `get_compatible_algorithms(bundle, paradigm)` -- Filters algorithms by paradigm compatibility.
- `get_compatible_sensor_classes(bundle, paradigm)` -- Filters sensor classes by paradigm compatibility.

Caches: `_CACHE` (domains), `_PARADIGM_CACHE` (paradigms), `_SENSOR_CACHE` (catalog), `_BUNDLE_CACHE` (bundles).

### schema.py
Frozen Pydantic models defining the YAML schema. All models use `frozen=True`. Organized into layers:

**Core domain models:**
- `DomainKnowledge` -- Top-level: governing equations, geometry constraints, sensor parameters, reconstruction algorithms, published parameters, dimensionless groups, transfer functions.
- `GoverningEquation` -- Name, LaTeX, description, variable definitions.
- `DimensionlessGroup` -- Name, formula, description.
- `GeometryConstraint` / `GeometryConstraintRule` -- Structured geometry rules.
- `ReconstructionAlgorithm` -- Algorithm with reference, confocal requirement, resolution, frequency constraint.
- `PublishedParameterSet` -- Parameters from published papers.

**Paradigm models:**
- `ParadigmKnowledge` -- Paradigm-level knowledge: keywords for detection, compatible sensor types/classes/algorithms, geometry constraints, validation rules, transfer functions, published baselines.
- `TransferFunction` -- Computable physics relationship (input -> output with relationship type and formula).
- `ValidationRule` -- Declarative (`range_check`, `threshold_check`) or Python-reference (`python_check`) validation rule.

**Sensor models (two-tier architecture):**
- `SensorClass` -- Class-level description (e.g., "research-grade SPAD arrays"). Agents reason at this level by default.
- `SensorProfile` -- Specific hardware model with full characterization (timing, spatial, noise, operational modes).
- `SensorCatalog` -- Collection of named sensor profiles.
- `TimingParameters`, `SpatialParameters`, `NoiseModel`, `OperationalMode` -- Component models.

**Algorithm model:**
- `AlgorithmKnowledge` -- First-class algorithm resource with paradigm and sensor class compatibility declarations.

**Bundle model:**
- `DomainBundle` -- Complete loaded domain: `DomainKnowledge` + all paradigms, sensor classes, sensor profiles, and algorithms.

## YAML Directory Layout

```
domains/
  nlos_transient_imaging/          # Directory-per-domain (preferred)
    domain.yaml                    # DomainKnowledge
    paradigms/
      relay_wall.yaml              # ParadigmKnowledge
      penumbra.yaml
    sensors/
      spad_array.yaml              # SensorClass
      spad_linear.yaml
      streak_camera.yaml
      gated_iccd.yaml
      profiles/
        swissspad2.yaml            # SensorProfile
        linospad2.yaml
        hamamatsu_c5680.yaml
    algorithms/
      lct.yaml                     # AlgorithmKnowledge
      fk_migration.yaml
      phasor_fields.yaml
  lensless_imaging/                # Another domain
    domain.yaml
    paradigms/
    sensors/
    algorithms/
  nlos.yaml                        # Legacy flat layout (backward compat)
  sensors.yaml                     # Legacy flat sensor catalog
  paradigms/                       # Legacy flat paradigm files
    relay_wall.yaml
    penumbra.yaml
```

## Domain Detection Flow

```
hypothesis_text
    |
    v
detect_domain()       -- keyword matching (NLOS_KEYWORDS, LENSLESS_KEYWORDS)
    |                     returns domain_name if score >= 2
    v
detect_paradigm()     -- loads paradigm YAMLs, scores each by keyword overlap
    |                     returns paradigm_name if best score >= 2
    v
load_domain_bundle()  -- scans domain directory, loads all resources
    |
    v
DomainBundle (domain + paradigms + sensors + algorithms)
```

## How to Add a New Domain

1. Create a directory: `domains/{domain_name}/`
2. Add `domain.yaml` with `DomainKnowledge` schema (governing equations, dimensionless groups, etc.).
3. Add paradigm YAMLs in `paradigms/` with keywords for auto-detection.
4. Add sensor class YAMLs in `sensors/` and profiles in `sensors/profiles/`.
5. Add algorithm YAMLs in `algorithms/` with `compatible_paradigms` and `compatible_sensor_classes`.
6. Add keyword set to `__init__.py` (like `NLOS_KEYWORDS`) for domain detection.
7. Add domain mapping to `_DOMAIN_FILE_MAP` for legacy fallback.

No Python code changes needed beyond keywords -- the loader scans directories automatically.

## Key Patterns

- **Directory-per-domain**: Each domain is self-contained in its own directory. The loader scans `domain.yaml`, `paradigms/`, `sensors/`, `sensors/profiles/`, and `algorithms/` automatically.
- **Legacy fallback**: Flat YAML files (`nlos.yaml`, `sensors.yaml`, `paradigms/*.yaml`) are still supported for backward compatibility.
- **Lazy loading with caching**: Domain bundles are loaded on first access and cached in module-level dicts.
- **Two-tier sensor architecture**: `SensorClass` for reasoning (capabilities, tradeoffs); `SensorProfile` for code generation (exact specs).

## Dependencies

- **Depends on**: `pydantic`, `pyyaml`, `structlog`.
- **Depended on by**: `physics.checker` (paradigm checks), `physics.context` (prompt formatting), `physics.reasoning` (optimizer, explorer), `physics.consultation` (reasoning query routing).
