"""Base class for NLOS scene templates.

Provides the NLOSSceneTemplate frozen Pydantic model that produces
Mitsuba 3 / mitransient scene dicts via the build() method. Subclasses
override _build_hidden_objects() to define benchmark geometries.

No mitsuba imports at module level — templates work without mitsuba installed.
"""

from __future__ import annotations

from pydantic import BaseModel

SPEED_OF_LIGHT: float = 299_792_458.0

SPP_TIERS: dict[str, int] = {
    "draft": 64,
    "low": 256,
    "medium": 1024,
    "high": 4096,
    "ultra": 16384,
}


class NLOSSceneTemplate(BaseModel, frozen=True):
    """Frozen base class for NLOS transient scene templates.

    Produces a Mitsuba scene dict via build(). Subclasses override
    _build_hidden_objects() to add hidden geometry.

    Fields use defaults from published NLOS literature (O'Toole 2018,
    Lindell 2019). The variant defaults to llvm_ad_rgb for mitransient
    compatibility.
    """

    relay_wall_size: float = 2.0
    relay_wall_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scanning_mode: str = "confocal"
    scan_resolution: int = 64
    temporal_bins: int = 2048
    temporal_resolution_ps: float = 32.0
    spp: int = 256
    variant: str = "llvm_ad_rgb"
    nlos_laser_sampling: bool = True
    nlos_hidden_geometry_sampling: bool = True
    max_depth: int = -1
    start_opl: float | None = None

    @property
    def bin_width_opl(self) -> float:
        """Convert temporal resolution (ps) to optical path length (m).

        bin_width_opl = temporal_resolution_ps * 1e-12 * SPEED_OF_LIGHT
        """
        return self.temporal_resolution_ps * 1e-12 * SPEED_OF_LIGHT

    @property
    def auto_start_opl(self) -> float:
        """Compute minimum round-trip OPL from geometry.

        Base implementation returns 0.0. Subclasses override with
        geometry-aware computation (2 * min_path_length with margin).
        """
        return 0.0

    def _build_film_dict(self) -> dict:
        """Build transient HDR film configuration dict."""
        effective_start_opl = (
            self.start_opl if self.start_opl is not None else self.auto_start_opl
        )
        return {
            "type": "transient_hdr_film",
            "temporal_bins": self.temporal_bins,
            "bin_width_opl": self.bin_width_opl,
            "start_opl": effective_start_opl,
            "rfilter": {"type": "box"},
        }

    def _build_integrator_dict(self) -> dict:
        """Build transient NLOS path integrator configuration dict."""
        return {
            "type": "transient_nlos_path",
            "nlos_laser_sampling": self.nlos_laser_sampling,
            "nlos_hidden_geometry_sampling": self.nlos_hidden_geometry_sampling,
            "max_depth": self.max_depth,
        }

    def _build_sensor_dict(self) -> dict:
        """Build NLOS capture meter sensor configuration dict."""
        return {
            "type": "nlos_capture_meter",
            "sensor_origin": list(self.relay_wall_position),
            "sampler": {
                "type": "independent",
                "sample_count": self.spp,
            },
            "film": self._build_film_dict(),
        }

    def _build_relay_wall_dict(self) -> dict:
        """Build relay wall rectangle with diffuse BSDF and sensor child."""
        half_size = self.relay_wall_size / 2.0
        return {
            "type": "rectangle",
            "to_world": {
                "type": "scale",
                "value": [half_size, half_size, 1.0],
            },
            "bsdf": {
                "type": "diffuse",
                "reflectance": {"type": "rgb", "value": [1.0, 1.0, 1.0]},
            },
            "sensor": self._build_sensor_dict(),
        }

    def _build_hidden_objects(self) -> dict:
        """Build hidden object geometry dict.

        Base returns empty dict. Subclasses override to add hidden
        geometry (spheres, meshes, corner reflectors, etc.).
        """
        return {}

    def build(self) -> dict:
        """Assemble a complete Mitsuba scene dict.

        Returns:
            Dict with type, integrator, relay_wall, plus hidden objects.
            Does NOT import mitsuba — dict is passed to mi.load_dict()
            at render time.
        """
        scene: dict = {
            "type": "scene",
            "integrator": self._build_integrator_dict(),
            "relay_wall": self._build_relay_wall_dict(),
        }
        hidden = self._build_hidden_objects()
        return {**scene, **hidden}
