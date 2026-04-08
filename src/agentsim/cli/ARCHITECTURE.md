# CLI Layer

> Terminal-based intervention gate UI for human-in-the-loop experiment review.

## Files

### __init__.py
Empty package init.

### gates.py
Implements `CliInterventionHandler` -- an interactive terminal handler that displays formatted state summaries at each checkpoint and prompts the user for actions.

**Gate checkpoints (5 total):**

1. **PRE_HYPOTHESIS** -- Shows raw hypothesis and literature context. Actions: approve, edit (revise hypothesis text), quit.

2. **POST_HYPOTHESIS** -- Shows formalized hypothesis with variables, predictions, assumptions, quality ratings, and parameter space. Actions: approve, edit (modify formalized text), redo (re-run with guidance), quit.

3. **PRE_EXECUTION** -- Shows simulation code and parameters for each scene. Actions: approve, redo (re-generate with feedback), quit.

4. **SCENE_VISUALIZATION** -- Opens rendered preview images in the default viewer (macOS `open` / Linux `xdg-open`). Shows scene preview validation status. Actions: approve, feedback (describe geometry changes), quit.

5. **POST_EXECUTION** -- Shows execution results: success/failure counts, output paths, errors, stdout tails. Actions: approve, quit.

**Shared prompt system:** `_prompt_action()` displays shortcut-labeled options (e.g., `[a]pprove`, `[e]dit`, `[r]edo`, `[q]uit`) and validates input.

Uses `click` for terminal I/O. Helper utilities: `_section()` for dividers, `_truncate()` for long output, `_open_image()` for platform-specific image viewing.

## Data Flow

```
orchestrator.runner
    |
    v
GateContext(checkpoint, state, message, preview_paths)
    |
    v
CliInterventionHandler.handle_gate()
    |-- dispatches to _gate_pre_hypothesis / _gate_post_hypothesis / etc.
    |-- displays formatted state summary via click.echo
    |-- prompts user for action
    |
    v
GateDecision(action, updated_state?, feedback_text?, reason?)
    |
    v
orchestrator.runner (applies decision: continue, edit state, redo phase, abort)
```

## Dependencies

- **Depends on**: `click`, `orchestrator.gates` (GateAction, GateCheckpoint, GateContext, GateDecision), `state.edits` (edit_hypothesis, edit_raw_hypothesis), `state.models` (ExperimentState).
- **Depended on by**: `main.py` (CLI entry point wires this handler into the orchestrator).
