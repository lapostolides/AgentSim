"""Per-run output directory management.

Each experiment run gets its own timestamped directory under the configured
output root. All artifacts (state snapshots, generated scripts, logs,
results) are saved within that directory, so successive runs never
overwrite each other.

Directory layout for a run::

    output/
    └── 2026-04-08_13-05-32_a1b2c3d4/
        ├── run_metadata.json        # Run ID, hypothesis, timestamps, config
        ├── state_initial.json       # State after initialization
        ├── state_iter_001.json      # State after iteration 1
        ├── state_iter_002.json      # State after iteration 2
        ├── state_final.json         # Final state
        ├── scripts/
        │   ├── scene_001.py         # Generated simulation code
        │   └── scene_002.py
        ├── results/
        │   ├── scene_001_stdout.txt # Captured stdout
        │   └── scene_001_metrics.json
        └── logs/
            └── experiment.jsonl     # Structured log events
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import structlog

from agentsim.state.serialization import serialize_state

logger = structlog.get_logger()


def _timestamp_slug() -> str:
    """UTC timestamp formatted for filesystem use: ``2026-04-08_13-05-32``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def create_run_directory(
    output_root: Path,
    experiment_id: str,
) -> Path:
    """Create a unique run directory under the output root.

    Format: ``{output_root}/{timestamp}_{experiment_id[:8]}/``

    Args:
        output_root: Parent directory for all runs (e.g., ``./output``).
        experiment_id: The ExperimentState.id (hex string).

    Returns:
        Path to the created run directory.
    """
    slug = f"{_timestamp_slug()}_{experiment_id[:8]}"
    run_dir = output_root / slug
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (run_dir / "scripts").mkdir(exist_ok=True)
    (run_dir / "results").mkdir(exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)

    return run_dir


def save_run_metadata(
    run_dir: Path,
    experiment_id: str,
    hypothesis: str,
    config_dict: dict,
) -> Path:
    """Write run metadata to ``run_metadata.json``.

    Args:
        run_dir: The run directory.
        experiment_id: Experiment ID.
        hypothesis: Raw hypothesis text.
        config_dict: Serialized orchestrator config.

    Returns:
        Path to the metadata file.
    """
    metadata = {
        "experiment_id": experiment_id,
        "hypothesis": hypothesis,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": config_dict,
    }
    path = run_dir / "run_metadata.json"
    path.write_text(json.dumps(metadata, indent=2, default=str))
    logger.info("run_metadata_saved", path=str(path))
    return path


def save_state_snapshot(
    run_dir: Path,
    state: object,
    label: str,
) -> Path:
    """Save a state snapshot with a descriptive label.

    Args:
        run_dir: The run directory.
        state: ExperimentState to serialize.
        label: Snapshot label (e.g., ``"initial"``, ``"iter_001"``, ``"final"``).

    Returns:
        Path to the saved file.
    """
    path = run_dir / f"state_{label}.json"
    path.write_text(serialize_state(state))
    logger.info("state_snapshot_saved", label=label, path=str(path))
    return path


def save_scene_script(
    run_dir: Path,
    scene_id: str,
    code: str,
) -> Path:
    """Save a generated simulation script.

    Args:
        run_dir: The run directory.
        scene_id: Scene identifier.
        code: Python source code.

    Returns:
        Path to the saved script.
    """
    safe_id = scene_id.replace("/", "_").replace(" ", "_")
    path = run_dir / "scripts" / f"{safe_id}.py"
    path.write_text(code)
    logger.info("scene_script_saved", scene_id=scene_id, path=str(path))
    return path


def save_execution_result(
    run_dir: Path,
    scene_id: str,
    stdout: str = "",
    stderr: str = "",
    metrics: dict | None = None,
) -> Path:
    """Save execution output for a scene.

    Args:
        run_dir: The run directory.
        scene_id: Scene identifier.
        stdout: Captured standard output.
        stderr: Captured standard error.
        metrics: Optional metrics dict.

    Returns:
        Path to the results subdirectory for this scene.
    """
    safe_id = scene_id.replace("/", "_").replace(" ", "_")
    results_dir = run_dir / "results"

    if stdout:
        (results_dir / f"{safe_id}_stdout.txt").write_text(stdout)
    if stderr:
        (results_dir / f"{safe_id}_stderr.txt").write_text(stderr)
    if metrics:
        (results_dir / f"{safe_id}_metrics.json").write_text(
            json.dumps(metrics, indent=2, default=str),
        )

    logger.info("execution_result_saved", scene_id=scene_id, path=str(results_dir))
    return results_dir


def append_log_event(run_dir: Path, event: dict) -> None:
    """Append a structured log event to the run's JSONL log file.

    Args:
        run_dir: The run directory.
        event: Log event dict.
    """
    path = run_dir / "logs" / "experiment.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def finalize_run(run_dir: Path) -> None:
    """Update run metadata with completion timestamp.

    Args:
        run_dir: The run directory.
    """
    meta_path = run_dir / "run_metadata.json"
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text())
        metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
        meta_path.write_text(json.dumps(metadata, indent=2, default=str))
        logger.info("run_finalized", path=str(run_dir))
