"""Blender script — invoked headless to render an NLOS scene preview.

Usage (called by renderer.py, not directly):
  blender --background --python blender_render.py -- scene.json output.png

Reads a SceneDescription JSON file and produces a rendered PNG showing
the relay wall, sensor, occluder, and hidden objects.
"""

import json
import math
import sys

import bpy
from mathutils import Vector


# ── Parse CLI args after "--" ────────────────────────────────────────

def _parse_args():
    argv = sys.argv
    separator = argv.index("--") if "--" in argv else len(argv)
    args = argv[separator + 1:]
    if len(args) < 2:
        raise SystemExit("Usage: blender --background --python blender_render.py -- scene.json output.png")
    return args[0], args[1]


SCENE_JSON_PATH, OUTPUT_PATH = _parse_args()

with open(SCENE_JSON_PATH) as f:
    SCENE = json.load(f)


# ── Helpers ──────────────────────────────────────────────────────────

def v3(d):
    """Convert a dict with x/y/z keys to a Vector."""
    return Vector((d["x"], d["y"], d["z"]))


def rgb(d):
    """Convert a dict with r/g/b keys to a tuple."""
    return (d["r"], d["g"], d["b"])


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def make_material(name, color, roughness=0.5, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def make_checker_material(name, block_size, res=32):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for node in nodes:
        nodes.remove(node)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    bsdf.inputs["Roughness"].default_value = 0.85
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    checker = nodes.new('ShaderNodeTexChecker')
    checker.location = (0, 0)
    checker.inputs["Scale"].default_value = res / block_size
    checker.inputs["Color1"].default_value = (0.85, 0.85, 0.85, 1.0)
    checker.inputs["Color2"].default_value = (0.15, 0.15, 0.15, 1.0)
    links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])

    texcoord = nodes.new('ShaderNodeTexCoord')
    texcoord.location = (-200, 0)
    links.new(texcoord.outputs["UV"], checker.inputs["Vector"])
    return mat


def make_semitransparent_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for node in nodes:
        nodes.remove(node)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)
    mix = nodes.new('ShaderNodeMixShader')
    mix.location = (400, 0)
    mix.inputs["Fac"].default_value = 0.6
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    diffuse = nodes.new('ShaderNodeBsdfPrincipled')
    diffuse.location = (200, 100)
    diffuse.inputs["Base Color"].default_value = (*color, 1.0)
    diffuse.inputs["Roughness"].default_value = 0.8
    links.new(diffuse.outputs["BSDF"], mix.inputs[1])

    transparent = nodes.new('ShaderNodeBsdfTransparent')
    transparent.location = (200, -100)
    transparent.inputs["Color"].default_value = (*color, 1.0)
    links.new(transparent.outputs["BSDF"], mix.inputs[2])
    return mat


def orient_cylinder(obj, start, end):
    """Orient a cylinder to span from start to end."""
    direction = (end - start).normalized()
    rot_quat = Vector((0, 0, 1)).rotation_difference(direction)
    obj.rotation_euler = rot_quat.to_euler()


def add_label(text, location, size=0.09, color=(1, 1, 1)):
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = 'CENTER'
    obj.name = f"Label_{text.replace(' ', '_')}"
    obj.rotation_euler = (math.radians(70), 0, math.radians(-35))
    mat = make_material(f"TextMat_{text}", color, emission=3.0)
    obj.data.materials.append(mat)


# ── Scene element builders ───────────────────────────────────────────

def build_relay_wall(wall_cfg):
    pos = v3(wall_cfg["position"])
    size = wall_cfg["size"]

    bpy.ops.mesh.primitive_plane_add(
        size=size,
        location=pos,
        rotation=(math.pi / 2, 0, 0),
    )
    wall = bpy.context.active_object
    wall.name = "RelayWall"

    pattern = wall_cfg.get("albedo_pattern", "uniform")
    if pattern == "checker":
        bs = wall_cfg.get("albedo_block_size", 4)
        mat = make_checker_material("WallAlbedo", bs)
    else:
        c = rgb(wall_cfg["color"])
        mat = make_material("WallMat", c, roughness=0.85)

    wall.data.materials.append(mat)
    return wall


def build_sensor(sensor_cfg):
    pos = v3(sensor_cfg["position"])

    # Body
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    body = bpy.context.active_object
    body.name = "SensorBody"
    body.scale = (0.12, 0.08, 0.10)

    # Lens barrel
    lens_pos = pos + Vector((0, 0.06, 0))
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.04, depth=0.06, location=lens_pos,
        rotation=(math.pi / 2, 0, 0),
    )
    lens = bpy.context.active_object
    lens.name = "SensorLens"

    # Tripod
    legs = []
    offsets = [(-0.08, 0, 0), (0.08, 0, 0), (0, 0.06, 0)]
    for i, (dx, dy, dz) in enumerate(offsets):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.008, depth=0.7,
            location=(pos.x + dx, pos.y + dy, pos.z - 0.40),
        )
        legs.append(bpy.context.active_object)

    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    lens.select_set(True)
    for leg in legs:
        leg.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()

    sensor = bpy.context.active_object
    sensor.name = "Sensor"
    c = rgb(sensor_cfg["color"])
    sensor.data.materials.append(make_material("SensorMat", c, roughness=0.15))
    return sensor


def build_occluder(occ_cfg):
    pos = v3(occ_cfg["position"])
    sz = v3(occ_cfg["size"])

    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    occ = bpy.context.active_object
    occ.name = "Occluder"
    occ.scale = (sz.x / 2, sz.y / 2, sz.z / 2)

    c = rgb(occ_cfg["color"])
    if occ_cfg.get("transparent", True):
        mat = make_semitransparent_material("OccluderMat", c)
    else:
        mat = make_material("OccluderMat", c, roughness=0.8)
    occ.data.materials.append(mat)
    return occ


def _build_compound(obj_cfg, color, label):
    """Build a compound object by joining its parts."""
    parts_list = []
    for part in obj_cfg.get("parts", []):
        built = build_hidden_object(part)
        if built:
            parts_list.append(built)
    if not parts_list:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts_list:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts_list[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = label or "HiddenCompound"
    obj.data.materials.clear()
    obj.data.materials.append(make_material(f"{obj.name}Mat", color, roughness=0.35))
    return obj


def build_hidden_object(obj_cfg):
    """Build a hidden object from its description dict."""
    kind = obj_cfg.get("kind", "box")
    c = rgb(obj_cfg.get("color", {"r": 0.5, "g": 0.5, "b": 0.5}))
    label = obj_cfg.get("label", "")

    # Compound objects don't have a top-level position
    if kind == "compound":
        return _build_compound(obj_cfg, c, label)

    pos = v3(obj_cfg["position"])

    if kind == "sphere":
        radius = obj_cfg.get("radius", 0.12)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius, location=pos, segments=48, ring_count=24)
        obj = bpy.context.active_object
        obj.name = label or "HiddenSphere"
        obj.data.materials.append(make_material(f"{obj.name}Mat", c, roughness=0.25))

    elif kind == "box":
        sz = v3(obj_cfg.get("size", {"x": 0.2, "y": 0.2, "z": 0.2}))
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        obj = bpy.context.active_object
        obj.name = label or "HiddenBox"
        obj.scale = (sz.x / 2, sz.y / 2, sz.z / 2)
        obj.data.materials.append(make_material(f"{obj.name}Mat", c, roughness=0.35))

    elif kind == "cylinder":
        radius = obj_cfg.get("radius", 0.1)
        height = obj_cfg.get("height", 0.3)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius, depth=height, location=pos)
        obj = bpy.context.active_object
        obj.name = label or "HiddenCylinder"
        obj.data.materials.append(make_material(f"{obj.name}Mat", c, roughness=0.30))

    else:
        return None

    return obj


def build_laser_beam(sensor_cfg):
    """Red laser beam from sensor to target point on wall."""
    start = v3(sensor_cfg["position"]) + Vector((0, 0.10, 0))
    end = v3(sensor_cfg.get("laser_target", {"x": 0, "y": 0, "z": 0}))
    mid = (start + end) / 2
    length = (end - start).length

    bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=length, location=mid)
    beam = bpy.context.active_object
    beam.name = "LaserBeam"
    orient_cylinder(beam, start, end)
    beam.data.materials.append(make_material("LaserMat", (1, 0, 0), emission=15))
    return beam


def build_light_path(start, end, name, color):
    """Emissive arrow showing a light transport segment."""
    mid = (start + end) / 2
    length = (end - start).length
    direction = (end - start).normalized()

    bpy.ops.mesh.primitive_cylinder_add(radius=0.005, depth=length, location=mid)
    shaft = bpy.context.active_object
    shaft.name = name
    orient_cylinder(shaft, start, end)
    mat = make_material(f"{name}Mat", color, emission=8)
    shaft.data.materials.append(mat)

    bpy.ops.mesh.primitive_cone_add(
        radius1=0.02, depth=0.05,
        location=end - direction * 0.025)
    arrow = bpy.context.active_object
    arrow.name = f"{name}_Arrow"
    orient_cylinder(arrow, start, end)
    arrow.data.materials.append(mat)


def build_light_paths(sensor_cfg, wall_cfg, hidden_objects):
    """Show the multi-bounce NLOS light transport."""
    wall_hit = v3(sensor_cfg.get("laser_target", {"x": 0.2, "y": 0, "z": 0.15}))

    # Pick the first hidden object as the bounce target
    if hidden_objects:
        first = hidden_objects[0]
        if first.get("kind") == "compound" and "parts" in first and first["parts"]:
            hidden_pos = v3(first["parts"][0]["position"])
        elif "position" in first:
            hidden_pos = v3(first["position"])
        else:
            hidden_pos = v3(wall_cfg["position"]) + Vector((0, 1.0, 0))
    else:
        hidden_pos = v3(wall_cfg["position"]) + Vector((0, 1.0, 0))

    wall_return = wall_hit + Vector((-0.4, 0, -0.2))
    sensor_pos = v3(sensor_cfg["position"]) + Vector((0, 0.10, 0))

    build_light_path(wall_hit, hidden_pos, "PathToHidden", (1.0, 0.85, 0.0))
    build_light_path(hidden_pos, wall_return, "PathFromHidden", (1.0, 0.65, 0.0))
    build_light_path(wall_return, sensor_pos, "PathToSensor", (0.0, 0.8, 0.2))


def build_floor():
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0.5, -1.01))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(make_material("FloorMat", (0.12, 0.12, 0.14), roughness=0.95))


def build_labels(sensor_cfg, wall_cfg, occ_cfg, hidden_objects):
    wall_pos = v3(wall_cfg["position"])
    wall_size = wall_cfg["size"]
    sensor_pos = v3(sensor_cfg["position"])
    occ_pos = v3(occ_cfg["position"])

    add_label("SENSOR", sensor_pos + Vector((0, 0, 0.25)),
              size=0.10, color=(0.7, 0.9, 1.0))
    add_label("RELAY WALL", wall_pos + Vector((0, -0.20, wall_size / 2 + 0.12)),
              size=0.10, color=(0.9, 0.9, 0.9))
    add_label("OCCLUDER", occ_pos + Vector((0.15, 0, wall_size / 2 + 0.12)),
              size=0.08, color=(0.7, 0.7, 0.8))

    for obj_cfg in hidden_objects:
        label = obj_cfg.get("label", obj_cfg.get("kind", "object"))
        c = rgb(obj_cfg.get("color", {"r": 1, "g": 1, "b": 1}))

        # Compound objects: compute center from parts
        if obj_cfg.get("kind") == "compound" and "parts" in obj_cfg:
            parts = obj_cfg["parts"]
            if parts:
                avg_x = sum(p["position"]["x"] for p in parts) / len(parts)
                avg_y = sum(p["position"]["y"] for p in parts) / len(parts)
                avg_z = sum(p["position"]["z"] for p in parts) / len(parts)
                pos = Vector((avg_x, avg_y, avg_z))
            else:
                continue
        else:
            pos = v3(obj_cfg["position"])

        add_label(label.upper(), pos + Vector((0, 0, 0.20)),
                  size=0.07, color=c)


# ── Camera and lighting ──────────────────────────────────────────────

def setup_camera(cam_cfg):
    pos = v3(cam_cfg["position"])
    bpy.ops.object.camera_add(location=pos)
    cam = bpy.context.active_object
    cam.name = "MainCamera"
    cam.data.lens = cam_cfg.get("lens_mm", 32)
    cam.data.clip_end = 50

    target_pos = v3(cam_cfg["look_at"])
    bpy.ops.object.empty_add(location=target_pos)
    target = bpy.context.active_object
    target.name = "CamTarget"

    constraint = cam.constraints.new(type='TRACK_TO')
    constraint.target = target
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    bpy.context.scene.camera = cam


def setup_lighting():
    # Key light
    bpy.ops.object.light_add(type='AREA', location=(3, -2.5, 3.5))
    key = bpy.context.active_object
    key.name = "KeyLight"
    key.data.energy = 250
    key.data.size = 2.5
    key.data.color = (1.0, 0.95, 0.9)

    # Fill light
    bpy.ops.object.light_add(type='AREA', location=(-2.5, -0.5, 2))
    fill = bpy.context.active_object
    fill.name = "FillLight"
    fill.data.energy = 100
    fill.data.size = 3
    fill.data.color = (0.85, 0.9, 1.0)

    # Rim light
    bpy.ops.object.light_add(type='AREA', location=(0, 2.5, 2))
    rim = bpy.context.active_object
    rim.name = "RimLight"
    rim.data.energy = 120
    rim.data.size = 2

    # Point light on hidden objects
    bpy.ops.object.light_add(type='POINT', location=(0.5, 1.0, 0.8))
    spot = bpy.context.active_object
    spot.name = "HiddenSpot"
    spot.data.energy = 30


def setup_render(render_cfg, output_path):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = render_cfg.get("samples", 256)
    scene.cycles.use_denoising = render_cfg.get("use_denoising", True)
    scene.render.resolution_x = render_cfg.get("resolution_x", 1920)
    scene.render.resolution_y = render_cfg.get("resolution_y", 1080)
    scene.render.resolution_percentage = 100
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.015, 0.015, 0.025, 1.0)
        bg.inputs["Strength"].default_value = 0.3


# ── Main ─────────────────────────────────────────────────────────────

def main():
    clear_scene()

    wall_cfg = SCENE["relay_wall"]
    sensor_cfg = SCENE["sensor"]
    occ_cfg = SCENE["occluder"]
    hidden = list(SCENE.get("hidden_objects", []))

    build_relay_wall(wall_cfg)
    build_occluder(occ_cfg)

    for obj_cfg in hidden:
        build_hidden_object(obj_cfg)

    build_sensor(sensor_cfg)

    if sensor_cfg.get("show_laser", True):
        build_laser_beam(sensor_cfg)

    if SCENE.get("show_light_paths", True):
        build_light_paths(sensor_cfg, wall_cfg, hidden)

    if SCENE.get("show_floor", True):
        build_floor()

    if SCENE.get("show_labels", True):
        build_labels(sensor_cfg, wall_cfg, occ_cfg, hidden)

    setup_camera(SCENE.get("camera", {}))
    setup_lighting()
    setup_render(SCENE.get("render", {}), OUTPUT_PATH)

    bpy.ops.render.render(write_still=True)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
