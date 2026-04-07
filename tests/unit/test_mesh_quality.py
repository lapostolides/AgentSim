"""Tests for mesh quality validation via trimesh."""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from agentsim.physics.models import Severity


class TestTrimeshNotInstalled:
    """Test graceful handling when trimesh is not available."""

    def test_missing_trimesh_returns_info(self) -> None:
        """When trimesh is not importable, return INFO not ERROR."""
        # Temporarily hide trimesh from imports
        real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name: str, *args, **kwargs):
            if name == "trimesh":
                raise ImportError("No module named 'trimesh'")
            return real_import(name, *args, **kwargs)

        # Need to reload the module with trimesh unavailable
        import importlib
        import agentsim.physics.checks.mesh_quality as mq_mod

        with patch("builtins.__import__", side_effect=mock_import):
            # Call the function directly — it does runtime import
            results = mq_mod.check_mesh_quality(("some_mesh.stl",))

        assert len(results) >= 1
        assert any(
            r.severity == Severity.INFO and "trimesh" in r.message.lower()
            for r in results
        )


class TestMissingMeshFile:
    """Test handling of non-existent mesh files."""

    def test_nonexistent_file_returns_info(self) -> None:
        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality(("/nonexistent/path/mesh.stl",))
        assert len(results) >= 1
        assert any(r.severity == Severity.INFO for r in results)
        assert any("not found" in r.message.lower() or "runtime" in r.message.lower() for r in results)


class TestEmptyMeshPaths:
    """Test empty input."""

    def test_empty_paths_returns_empty(self) -> None:
        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality(())
        assert len(results) == 0


class TestGoodMesh:
    """Test good quality meshes (using trimesh creation utilities)."""

    def test_watertight_box_no_watertight_warning(self, tmp_path: Path) -> None:
        import trimesh

        mesh = trimesh.creation.box()
        mesh_path = tmp_path / "box.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality((str(mesh_path),))
        # A box should be watertight — no WARNING for watertightness
        watertight_warnings = [
            r for r in results
            if r.severity == Severity.WARNING and "watertight" in r.message.lower()
        ]
        assert len(watertight_warnings) == 0

    def test_good_mesh_only_info(self, tmp_path: Path) -> None:
        import trimesh

        mesh = trimesh.creation.box()
        mesh_path = tmp_path / "good_box.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality((str(mesh_path),))
        # Good mesh should only have INFO-level results
        assert all(r.severity == Severity.INFO for r in results)


class TestNonWatertightMesh:
    """Test non-watertight mesh detection."""

    def test_non_watertight_returns_warning(self, tmp_path: Path) -> None:
        import trimesh

        # Create a single open triangle (not watertight)
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        faces = np.array([[0, 1, 2]])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        mesh_path = tmp_path / "open.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality((str(mesh_path),))
        assert any(
            r.severity == Severity.WARNING and "watertight" in r.message.lower()
            for r in results
        )


class TestExtremeAspectRatio:
    """Test detection of extreme triangle aspect ratios."""

    def test_extreme_aspect_ratio_returns_error(self, tmp_path: Path) -> None:
        import trimesh

        # Create a very thin triangle with aspect ratio > 100
        vertices = np.array(
            [[0, 0, 0], [200, 0, 0], [0, 0.5, 0]],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2]])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        mesh_path = tmp_path / "thin.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality((str(mesh_path),))
        assert any(
            r.severity == Severity.ERROR and "aspect" in r.message.lower()
            for r in results
        )

    def test_moderate_aspect_ratio_returns_warning(self, tmp_path: Path) -> None:
        import trimesh

        # Create a triangle with aspect ratio ~20 (between 10 and 100)
        vertices = np.array(
            [[0, 0, 0], [20, 0, 0], [0, 1, 0]],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2]])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        mesh_path = tmp_path / "moderate.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        results = check_mesh_quality((str(mesh_path),))
        aspect_results = [r for r in results if "aspect" in r.message.lower()]
        assert any(r.severity == Severity.WARNING for r in aspect_results)


class TestPerformance:
    """Test performance budget."""

    def test_check_under_5s(self, tmp_path: Path) -> None:
        import trimesh

        mesh = trimesh.creation.box()
        mesh_path = tmp_path / "perf_test.stl"
        mesh.export(str(mesh_path))

        from agentsim.physics.checks.mesh_quality import check_mesh_quality

        start = time.perf_counter()
        check_mesh_quality((str(mesh_path),))
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Mesh check took {elapsed:.3f}s, exceeds 5s budget"
