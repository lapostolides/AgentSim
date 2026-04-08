"""Non-confocal mesh scene template (benchmark scene 2).

Loads an external .obj or .ply mesh as the hidden geometry, scanned
in non-confocal mode (laser and sensor at different wall positions).
"""

from __future__ import annotations

from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
    NLOSSceneTemplate,
)


class NonConfocalMeshScene(NLOSSceneTemplate, frozen=True):
    """Non-confocal scanning scene with a mesh-based hidden object.

    The mesh file is referenced by filename and loaded at render time
    by Mitsuba. Supports .obj and .ply formats.
    """

    mesh_filename: str
    mesh_position: tuple[float, float, float] = (0.0, 1.0, 0.0)
    mesh_scale: float = 1.0
    mesh_format: str = "obj"
    scanning_mode: str = "non-confocal"

    def _build_hidden_objects(self) -> dict:
        """Build mesh-based hidden geometry."""
        return {
            "hidden_mesh": {
                "type": self.mesh_format,
                "filename": self.mesh_filename,
                "to_world": {
                    "type": "scale",
                    "value": [self.mesh_scale] * 3,
                },
                "bsdf": {
                    "type": "diffuse",
                    "reflectance": {"type": "rgb", "value": [1.0, 1.0, 1.0]},
                },
            },
        }
