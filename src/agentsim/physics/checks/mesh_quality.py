"""Mesh quality validation via trimesh.

Checks watertightness, triangle aspect ratio, and skewness for
mesh files referenced by simulation code. Gracefully skips when
trimesh is not installed or mesh files are missing (runtime generation).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from agentsim.physics.models import CheckResult, Severity

# Aspect ratio thresholds
EXTREME_ASPECT_RATIO = 100.0
HIGH_ASPECT_RATIO = 10.0

# Skewness threshold (1.0 = degenerate, 0.0 = equilateral)
SKEWNESS_THRESHOLD = 0.9


def check_mesh_quality(
    mesh_paths: tuple[str, ...],
) -> tuple[CheckResult, ...]:
    """Validate mesh quality for all referenced mesh files.

    Args:
        mesh_paths: Tuple of file paths to mesh files.

    Returns:
        Tuple of CheckResult with quality findings per mesh.
        Returns empty tuple for empty input.
        Returns INFO if trimesh not installed or file not found.
    """
    if not mesh_paths:
        return ()

    try:
        import trimesh  # noqa: F811
    except ImportError:
        return (
            CheckResult(
                check="mesh_quality",
                severity=Severity.INFO,
                message="trimesh not installed -- skipping mesh quality checks",
            ),
        )

    results: list[CheckResult] = []

    for path_str in mesh_paths:
        path = Path(path_str)
        if not path.exists():
            results.append(
                CheckResult(
                    check="mesh_quality",
                    severity=Severity.INFO,
                    message=(
                        f"Mesh file not found: {path_str} "
                        "(may be generated at runtime)"
                    ),
                    parameter=path_str,
                )
            )
            continue

        try:
            mesh = trimesh.load(path_str)
        except Exception as exc:
            results.append(
                CheckResult(
                    check="mesh_quality",
                    severity=Severity.WARNING,
                    message=f"Failed to load mesh: {path_str}: {exc}",
                    parameter=path_str,
                )
            )
            continue

        if not isinstance(mesh, trimesh.Trimesh):
            results.append(
                CheckResult(
                    check="mesh_quality",
                    severity=Severity.WARNING,
                    message=f"File {path_str} did not load as a triangle mesh",
                    parameter=path_str,
                )
            )
            continue

        # Watertightness check
        if not mesh.is_watertight:
            results.append(
                CheckResult(
                    check="mesh_quality",
                    severity=Severity.WARNING,
                    message=f"Mesh is not watertight: {path_str}",
                    parameter=path_str,
                )
            )

        # Aspect ratio check
        if len(mesh.triangles) > 0:
            aspect_ratios = _compute_triangle_aspect_ratios(mesh.triangles)
            max_ar = float(np.max(aspect_ratios))

            if max_ar > EXTREME_ASPECT_RATIO:
                results.append(
                    CheckResult(
                        check="mesh_quality",
                        severity=Severity.ERROR,
                        message=(
                            f"Extreme aspect ratio {max_ar:.1f} in {path_str} "
                            f"(threshold: {EXTREME_ASPECT_RATIO})"
                        ),
                        parameter=path_str,
                        details=f"max_aspect_ratio={max_ar:.3f}",
                    )
                )
            elif max_ar > HIGH_ASPECT_RATIO:
                results.append(
                    CheckResult(
                        check="mesh_quality",
                        severity=Severity.WARNING,
                        message=(
                            f"High aspect ratio {max_ar:.1f} in {path_str} "
                            f"(threshold: {HIGH_ASPECT_RATIO})"
                        ),
                        parameter=path_str,
                        details=f"max_aspect_ratio={max_ar:.3f}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        check="mesh_quality",
                        severity=Severity.INFO,
                        message=f"Aspect ratio {max_ar:.1f} is acceptable: {path_str}",
                        parameter=path_str,
                        details=f"max_aspect_ratio={max_ar:.3f}",
                    )
                )

            # Skewness check
            skewness = _compute_triangle_skewness(mesh.triangles)
            max_skew = float(np.max(skewness))

            if max_skew > SKEWNESS_THRESHOLD:
                results.append(
                    CheckResult(
                        check="mesh_quality",
                        severity=Severity.WARNING,
                        message=f"High skewness {max_skew:.3f} in {path_str}",
                        parameter=path_str,
                        details=f"max_skewness={max_skew:.3f}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        check="mesh_quality",
                        severity=Severity.INFO,
                        message=f"Skewness {max_skew:.3f} is acceptable: {path_str}",
                        parameter=path_str,
                        details=f"max_skewness={max_skew:.3f}",
                    )
                )
        else:
            results.append(
                CheckResult(
                    check="mesh_quality",
                    severity=Severity.INFO,
                    message=f"Mesh has no triangles: {path_str}",
                    parameter=path_str,
                )
            )

    return tuple(results)


def _compute_triangle_aspect_ratios(triangles: np.ndarray) -> np.ndarray:
    """Compute aspect ratio (max_edge / min_edge) per triangle.

    Args:
        triangles: Array of shape (N, 3, 3) -- N triangles, 3 vertices, 3 coords.

    Returns:
        Array of shape (N,) with aspect ratio per triangle.
    """
    # Edge vectors
    e0 = triangles[:, 1] - triangles[:, 0]
    e1 = triangles[:, 2] - triangles[:, 1]
    e2 = triangles[:, 0] - triangles[:, 2]

    # Edge lengths
    len0 = np.linalg.norm(e0, axis=-1)
    len1 = np.linalg.norm(e1, axis=-1)
    len2 = np.linalg.norm(e2, axis=-1)

    # Stack and compute ratio (avoid division by zero)
    edge_lengths = np.stack([len0, len1, len2], axis=-1)
    min_edges = np.maximum(np.min(edge_lengths, axis=-1), 1e-10)
    max_edges = np.max(edge_lengths, axis=-1)

    return max_edges / min_edges


def _compute_triangle_skewness(triangles: np.ndarray) -> np.ndarray:
    """Compute skewness per triangle based on deviation from equilateral.

    Skewness = max(|angle - 60deg| / 60deg) per triangle.
    0.0 = equilateral, 1.0 = degenerate.

    Args:
        triangles: Array of shape (N, 3, 3).

    Returns:
        Array of shape (N,) with skewness per triangle.
    """
    ideal_angle = np.pi / 3.0

    # Compute edge vectors from each vertex
    v0 = triangles[:, 0]
    v1 = triangles[:, 1]
    v2 = triangles[:, 2]

    # Edges from each vertex
    e01 = v1 - v0
    e02 = v2 - v0
    e10 = v0 - v1
    e12 = v2 - v1
    e20 = v0 - v2
    e21 = v1 - v2

    # Compute angles at each vertex via dot product
    angle0 = _safe_angle_between(e01, e02)
    angle1 = _safe_angle_between(e10, e12)
    angle2 = _safe_angle_between(e20, e21)

    angles = np.stack([angle0, angle1, angle2], axis=-1)
    deviations = np.abs(angles - ideal_angle) / ideal_angle

    return np.max(deviations, axis=-1)


def _safe_angle_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute angle between vector pairs, clamped to avoid NaN from arccos.

    Args:
        a: Array of vectors, shape (N, 3).
        b: Array of vectors, shape (N, 3).

    Returns:
        Array of angles in radians, shape (N,).
    """
    norm_a = np.linalg.norm(a, axis=-1, keepdims=True)
    norm_b = np.linalg.norm(b, axis=-1, keepdims=True)
    # Avoid division by zero
    norm_a = np.maximum(norm_a, 1e-10)
    norm_b = np.maximum(norm_b, 1e-10)
    cos_angle = np.sum(a * b, axis=-1) / (norm_a.squeeze(-1) * norm_b.squeeze(-1))
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return np.arccos(cos_angle)
