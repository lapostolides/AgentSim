"""File handling utilities — load and validate user-provided files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Supported file extensions and their categories
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".stl": "mesh",
    ".obj": "mesh",
    ".ply": "mesh",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
    ".csv": "data",
    ".tsv": "data",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".exr": "image",
    ".hdr": "image",
    ".tiff": "image",
    ".xml": "config",
    ".py": "script",
    ".txt": "text",
}


class FileLoadError(Exception):
    """Raised when a file cannot be loaded or validated."""


def validate_file_path(path: str) -> Path:
    """Validate that a file exists and is readable.

    Args:
        path: Path to the file.

    Returns:
        Resolved Path object.

    Raises:
        FileLoadError: If the file doesn't exist or isn't readable.
    """
    resolved = Path(path).resolve()

    if not resolved.exists():
        raise FileLoadError(f"File not found: {path}")
    if not resolved.is_file():
        raise FileLoadError(f"Not a file: {path}")
    if not resolved.suffix.lower() in SUPPORTED_EXTENSIONS:
        logger.warning("unsupported_extension", path=path, suffix=resolved.suffix)

    return resolved


def detect_file_type(path: str) -> str:
    """Detect file type from extension.

    Args:
        path: File path.

    Returns:
        File type category string.
    """
    suffix = Path(path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(suffix, "unknown")


def load_text_file(path: str) -> str:
    """Load a text file's contents.

    Args:
        path: Path to the text file.

    Returns:
        File contents as string.

    Raises:
        FileLoadError: If the file can't be read.
    """
    resolved = validate_file_path(path)
    try:
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise FileLoadError(f"File is not valid UTF-8 text: {path}")


def load_json_file(path: str) -> dict[str, Any]:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data.

    Raises:
        FileLoadError: If the file can't be parsed.
    """
    text = load_text_file(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise FileLoadError(f"Invalid JSON in {path}: {e}")


def load_yaml_file(path: str) -> dict[str, Any]:
    """Load and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML data.

    Raises:
        FileLoadError: If yaml is not available or file can't be parsed.
    """
    try:
        import yaml
    except ImportError:
        raise FileLoadError("PyYAML is required to load YAML files: pip install pyyaml")

    text = load_text_file(path)
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise FileLoadError(f"Invalid YAML in {path}: {e}")


def get_file_metadata(path: str) -> dict[str, Any]:
    """Extract metadata from a file without fully loading it.

    Returns basic info (size, type, extension) and format-specific
    metadata when possible.

    Args:
        path: Path to the file.

    Returns:
        Dict of metadata about the file.
    """
    resolved = validate_file_path(path)
    stat = resolved.stat()

    metadata: dict[str, Any] = {
        "path": str(resolved),
        "name": resolved.name,
        "extension": resolved.suffix.lower(),
        "type": detect_file_type(path),
        "size_bytes": stat.st_size,
    }

    # Add format-specific metadata
    if metadata["type"] == "mesh" and resolved.suffix.lower() == ".stl":
        metadata.update(_get_stl_metadata(resolved))

    return metadata


def _get_stl_metadata(path: Path) -> dict[str, Any]:
    """Extract basic metadata from an STL file."""
    try:
        content = path.read_bytes()
        if content[:5] == b"solid":
            return {"stl_format": "ascii"}
        # Binary STL: bytes 80-84 contain triangle count (uint32 LE)
        if len(content) >= 84:
            import struct
            triangle_count = struct.unpack_from("<I", content, 80)[0]
            return {"stl_format": "binary", "triangle_count": triangle_count}
    except Exception:
        pass
    return {}


def validate_files(paths: list[str]) -> list[str]:
    """Validate a list of file paths, returning only valid ones.

    Logs warnings for invalid files but doesn't raise.

    Args:
        paths: List of file paths to validate.

    Returns:
        List of valid, resolved file paths.
    """
    valid: list[str] = []
    for path in paths:
        try:
            resolved = validate_file_path(path)
            valid.append(str(resolved))
        except FileLoadError as e:
            logger.warning("invalid_file", path=path, error=str(e))
    return valid
