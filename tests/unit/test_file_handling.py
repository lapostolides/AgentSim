"""Tests for file handling utilities."""

import json
import struct
from pathlib import Path

import pytest

from agentsim.utils.file_handling import (
    FileLoadError,
    detect_file_type,
    get_file_metadata,
    load_json_file,
    load_text_file,
    validate_file_path,
    validate_files,
)


class TestDetectFileType:
    def test_mesh_types(self):
        assert detect_file_type("/data/model.stl") == "mesh"
        assert detect_file_type("/data/model.obj") == "mesh"
        assert detect_file_type("/data/model.ply") == "mesh"

    def test_config_types(self):
        assert detect_file_type("/data/config.yaml") == "config"
        assert detect_file_type("/data/config.yml") == "config"
        assert detect_file_type("/data/config.json") == "config"
        assert detect_file_type("/data/scene.xml") == "config"

    def test_image_types(self):
        assert detect_file_type("/data/render.png") == "image"
        assert detect_file_type("/data/render.exr") == "image"

    def test_unknown_type(self):
        assert detect_file_type("/data/file.xyz") == "unknown"

    def test_case_insensitive(self):
        assert detect_file_type("/data/MODEL.STL") == "mesh"


class TestValidateFilePath:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = validate_file_path(str(f))
        assert result == f.resolve()

    def test_nonexistent_file(self):
        with pytest.raises(FileLoadError, match="File not found"):
            validate_file_path("/nonexistent/file.txt")

    def test_directory_path(self, tmp_path):
        with pytest.raises(FileLoadError, match="Not a file"):
            validate_file_path(str(tmp_path))


class TestLoadTextFile:
    def test_load(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert load_text_file(str(f)) == "hello world"

    def test_nonexistent(self):
        with pytest.raises(FileLoadError):
            load_text_file("/nonexistent/file.txt")


class TestLoadJsonFile:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"key": "value", "count": 42}))
        data = load_json_file(str(f))
        assert data["key"] == "value"
        assert data["count"] == 42

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        with pytest.raises(FileLoadError, match="Invalid JSON"):
            load_json_file(str(f))


class TestGetFileMetadata:
    def test_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        meta = get_file_metadata(str(f))
        assert meta["name"] == "test.txt"
        assert meta["type"] == "text"
        assert meta["size_bytes"] == 5

    def test_binary_stl(self, tmp_path):
        f = tmp_path / "model.stl"
        # Create a minimal binary STL: 80-byte header + 4-byte triangle count
        header = b"\x00" * 80
        triangle_count = struct.pack("<I", 42)
        f.write_bytes(header + triangle_count)
        meta = get_file_metadata(str(f))
        assert meta["type"] == "mesh"
        assert meta["stl_format"] == "binary"
        assert meta["triangle_count"] == 42

    def test_ascii_stl(self, tmp_path):
        f = tmp_path / "model.stl"
        f.write_text("solid test\nendsolid test")
        meta = get_file_metadata(str(f))
        assert meta["stl_format"] == "ascii"


class TestValidateFiles:
    def test_mixed_valid_invalid(self, tmp_path):
        good = tmp_path / "good.txt"
        good.write_text("ok")
        paths = [str(good), "/nonexistent/bad.txt"]
        result = validate_files(paths)
        assert len(result) == 1
        assert "good.txt" in result[0]

    def test_all_valid(self, tmp_path):
        files = []
        for name in ["a.txt", "b.json", "c.stl"]:
            f = tmp_path / name
            f.write_text("data")
            files.append(str(f))
        result = validate_files(files)
        assert len(result) == 3
