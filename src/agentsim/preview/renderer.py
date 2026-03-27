"""Render an NLOS scene preview via Blender headless.

Writes a JSON scene description to disk, invokes Blender with the
render script, and returns the path to the rendered image.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from agentsim.preview.scene_description import SceneDescription

BLENDER_PATHS = [
    "/Applications/Blender.app/Contents/MacOS/Blender",
    shutil.which("blender") or "",
]

RENDER_SCRIPT = Path(__file__).parent / "blender_render.py"


def _find_blender() -> str:
    for path in BLENDER_PATHS:
        if path and Path(path).is_file():
            return path
    raise FileNotFoundError(
        "Blender not found. Install Blender or set BLENDER_PATH env var. "
        "Searched: " + ", ".join(p for p in BLENDER_PATHS if p)
    )


def preview_scene(
    scene: SceneDescription,
    output_path: str | Path,
    blender_path: str | None = None,
    timeout_seconds: int = 300,
) -> Path:
    """Render a scene preview and return the output image path.

    Args:
        scene: Immutable scene description with all geometry.
        output_path: Where to save the rendered PNG.
        blender_path: Override path to Blender executable.
        timeout_seconds: Max render time before aborting.

    Returns:
        Path to the rendered PNG image.

    Raises:
        FileNotFoundError: If Blender is not installed.
        subprocess.TimeoutExpired: If rendering exceeds timeout.
        RuntimeError: If Blender exits with an error.
    """
    blender = blender_path or _find_blender()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write scene description as JSON for the Blender script to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="nlos_scene_"
    ) as f:
        f.write(scene.model_dump_json(indent=2))
        scene_json_path = f.name

    try:
        result = subprocess.run(
            [
                blender,
                "--background",
                "--python", str(RENDER_SCRIPT),
                "--",
                scene_json_path,
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Blender render failed (exit {result.returncode}):\n"
                f"stderr: {result.stderr[-2000:]}\n"
                f"stdout: {result.stdout[-2000:]}"
            )

        if not output_path.exists():
            raise RuntimeError(
                f"Blender completed but output not found at {output_path}\n"
                f"stderr: {result.stderr[-2000:]}\n"
                f"stdout: {result.stdout[-2000:]}"
            )

    finally:
        Path(scene_json_path).unlink(missing_ok=True)

    return output_path
