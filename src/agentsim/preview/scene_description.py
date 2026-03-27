"""Immutable data models describing an NLOS scene for visualization.

These models define the geometry that gets passed to Blender for rendering.
They are independent of any specific simulation — any experiment can construct
a SceneDescription from its parameters and get a preview rendered.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Vec3(BaseModel, frozen=True):
    """3D vector / point."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class Color(BaseModel, frozen=True):
    """RGB color in [0, 1]."""
    r: float = 0.5
    g: float = 0.5
    b: float = 0.5

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.r, self.g, self.b)


class RelayWall(BaseModel, frozen=True):
    """The relay wall that scatters light toward the hidden scene."""
    position: Vec3 = Field(default_factory=lambda: Vec3(x=0, y=0, z=0))
    size: float = 2.0
    albedo_pattern: str = "uniform"  # uniform, checker, random_binary, hadamard, perlin
    albedo_block_size: int = 4       # for checker pattern
    color: Color = Field(default_factory=lambda: Color(r=0.8, g=0.8, b=0.8))
    normal: Vec3 = Field(
        default_factory=lambda: Vec3(x=0, y=-1, z=0),
        description="Outward normal direction (toward sensor)",
    )


class Sensor(BaseModel, frozen=True):
    """The SPAD sensor / pulsed laser system."""
    position: Vec3 = Field(default_factory=lambda: Vec3(x=0, y=-1.5, z=0))
    look_at: Vec3 = Field(default_factory=lambda: Vec3(x=0, y=0, z=0))
    color: Color = Field(default_factory=lambda: Color(r=0.08, g=0.08, b=0.10))
    show_laser: bool = True
    laser_target: Vec3 = Field(
        default_factory=lambda: Vec3(x=0.2, y=0, z=0.15),
        description="Point on the relay wall where the laser is aimed",
    )


class Occluder(BaseModel, frozen=True):
    """Partition wall that blocks direct line of sight."""
    position: Vec3 = Field(default_factory=lambda: Vec3(x=1.02, y=0.85, z=0))
    size: Vec3 = Field(
        default_factory=lambda: Vec3(x=0.04, y=1.9, z=2.0),
        description="Width (thickness), depth (into scene), height",
    )
    color: Color = Field(default_factory=lambda: Color(r=0.45, g=0.45, b=0.50))
    transparent: bool = True  # semi-transparent so hidden objects are visible


class SphereObject(BaseModel, frozen=True):
    """A spherical hidden object."""
    kind: str = "sphere"
    position: Vec3
    radius: float = 0.12
    color: Color = Field(default_factory=lambda: Color(r=0.9, g=0.35, b=0.15))
    label: str = ""


class BoxObject(BaseModel, frozen=True):
    """A box-shaped hidden object."""
    kind: str = "box"
    position: Vec3
    size: Vec3 = Field(default_factory=lambda: Vec3(x=0.2, y=0.2, z=0.2))
    color: Color = Field(default_factory=lambda: Color(r=0.15, g=0.55, b=0.90))
    label: str = ""


class CylinderObject(BaseModel, frozen=True):
    """A cylindrical hidden object."""
    kind: str = "cylinder"
    position: Vec3
    radius: float = 0.1
    height: float = 0.3
    color: Color = Field(default_factory=lambda: Color(r=0.2, g=0.8, b=0.4))
    label: str = ""


class CompoundObject(BaseModel, frozen=True):
    """A compound hidden object built from multiple primitives."""
    kind: str = "compound"
    parts: tuple[BoxObject | SphereObject | CylinderObject, ...] = ()
    color: Color = Field(default_factory=lambda: Color(r=0.15, g=0.55, b=0.90))
    label: str = ""


HiddenObject = SphereObject | BoxObject | CylinderObject | CompoundObject


class CameraSettings(BaseModel, frozen=True):
    """Camera position and lens settings for the preview render."""
    position: Vec3 = Field(default_factory=lambda: Vec3(x=3.2, y=-2.0, z=2.2))
    look_at: Vec3 = Field(default_factory=lambda: Vec3(x=0.2, y=0.4, z=0.0))
    lens_mm: float = 32.0


class RenderSettings(BaseModel, frozen=True):
    """Render quality settings."""
    resolution_x: int = 1920
    resolution_y: int = 1080
    samples: int = 256
    use_denoising: bool = True


class SceneDescription(BaseModel, frozen=True):
    """Complete description of an NLOS scene for preview rendering.

    Construct this from your simulation parameters, then pass it to
    preview_scene() to get a Blender render before execution.
    """
    relay_wall: RelayWall = Field(default_factory=RelayWall)
    sensor: Sensor = Field(default_factory=Sensor)
    occluder: Occluder = Field(default_factory=Occluder)
    hidden_objects: tuple[HiddenObject, ...] = ()
    camera: CameraSettings = Field(default_factory=CameraSettings)
    render: RenderSettings = Field(default_factory=RenderSettings)
    show_light_paths: bool = True
    show_labels: bool = True
    show_floor: bool = True
    title: str = ""
