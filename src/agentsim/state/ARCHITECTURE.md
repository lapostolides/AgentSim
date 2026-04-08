# state

> Frozen Pydantic models defining all experiment state, pure transition functions, and serialization helpers.

## Files

### __init__.py
Barrel export of all primary models and transition functions. Consumers import from `agentsim.state` directly.

### models.py
All frozen Pydantic models (`BaseModel, frozen=True`) that make up the experiment state. Key types:

- **`ExperimentState`** -- Top-level envelope. The single object serialized between agent phases. Contains all user input, agent outputs, environment info, literature grounding, physics validations, and error tracking. Fields use tuples for immutable collections.
- **`ExperimentStatus`** enum -- Pipeline progression: `INITIALIZED` -> `LITERATURE_REVIEWED` -> `HYPOTHESIS_READY` -> `PLAN_READY` -> `SCENES_READY` -> `PHYSICS_VALIDATED` -> `EXECUTED` -> `EVALUATED` -> `ANALYZED` -> `COMPLETED` (or `FAILED`).
- **`Hypothesis`** -- Structured hypothesis with `raw_text`, `formalized`, `variables`, `parameter_space`, `predictions`, `assumptions`, and `quality_ratings`.
- **`QualityRatings`** -- Six-dimension self-assessment scores (0.0-1.0) plus composite and reasoning.
- **`ParameterSpec`** -- Single parameter definition with name, description, discrete values or continuous range.
- **`SceneSpec`** -- Generated simulation code with parameters and file references.
- **`ScenePreview`** -- Preview render metadata (path, validity, warnings).
- **`ExecutionResult`** -- Scene execution outcome (status, outputs, timing, errors).
- **`EvaluationResult`** -- Metrics and ground-truth comparison for a scene.
- **`AnalysisReport`** -- Analyst output: findings, confidence, hypothesis support, next experiments, and the critical `should_stop` flag.
- **`LiteratureEntry`** -- Single paper with verification status (verified/unverified/fabricated).
- **`OpenQuestion`** -- Research gap with significance explanation.
- **`LiteratureContext`** -- Full literature review: entries, summary, open questions, trivial gaps, methodology notes.
- **`LiteratureValidation`** -- Post-analysis check against literature with confidence adjustment.
- **`PhysicsRecommendation`** -- Physics-space reasoning results (optimizer and/or explorer).
- **`FileReference`**, **`AvailablePackage`**, **`EnvironmentInfo`**, **`ExperimentPlan`** -- Supporting types.

Helper functions: `_new_id()` (12-char UUID hex), `_now()` (UTC datetime).

### transitions.py
Pure state transition functions. Every function takes an `ExperimentState` (plus new data) and returns a new `ExperimentState` via `model_copy(update={...})`. No mutation.

Primary transitions (each advances `status`):
- `start_experiment(hypothesis_text, file_paths)` -> new state with `INITIALIZED`
- `set_literature_context(state, context)` -> `LITERATURE_REVIEWED`
- `add_hypothesis(state, hypothesis)` -> `HYPOTHESIS_READY`
- `add_plan(state, plan)` -> `PLAN_READY`
- `add_scenes(state, scenes)` -> `SCENES_READY`
- `add_physics_validation(state, validation)` -> `PHYSICS_VALIDATED`
- `add_execution_result(state, result)` -> `EXECUTED`
- `add_evaluation(state, evaluation)` -> `EVALUATED`
- `add_analysis(state, report)` -> `ANALYZED` or `COMPLETED` (if `should_stop`)

Supplementary transitions (no status change):
- `set_environment()`, `set_literature_validation()`, `add_scene_preview()`, `set_consultation_summary()`, `set_physics_recommendation()`, `add_error()`

Terminal: `mark_failed(state, error)` -> `FAILED`.

Also contains `_detect_file_type()` for mapping file extensions to categories.

### edits.py
Pure helper functions for creating edited copies of frozen state. Used by intervention gates when users modify state mid-pipeline.

- `edit_raw_hypothesis(state, new_text)` -- Replace raw hypothesis text
- `edit_hypothesis(state, **updates)` -- Update arbitrary hypothesis fields
- `replace_scenes(state, scenes)` -- Replace all scenes and clear previews

### serialization.py
JSON serialization helpers for passing state between agent phases.

- `serialize_state(state)` / `deserialize_state(json_str)` -- Full roundtrip via Pydantic's `model_dump_json` / `model_validate_json`
- `serialize_model(model)` / `deserialize_model(json_str, model_class)` -- Generic versions for any Pydantic model
- `state_to_prompt_context(state, max_length=50_000)` -- Formats state as an `<experiment_state>` XML block for agent prompts. If serialized state exceeds `max_length`, truncates by keeping essential fields (id, status, iteration, hypothesis, plan, literature_context) and only the latest analysis.

## Data Flow

```
start_experiment()
    |
    v
ExperimentState (frozen)
    |
    +-- serialize to JSON --> agent prompt context
    |
    +-- agent produces output --> runner extracts JSON
    |
    +-- transition function(state, new_data) --> NEW ExperimentState
    |
    +-- repeat for each phase
```

## Key Patterns

- **Immutability**: Every model uses `frozen=True`. Collections use tuples (not lists) for hashability. New state is always created via `model_copy(update={...})`.
- **Status progression**: `ExperimentStatus` enum tracks pipeline phase. Each transition function advances status to the appropriate next value.
- **Accumulation**: Results are appended to tuples across iterations: `(*state.scenes, new_scene)`. This preserves full history.
- **Truncation for context windows**: `state_to_prompt_context()` handles long experiments by keeping only essential fields plus the latest analysis when state exceeds 50K characters.

## Dependencies

- **Depends on**: `pydantic`, `agentsim.physics.models` (PhysicsValidation, PhysicsConsultationSummary), `agentsim.physics.reasoning.models` (ExplorerResult, OptimizerResult)
- **Depended on by**: Every other subpackage. This is the foundational data layer.
