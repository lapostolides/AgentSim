"""Environment discovery — probes what simulation packages are available.

Instead of MCP servers, we simply check which Python packages the
current environment can import. Agents then write code that uses
these packages directly.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys

import structlog

from agentsim.state.models import AvailablePackage, EnvironmentInfo

logger = structlog.get_logger()

# Well-known simulation packages and their import names.
# Keys are package display names, values are the importable module name.
KNOWN_SIMULATION_PACKAGES: dict[str, str] = {
    "mitsuba": "mitsuba",
    "blender": "bpy",
    "carla": "carla",
    "pybullet": "pybullet",
    "trimesh": "trimesh",
    "open3d": "open3d",
    "pyglet": "pyglet",
    "pyvista": "pyvista",
    "vtk": "vtk",
    "opencv": "cv2",
    "scipy": "scipy",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "pillow": "PIL",
    "scikit-image": "skimage",
}


def _check_package(import_name: str) -> tuple[bool, str]:
    """Check if a package is importable and get its version.

    Does NOT actually import the package (avoids side effects).
    Uses importlib.util.find_spec for a lightweight check.
    """
    spec = importlib.util.find_spec(import_name)
    if spec is None:
        return False, ""

    # Try to get version from metadata
    # Package metadata name often differs from import name
    version = ""
    for dist_name in [import_name, import_name.replace("_", "-")]:
        try:
            version = importlib.metadata.version(dist_name)
            break
        except importlib.metadata.PackageNotFoundError:
            continue

    return True, version


def discover_environment(
    extra_packages: dict[str, str] | None = None,
) -> EnvironmentInfo:
    """Discover what simulation packages are available.

    Probes the Python environment for known simulation packages
    without actually importing them.

    Args:
        extra_packages: Additional package name → import name mappings
            to check beyond the built-in list.

    Returns:
        EnvironmentInfo describing available packages.
    """
    packages_to_check = dict(KNOWN_SIMULATION_PACKAGES)
    if extra_packages:
        packages_to_check.update(extra_packages)

    found: list[AvailablePackage] = []

    for display_name, import_name in sorted(packages_to_check.items()):
        available, version = _check_package(import_name)
        if available:
            found.append(AvailablePackage(
                name=display_name,
                version=version,
                import_name=import_name,
            ))
            logger.info(
                "package_available",
                name=display_name,
                import_name=import_name,
                version=version,
            )

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    logger.info(
        "environment_discovered",
        python_version=python_version,
        package_count=len(found),
        packages=[p.name for p in found],
    )

    return EnvironmentInfo(
        packages=tuple(found),
        python_version=python_version,
    )


def format_environment_for_prompt(env: EnvironmentInfo) -> str:
    """Format environment info as a readable string for agent prompts."""
    if not env.packages:
        return "No simulation packages detected. You can install packages with pip."

    lines = [f"Python {env.python_version}", "", "Available packages:"]
    for pkg in env.packages:
        version_str = f" ({pkg.version})" if pkg.version else ""
        import_note = f"  [import {pkg.import_name}]" if pkg.import_name != pkg.name else ""
        lines.append(f"  - {pkg.name}{version_str}{import_note}")

    return "\n".join(lines)
