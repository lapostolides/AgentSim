"""NLOS scene template registry.

Public API for creating and discovering NLOS scene templates.
Templates produce Mitsuba scene dicts without importing mitsuba.
"""

from __future__ import annotations

from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
    NLOSSceneTemplate,
    SPEED_OF_LIGHT,
    SPP_TIERS,
)
from agentsim.physics.domains.nlos_transient_imaging.templates.confocal_point import (
    ConfocalPointScene,
)
from agentsim.physics.domains.nlos_transient_imaging.templates.nonconfocal_mesh import (
    NonConfocalMeshScene,
)
from agentsim.physics.domains.nlos_transient_imaging.templates.retroreflective import (
    RetroReflectiveScene,
)

__all__ = [
    "NLOSSceneTemplate",
    "SPEED_OF_LIGHT",
    "SPP_TIERS",
    "ConfocalPointScene",
    "NonConfocalMeshScene",
    "RetroReflectiveScene",
    "get_template",
    "list_templates",
]

_TEMPLATE_REGISTRY: dict[str, type[NLOSSceneTemplate]] = {
    "confocal_point": ConfocalPointScene,
    "nonconfocal_mesh": NonConfocalMeshScene,
    "retroreflective": RetroReflectiveScene,
}


def get_template(name: str) -> type[NLOSSceneTemplate]:
    """Look up a scene template class by name.

    Args:
        name: Template identifier (e.g., "confocal_point").

    Returns:
        The template class (not an instance).

    Raises:
        KeyError: If name is not in the registry.
    """
    if name not in _TEMPLATE_REGISTRY:
        available = ", ".join(sorted(_TEMPLATE_REGISTRY.keys()))
        msg = f"Unknown template {name!r}. Available: {available}"
        raise KeyError(msg)
    return _TEMPLATE_REGISTRY[name]


def list_templates() -> list[str]:
    """Return sorted list of available template names."""
    return sorted(_TEMPLATE_REGISTRY.keys())
