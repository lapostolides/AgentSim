"""Confocal point reflector scene template (benchmark scene 1).

Single hidden sphere behind the relay wall, scanned in confocal mode.
Produces the canonical single-peak transient response used for validation.
"""

from __future__ import annotations

import math

from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
    NLOSSceneTemplate,
)


class ConfocalPointScene(NLOSSceneTemplate, frozen=True):
    """Confocal scanning scene with a single hidden sphere.

    Defaults match O'Toole 2018 benchmark parameters. The hidden
    sphere is placed at hidden_object_pos behind the relay wall.
    """

    hidden_object_pos: tuple[float, float, float] = (0.0, 1.0, 0.0)
    hidden_object_radius: float = 0.1
    scanning_mode: str = "confocal"

    @property
    def auto_start_opl(self) -> float:
        """Compute minimum round-trip OPL with 10% margin below.

        Path: sensor -> relay wall center -> hidden object -> relay wall center -> sensor.
        For confocal, laser and sensor share the same wall point.
        """
        wall_x, wall_y, wall_z = self.relay_wall_position
        obj_x, obj_y, obj_z = self.hidden_object_pos

        # Distance from relay wall to hidden object
        wall_to_obj = math.sqrt(
            (obj_x - wall_x) ** 2
            + (obj_y - wall_y) ** 2
            + (obj_z - wall_z) ** 2
        )

        # Minimum round-trip OPL (wall -> object -> wall, confocal)
        min_round_trip = 2.0 * wall_to_obj

        # Apply 10% margin below
        return min_round_trip * 0.9

    def _build_hidden_objects(self) -> dict:
        """Build hidden sphere geometry."""
        return {
            "hidden_sphere": {
                "type": "sphere",
                "center": list(self.hidden_object_pos),
                "radius": self.hidden_object_radius,
                "bsdf": {
                    "type": "diffuse",
                    "reflectance": {"type": "rgb", "value": [1.0, 1.0, 1.0]},
                },
            },
        }
