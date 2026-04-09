# Optimizer Subpackage Architecture

## Purpose

Bayesian optimization of sensor parameter spaces for Pareto-optimal CRB/cost/margin tradeoffs. Given a sensor family and parameter ranges, the optimizer explores the configuration space using a Gaussian Process surrogate and Expected Improvement acquisition to find configurations that minimize CRB bounds while respecting operational cost and constraint satisfaction.

## Modules

| Module | Description |
|--------|-------------|
| `models.py` | Frozen Pydantic data models: CostWeights, ParetoPoint, BOMetadata, FamilyOptimizationResult, OptimizationResult |
| `gaussian_process.py` | Minimal GP with RBF kernel using scipy Cholesky for BO surrogate |
| `acquisition.py` | Expected Improvement acquisition function with adaptive convergence stopping |
| `pareto.py` | Non-dominated sorting and Pareto front extraction with infeasibility filtering |
| `cost.py` | Operational cost computation with configurable weight normalization |
| `scoping.py` | Scope-based filtering to select which families/parameters to optimize |
| `optimizer.py` | Main BO loop composing all modules into a complete optimization run |

## Dependency Diagram

```
optimizer.py
  |-- gaussian_process.py
  |-- acquisition.py
  |-- pareto.py
  |-- cost.py
  |-- scoping.py
  |-- models.py

scoping.py
  |-- models.py

pareto.py
  |-- models.py (ParetoPoint construction)

cost.py
  |-- models.py (CostWeights)
  |-- knowledge_graph/models.py (SensorNode, OperationalProps)

gaussian_process.py
  |-- (numpy, scipy only)

acquisition.py
  |-- gaussian_process.py (MinimalGP for predict)
  |-- (numpy, scipy only)

models.py
  |-- knowledge_graph/models.py (SensorFamily, ConfidenceQualifier)
```

## Lazy Import Strategy

This subpackage is lazily imported by `runner.py` to avoid a hard scipy/numpy dependency at startup. The optimizer is only loaded when a BO optimization step is requested, keeping the base AgentSim installation lightweight.
