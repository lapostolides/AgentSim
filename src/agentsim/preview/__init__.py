"""Scene preview module — renders NLOS scene geometry via Blender before simulation."""

from agentsim.preview.scene_description import (
    BoxObject,
    CompoundObject,
    CylinderObject,
    Occluder,
    RelayWall,
    SceneDescription,
    Sensor,
    SphereObject,
)
from agentsim.preview.renderer import preview_scene

__all__ = [
    "BoxObject",
    "CylinderObject",
    "Occluder",
    "RelayWall",
    "SceneDescription",
    "Sensor",
    "CompoundObject",
    "SphereObject",
    "preview_scene",
]
