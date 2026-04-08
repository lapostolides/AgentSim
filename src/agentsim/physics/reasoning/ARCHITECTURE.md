# Physics-Space Reasoning Engine

> Deterministic constraint propagation, formula evaluation, sensor+algorithm optimization, and novelty detection -- entirely in Python, no LLM calls.

## Files

### __init__.py
Package entry point. Re-exports: `propagate_constraints`, `optimize_setup`, `find_novel_regions`.

### models.py
Seven frozen Pydantic output models organized into three groups:

**Propagation outputs:**
- `ComputedValue` -- A single derived quantity: parameter name, numeric value, source input, source formula, relationship type.
- `PropagationResult` -- All computed values from BFS traversal, plus the seed inputs and any warnings.

**Optimizer outputs:**
- `ScoredSetup` -- A sensor_class + algorithm pairing with computed metrics, numeric score, and rationale.
- `OptimizerResult` -- Ranked list of `ScoredSetup` objects for a paradigm.

**Explorer outputs:**
- `NovelParameter` -- A parameter value outside published baselines, with baseline min/max and novelty type.
- `NovelExperiment` -- A proposed experiment combining novel parameters with scientific interest description.
- `ExplorerResult` -- All novel parameters and proposed experiments for a paradigm.

### formula.py
**Safe formula evaluation using SymPy.** Parses YAML formula strings (e.g., `"c * dt / 2"`) without `eval()`.

- `safe_eval_formula(formula, tf, input_value)` -- Preprocesses the formula (strips LHS, handles `^` -> `**`, rejects proportionality markers), parses via `sympy.sympify` with a restricted namespace of physical constants, identifies the single free variable, applies unit prefix conversion, and returns the computed value.
- `_detect_unit_scale(param_name)` -- Detects SI conversion factor from parameter name suffixes (e.g., `_ps` -> 1e-12, `_um` -> 1e-6).
- `_build_constants_table()` -- Auto-builds a SymPy symbol table from the `UNIVERSAL` and `COMPUTATIONAL_IMAGING` registries, mapping both full names and symbols to magnitudes. Also includes math functions (`sqrt`, `log`, `sin`, etc.).

Returns `None` for unparseable formulas (proportionality, descriptive text, multiple unknowns), allowing the caller to fall back to the relationship dispatch table.

### propagation.py
**BFS constraint propagation through transfer function graphs.**

- `build_tf_graph(transfer_functions)` -- Builds a lookup dict keyed by input parameter name. Deduplicates by (input, output) pair.
- `evaluate_tf(tf, input_value)` -- Evaluates a single transfer function. Tries `safe_eval_formula()` first (physically accurate); falls back to a relationship dispatch table (`linear`, `inverse`, `sqrt`, `quadratic`, `logarithmic`, `inverse_sqrt`, `proportional`).
- `propagate_constraints(inputs, transfer_functions)` -- Seeds BFS with input parameters, evaluates reachable TFs, cascades outputs as inputs for downstream TFs. Tracks visited edges to prevent infinite loops. Capped at 100 iterations.

### optimizer.py
**Rank sensor+algorithm combinations by propagation-derived scores.**

- `optimize_setup(hypothesis_params, bundle, paradigm)` -- Enumerates the cartesian product of compatible sensor classes and algorithms, merges transfer functions (paradigm + sensor + algorithm), propagates constraints, scores each setup, returns sorted results.
- `_compute_setup_score(result, hypothesis_params)` -- Heuristic scoring: +1 per finite computed output, +1 per well-defined relationship output, +2 per hypothesis parameter that overlaps with computed parameter names.

### explorer.py
**Find novel parameter regions outside published baselines.**

- `find_novel_regions(hypothesis_params, paradigm)` -- Builds min/max coverage ranges from all published baselines in the paradigm, compares each hypothesis parameter, flags `out_of_range` or `no_baseline` novelty.
- `_propose_experiments(hypothesis_params, novel_params)` -- Generates a proposed experiment combining all novel parameter values.

## Data Flow

### Constraint Propagation
```
inputs: {param_name: value}
    |
    v
build_tf_graph(transfer_functions)  -- adjacency list keyed by input param
    |
    v
BFS queue: [(param, value), ...]
    |
    v  for each (param, value):
evaluate_tf(tf, value)
    |-- try safe_eval_formula() (SymPy with constants + unit prefixes)
    |-- fallback: relationship dispatch table
    |
    v
ComputedValue(parameter, value, source_input, formula, relationship)
    |
    v  cascade: enqueue output if it feeds other TFs
    |
    v
PropagationResult(inputs, computed_values, warnings)
```

### Optimizer Mode
```
hypothesis_params + DomainBundle + ParadigmKnowledge
    |
    v
get_compatible_sensor_classes() x get_compatible_algorithms()
    |
    v
cartesian product: (sensor_class, algorithm)
    |
    v  for each pair:
merge TFs: paradigm.transfer_functions + sensor.transfer_functions + algorithm.transfer_functions
    |
    v
propagate_constraints(hypothesis_params, merged_tfs)
    |
    v
_compute_setup_score(propagation_result, hypothesis_params)
    |
    v
sort by score descending -> OptimizerResult
```

### Explorer Mode
```
hypothesis_params + ParadigmKnowledge.published_baselines
    |
    v
_build_covered_ranges()  -- min/max per numeric parameter across all baselines
    |
    v
_find_novel_params()     -- flag params outside ranges or absent from baselines
    |
    v
_propose_experiments()   -- combine novel params into experiment proposal
    |
    v
ExplorerResult(novel_parameters, proposed_experiments)
```

## Key Patterns

- **No eval()**: Formula evaluation uses `sympy.sympify` with a restricted local namespace. Unparseable formulas fall back to the relationship dispatch table.
- **Unit prefix detection**: Parameter name suffixes (e.g., `_ps`, `_um`, `_mm`) automatically convert between declared units and SI for formula evaluation.
- **BFS with visited-edge tracking**: Prevents infinite loops on circular transfer function graphs.
- **Immutable throughout**: Neither inputs dict nor TransferFunction tuples are mutated. PropagationResult defensive-copies the inputs dict.

## Dependencies

- **Depends on**: `sympy`, `physics.constants` (for formula constant table), `physics.domains.schema` (TransferFunction, DomainBundle, ParadigmKnowledge), `physics.domains` (compatibility filters).
- **Depended on by**: `physics.consultation` (routes reasoning queries here), `physics.context` (formats OptimizerResult for prompts).
