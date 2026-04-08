# utils

> Shared utility functions for file handling and logging configuration.

## Files

### __init__.py
Empty.

### file_handling.py
File loading, validation, and metadata extraction utilities. Used at system boundaries when processing user-provided files.

Key exports:

- **`SUPPORTED_EXTENSIONS`** -- Dict mapping file extensions to categories: mesh (.stl, .obj, .ply), config (.yaml, .yml, .json, .xml), data (.csv, .tsv), image (.png, .jpg, .jpeg, .exr, .hdr, .tiff), script (.py), text (.txt).
- **`FileLoadError`** -- Custom exception for file loading failures.
- **`validate_file_path(path)`** -- Checks existence, is-file, and logs warnings for unsupported extensions. Returns resolved `Path`.
- **`detect_file_type(path)`** -- Returns category string from `SUPPORTED_EXTENSIONS`.
- **`load_text_file(path)`** -- Reads UTF-8 text with validation.
- **`load_json_file(path)`** -- Parses JSON with error wrapping.
- **`load_yaml_file(path)`** -- Parses YAML (requires PyYAML, raises if missing).
- **`get_file_metadata(path)`** -- Returns dict with path, name, extension, type, size. For STL files, also extracts format (ascii/binary) and triangle count.
- **`validate_files(paths)`** -- Batch validation, returns only valid paths, logs warnings for invalid ones.

### logging_config.py
Structured logging setup using structlog.

- **`configure_logging(verbose)`** -- Configures structlog with context variable merging, log level stamping, ISO timestamps. Verbose mode uses `ConsoleRenderer()` at DEBUG level; normal mode uses `JSONRenderer()` at INFO level. Called once at CLI startup.

## Key Patterns

- **Fail-fast validation**: `validate_file_path()` raises `FileLoadError` immediately on missing or non-file paths.
- **Defensive loading**: Each loader wraps format-specific errors in `FileLoadError` with descriptive messages.
- **Structured logging**: All warnings use structlog keyword args (`path=`, `error=`) for machine-parseable output.

## Dependencies

- **Depends on**: `pathlib`, `json`, `structlog`. Optional: `yaml` (PyYAML), `struct` (for STL metadata).
- **Depended on by**: `orchestrator/runner.py` (file validation), `main.py` (logging setup).
