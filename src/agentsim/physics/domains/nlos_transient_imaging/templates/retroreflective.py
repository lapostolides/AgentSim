"""Retroreflective corner scene template (benchmark scene 3).

Two perpendicular rectangles forming a corner reflector that produces
an enhanced retroreflective return signal in the transient response.
"""

from __future__ import annotations

from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
    NLOSSceneTemplate,
)


class RetroReflectiveScene(NLOSSceneTemplate, frozen=True):
    """Corner reflector scene with two perpendicular rectangles.

    The corner reflector is formed by a horizontal and vertical
    rectangle meeting at corner_position, producing an enhanced
    retroreflective signal.
    """

    corner_position: tuple[float, float, float] = (0.0, 1.0, 0.0)
    corner_size: float = 0.5

    def _build_hidden_objects(self) -> dict:
        """Build two perpendicular rectangles forming a corner reflector."""
        cx, cy, cz = self.corner_position
        half = self.corner_size / 2.0

        return {
            "corner_horizontal": {
                "type": "rectangle",
                "to_world": {
                    "type": "scale",
                    "value": [half, half, 1.0],
                },
                "bsdf": {
                    "type": "diffuse",
                    "reflectance": {"type": "rgb", "value": [1.0, 1.0, 1.0]},
                },
            },
            "corner_vertical": {
                "type": "rectangle",
                "to_world": {
                    "type": "scale",
                    "value": [half, half, 1.0],
                },
                "bsdf": {
                    "type": "diffuse",
                    "reflectance": {"type": "rgb", "value": [1.0, 1.0, 1.0]},
                },
            },
        }
