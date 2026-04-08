# Environment Discovery

> Probes the Python environment to detect available simulation packages without importing them.

## Files

### __init__.py
Empty package init.

### discovery.py
Discovers what simulation packages are available in the current Python environment. Uses `importlib.util.find_spec()` for lightweight detection (no actual imports, no side effects) and `importlib.metadata.version()` for version retrieval.

**Known packages** (`KNOWN_SIMULATION_PACKAGES` dict, 15 entries):
mitsuba, blender (bpy), carla, pybullet, trimesh, open3d, pyglet, pyvista, vtk, opencv (cv2), scipy, numpy, matplotlib, pillow (PIL), scikit-image (skimage).

**Public API:**

- `discover_environment(extra_packages?)` -- Probes all known packages (plus any extras), returns `EnvironmentInfo` with `packages: tuple[AvailablePackage, ...]` and `python_version: str`. Logs each found package via structlog.

- `format_environment_for_prompt(env)` -- Formats `EnvironmentInfo` as a human-readable string for agent prompts, listing available packages with versions and import names.

## Data Flow

```
discover_environment()
    |
    v  for each known + extra package:
_check_package(import_name)
    |-- importlib.util.find_spec()  -- is it importable?
    |-- importlib.metadata.version() -- what version?
    |
    v
EnvironmentInfo(packages, python_version)
    |
    v
format_environment_for_prompt()  -- Markdown for agent context
```

## Key Patterns

- **No actual imports**: Uses `find_spec` to avoid triggering package initialization side effects (important for heavy packages like Blender or Mitsuba).
- **Extensible**: `extra_packages` parameter allows callers to add custom package checks.

## Dependencies

- **Depends on**: `importlib` (stdlib), `structlog`, `state.models` (AvailablePackage, EnvironmentInfo).
- **Depended on by**: `orchestrator.runner` (discovers environment at experiment start, injects into agent prompts).
