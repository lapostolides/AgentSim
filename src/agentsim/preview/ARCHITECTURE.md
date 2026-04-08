# Scene Preview / Rendering

> Generates Blender-rendered preview images of NLOS scene geometry before simulation execution.

## Files

### __init__.py
Empty package init.

### scene_description.py
Frozen Pydantic models describing the complete geometry of an NLOS scene for visualization. These models are simulation-independent -- any experiment constructs a `SceneDescription` from its parameters.

**Core models:**
- `Vec3` -- 3D point/vector with `to_tuple()`.
- `Color` -- RGB color in [0, 1] range.
- `RelayWall` -- Position, size, albedo pattern (uniform/checker), normal direction.
- `Sensor` -- Position, look-at, FOV, laser target, show_laser toggle.
- `Occluder` -- Position, size, transparency toggle.
- `SphereObject`, `BoxObject`, `CylinderObject`, `CompoundObject` -- Hidden object primitives. `CompoundObject` joins multiple primitives.
- `HiddenObject` -- Union type of all object primitives.
- `CameraSettings` -- Camera position, look-at, lens focal length.
- `RenderSettings` -- Resolution, samples, denoising toggle.
- `SceneDescription` -- Top-level model combining all elements. Entry point for rendering.

### renderer.py
Invokes Blender headless to render a scene preview.

- `preview_scene(scene, output_path, blender_path?, timeout_seconds?)` -- Serializes the `SceneDescription` to a temporary JSON file, launches Blender with `--background --python blender_render.py`, and returns the output PNG path.
- `_find_blender()` -- Searches standard paths (`/Applications/Blender.app/...`, `which blender`).

Handles errors: Blender not found (FileNotFoundError), render timeout (TimeoutExpired), render failure (RuntimeError). Cleans up temporary JSON file in all cases.

### blender_render.py
Blender Python script executed headless. Reads the scene JSON and builds the 3D scene:

- **Scene elements**: relay wall (with optional checker pattern), sensor (body + lens + tripod), occluder (semi-transparent), hidden objects (sphere/box/cylinder/compound).
- **Light transport visualization**: laser beam (red emissive cylinder), three-bounce light paths (emissive arrows: wall->hidden, hidden->wall, wall->sensor).
- **Labels**: Text objects positioned above each element.
- **Lighting**: Three-point setup (key, fill, rim) plus a point light on hidden objects.
- **Camera**: Positioned via track-to constraint targeting a look-at point.
- **Rendering**: Cycles engine with configurable samples, denoising, and resolution.

## Data Flow

```
Experiment parameters
    |
    v
SceneDescription (frozen Pydantic model)
    |
    v
preview_scene()
    |-- serialize to temp JSON
    |-- subprocess: blender --background --python blender_render.py -- scene.json output.png
    |
    v
blender_render.py (inside Blender)
    |-- parse JSON
    |-- build geometry, materials, lighting, camera
    |-- bpy.ops.render.render(write_still=True)
    |
    v
output.png (rendered preview image)
```

## Key Patterns

- **Simulation-independent models**: `SceneDescription` is purely geometric -- it does not depend on simulation code or execution results.
- **Subprocess isolation**: Blender runs in a separate process. The render script uses Blender's Python API (`bpy`) which is only available inside Blender.
- **Material system**: Includes checker patterns, semi-transparent materials, and emissive materials for visualization overlays (laser, light paths, labels).

## Dependencies

- **Depends on**: `pydantic`, Blender (external, optional), `bpy` + `mathutils` (inside Blender process only).
- **Depended on by**: `orchestrator.runner` (renders previews at SCENE_VISUALIZATION gate), `cli.gates` (opens rendered images for review).
