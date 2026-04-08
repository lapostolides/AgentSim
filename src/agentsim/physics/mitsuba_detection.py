"""Mitsuba 3 + mitransient availability detection and scene agent context generation.

Checks whether mitsuba and mitransient packages are available in the
discovered environment, and generates appropriate scene agent context
for either Mitsuba-based physically-based rendering or numpy-based
approximate simulation.
"""

from __future__ import annotations

import structlog

from agentsim.state.models import EnvironmentInfo

logger = structlog.get_logger()


def has_mitsuba_transient(env: EnvironmentInfo) -> bool:
    """Check whether both mitsuba and mitransient are available.

    Both packages are required for physically-based NLOS transient
    rendering. If either is missing, the pipeline falls back to
    numpy-based approximate simulation.

    Args:
        env: Discovered environment information with available packages.

    Returns:
        True if both mitsuba and mitransient are present.
    """
    names = {p.name for p in env.packages}
    available = "mitsuba" in names and "mitransient" in names
    logger.debug("mitsuba_transient_check", available=available, packages=sorted(names))
    return available


def format_mitsuba_scene_context(has_mitsuba: bool) -> str:
    """Generate scene agent context for the appropriate rendering mode.

    When Mitsuba + mitransient are available, returns instructions for
    physically-based transient rendering with correct import order.
    Otherwise, returns numpy fallback guidance.

    Args:
        has_mitsuba: Whether mitsuba + mitransient are available.

    Returns:
        Multiline string with rendering mode instructions for the scene agent.
    """
    if has_mitsuba:
        context = _format_mitsuba_context()
    else:
        context = _format_numpy_fallback_context()

    mode = "mitsuba" if has_mitsuba else "numpy"
    logger.info("mitsuba_scene_context_formatted", mode=mode)
    return context


def _format_mitsuba_context() -> str:
    """Format context for Mitsuba 3 + mitransient rendering mode."""
    return """\
## Rendering Mode: Mitsuba 3 + mitransient (Physically-Based)

Mitsuba 3 with mitransient is available for NLOS transient rendering.
mitransient provides NLOS-specific plugins (transient integrators,
streak sensors) that extend Mitsuba's differentiable rendering engine.

### CRITICAL: Import Order (Pitfall 2)

The variant MUST be set before importing mitransient:

```python
import mitsuba as mi
mi.set_variant('llvm_ad_rgb')
import mitransient as mitr  # AFTER set_variant
import numpy as np
```

WARNING: do NOT call mi.set_variant() inside template code or after
mitransient has been imported. The variant must be locked first.

### Template Usage

Import scene templates for structured scene construction:

```python
from agentsim.physics.domains.nlos_transient_imaging.templates import (
    ConfocalPointScene,
    NonConfocalMeshScene,
    get_template,
)
```

### Example Workflow

```python
# 1. Create template with parameters
template = ConfocalPointScene(
    scan_points=32,
    time_bins=1024,
    spp=256,  # default for fast iteration (D-07)
)

# 2. Build scene dict and render
scene_dict = template.build()
scene = mi.load_dict(scene_dict)
image = mi.render(scene)

# 3. Save raw transient data as .npy (D-09)
transient = np.array(image)
np.save("transient_data.npy", transient)
```

### Notes

- Use spp=256 for fast iteration during development (D-07).
  Increase for final results (spp=4096+).
- Always save raw transient data as .npy files (D-09) for
  downstream analysis and reconstruction.
- The llvm_ad_rgb variant supports differentiable rendering
  with RGB color channels.
"""


def _format_numpy_fallback_context() -> str:
    """Format context for numpy-based approximate simulation."""
    return """\
## Rendering Mode: Numpy Approximate

Mitsuba is not available in the current environment. Use numpy-based
approximate transient simulation. Mark all outputs as 'approximate'
in output metadata.

Generate self-contained numpy scripts that simulate transient light
transport using analytical models (inverse-square falloff, geometric
path lengths). Save transient data as .npy files.
"""
