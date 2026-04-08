# Smoke Tests

End-to-end validation tests that exercise the full AgentSim physics-aware pipeline without requiring API credits. Each test runs the deterministic physics components (domain detection, constraint propagation, formula evaluation, optimizer) and a numerical simulation to confirm the physics predictions.

## Tests

### nlos_depth_resolution_test.py

**Hypothesis:** "What is the depth resolution limit of confocal NLOS with 32ps SPAD temporal bins?"

**What it exercises:**
1. **Domain detection** — identifies `nlos_transient_imaging` from hypothesis keywords
2. **Domain bundle loading** — loads relay_wall paradigm with SPAD sensors and LCT/FK/phasor algorithms from YAML
3. **Physics optimizer** — ranks 9 sensor+algorithm combos (3 sensors x 3 algorithms) using constraint propagation through transfer function graphs
4. **Formula evaluation** — computes `depth_resolution_m = c * dt / 2` via SymPy with unit prefix detection (`_ps` -> 1e-12), producing 0.00480m (4.8mm) instead of the previous incorrect 32.0m
5. **Numerical simulation** — simulates confocal three-bounce NLOS transient histograms at 5 bin widths (8-64ps), reconstructs depth via peak detection, measures error

**What it confirmed:**
- Depth resolution scales exactly as `c * dt / 2` — all actual errors are within the predicted resolution limit
- At 32ps bins: predicted 4.80mm resolution, actual 0.93mm error (well within limit)
- The jitter floor (70ps FWHM SPAD timing jitter) doesn't dominate until bin widths drop below ~16ps
- The formula evaluation fix (SymPy-based) produces physically correct values throughout the pipeline
- YAML parameters (jitter, scan geometry, relay wall size) flow correctly from domain data into the simulation

**Run:**
```bash
cd /Users/default/mas-664/sim-agents
.venv/bin/python smoke_tests/nlos_depth_resolution_test.py
```

**Output:**
```
Bin Width   Predicted dr   Actual Error   Within Limit
    8 ps        1.20 mm        0.27 mm           YES
   16 ps        2.40 mm        0.93 mm           YES
   32 ps        4.80 mm        0.93 mm           YES
   48 ps        7.20 mm        3.33 mm           YES
   64 ps        9.59 mm        3.87 mm           YES
```

Results saved to `smoke_tests/output/depth_resolution_results.json`.

## Adding New Smoke Tests

Each test should:
1. Define a hypothesis string
2. Run domain detection + optimizer (deterministic, no API)
3. Generate and execute a numerical simulation using numpy/scipy
4. Compare results against physics predictions from the constraint propagation engine
5. Save results to `smoke_tests/output/`
