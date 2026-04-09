"""Parameter sensitivity analysis via Morris method / Elementary Effects (CRB-05, D-08).

Morris method: randomized OAT trajectories that capture both individual effects
(mu_star = mean absolute elementary effect) and interaction effects (sigma =
standard deviation of elementary effects). More informative than plain OAT
with minimal extra cost.

For each trajectory (default r=10):
  1. Sample a random scaling factor for the perturbation
  2. For each parameter, perturb one at a time by delta
  3. Compute elementary effect: EE_i = (CRB(p+dp_i) - CRB(p)) / dp_i

Aggregate across trajectories:
  mu_star_i = mean(|EE_i|)  -- importance (how much param matters)
  sigma_i = std(EE_i)       -- interaction (nonlinear/interactive effects)

Classification: mu_star < threshold -> negligible, sigma/mu_star < 0.5 -> linear,
sigma/mu_star >= 0.5 -> nonlinear/interactive

Default perturbation_fraction=0.1, num_trajectories=10.
"""

from __future__ import annotations

import math
import random

from pydantic import BaseModel

from agentsim.knowledge_graph.crb.dispatch import compute_crb
from agentsim.knowledge_graph.crb.models import SensitivityEntry
from agentsim.knowledge_graph.models import SensorNode


class SensitivityResult(BaseModel, frozen=True):
    """Result of a Morris method sensitivity analysis run (D-09)."""

    sensor_name: str
    estimation_task: str
    baseline_crb: float
    num_trajectories: int
    entries: tuple[SensitivityEntry, ...] = ()


def _locate_parameter(sensor: SensorNode, param_name: str) -> float:
    """Find a numeric parameter value in sensor family_specs or property groups.

    Args:
        sensor: Sensor node to search.
        param_name: Parameter name to locate.

    Returns:
        The numeric value.

    Raises:
        ValueError: If parameter not found or not numeric.
    """
    # Search family_specs first
    if param_name in sensor.family_specs:
        val = sensor.family_specs[param_name]
        if isinstance(val, (int, float)):
            return float(val)
        raise ValueError(
            f"Parameter '{param_name}' in family_specs is not numeric: {val!r}"
        )

    # Search property groups (geometric, temporal, radiometric)
    for group_name in ("geometric", "temporal", "radiometric"):
        group = getattr(sensor, group_name, None)
        if group is not None and hasattr(group, param_name):
            val = getattr(group, param_name)
            if isinstance(val, (int, float)):
                return float(val)

    raise ValueError(
        f"Parameter '{param_name}' not found in sensor '{sensor.name}' "
        f"family_specs or property groups"
    )


def _perturb_sensor(
    sensor: SensorNode,
    param_name: str,
    delta: float,
) -> SensorNode:
    """Create a new SensorNode with one parameter perturbed by delta.

    Uses immutable model_copy -- never mutates the original (Pitfall 4).

    Args:
        sensor: Original sensor.
        param_name: Parameter to perturb.
        delta: Amount to add to the parameter value.

    Returns:
        New SensorNode with the perturbed value.
    """
    if param_name in sensor.family_specs:
        nominal = float(sensor.family_specs[param_name])
        new_specs = {**sensor.family_specs, param_name: nominal + delta}
        return sensor.model_copy(update={"family_specs": new_specs})

    # Search property groups
    for group_name in ("geometric", "temporal", "radiometric"):
        group = getattr(sensor, group_name, None)
        if group is not None and hasattr(group, param_name):
            new_group = group.model_copy(update={param_name: getattr(group, param_name) + delta})
            return sensor.model_copy(update={group_name: new_group})

    raise ValueError(f"Cannot perturb '{param_name}' -- not found in sensor")


def _classify(mu_star: float, sigma: float, max_mu_star: float) -> str:
    """Classify parameter effect based on Morris method thresholds.

    Args:
        mu_star: Mean absolute elementary effect for this parameter.
        sigma: Standard deviation of elementary effects.
        max_mu_star: Maximum mu_star across all parameters.

    Returns:
        Classification string: negligible, linear, or nonlinear.
    """
    if max_mu_star == 0.0 or mu_star < 0.01 * max_mu_star:
        return "negligible"
    ratio = sigma / mu_star if mu_star > 0.0 else 0.0
    if ratio < 0.5:
        return "linear"
    return "nonlinear"


def compute_sensitivity(
    sensor: SensorNode,
    parameters: list[str],
    *,
    perturbation_fraction: float = 0.1,
    num_trajectories: int = 10,
    estimation_task: str = "",
    snr: float = 100.0,
    target_depth_m: float = 5.0,
    n_photons: int = 10000,
    seed: int | None = 42,
) -> SensitivityResult:
    """Run Morris method sensitivity analysis on sensor parameters.

    Computes elementary effects across multiple randomized trajectories
    to determine parameter importance (mu_star) and interaction effects
    (sigma).

    Args:
        sensor: Sensor node to analyze.
        parameters: List of parameter names to perturb.
        perturbation_fraction: Fractional perturbation size (default 10%).
        num_trajectories: Number of randomized OAT trajectories.
        estimation_task: Override for CRB estimation task.
        snr: Signal-to-noise ratio passed to compute_crb.
        target_depth_m: Target depth passed to compute_crb.
        n_photons: Photon count passed to compute_crb.
        seed: Random seed for reproducibility (None for non-deterministic).

    Returns:
        SensitivityResult with ranked entries.

    Raises:
        ValueError: If any parameter name is not found in the sensor.
    """
    rng = random.Random(seed)

    crb_kwargs = {
        "snr": snr,
        "target_depth_m": target_depth_m,
        "n_photons": n_photons,
    }

    # Compute baseline CRB
    baseline_result = compute_crb(sensor, estimation_task, **crb_kwargs)
    baseline_crb = baseline_result.bound_value

    if not parameters:
        return SensitivityResult(
            sensor_name=sensor.name,
            estimation_task=estimation_task or baseline_result.estimation_task,
            baseline_crb=baseline_crb,
            num_trajectories=num_trajectories,
            entries=(),
        )

    # Validate all parameters exist and are numeric before starting
    nominal_values: dict[str, float] = {}
    for param in parameters:
        nominal_values[param] = _locate_parameter(sensor, param)

    # Collect elementary effects across trajectories
    elementary_effects: dict[str, list[float]] = {p: [] for p in parameters}

    for _traj in range(num_trajectories):
        # Random trajectory scale: uniform in [0.5*fraction, 1.5*fraction]
        trajectory_scale = rng.uniform(0.5, 1.5)

        for param in parameters:
            nominal = nominal_values[param]
            delta = perturbation_fraction * nominal * trajectory_scale

            if abs(delta) < 1e-30:
                # Parameter is zero or near-zero; use absolute perturbation
                delta = perturbation_fraction * trajectory_scale

            perturbed = _perturb_sensor(sensor, param, delta)
            perturbed_result = compute_crb(perturbed, estimation_task, **crb_kwargs)
            perturbed_crb = perturbed_result.bound_value

            # Elementary effect
            ee = (perturbed_crb - baseline_crb) / delta
            elementary_effects[param].append(ee)

    # Aggregate: mu_star = mean(|EE|), sigma = std(EE)
    raw_entries: list[tuple[str, float, float, float]] = []
    for param in parameters:
        ees = elementary_effects[param]
        mu_star = sum(abs(e) for e in ees) / len(ees)
        mean_ee = sum(ees) / len(ees)
        sigma = math.sqrt(sum((e - mean_ee) ** 2 for e in ees) / len(ees))
        raw_entries.append((param, nominal_values[param], mu_star, sigma))

    # Find max mu_star for classification threshold
    max_mu_star = max(entry[2] for entry in raw_entries) if raw_entries else 0.0

    # Sort by mu_star descending, assign ranks
    raw_entries.sort(key=lambda x: x[2], reverse=True)

    entries: list[SensitivityEntry] = []
    for rank, (param, nominal, mu_star, sigma) in enumerate(raw_entries, start=1):
        classification = _classify(mu_star, sigma, max_mu_star)
        entries.append(
            SensitivityEntry(
                parameter_name=param,
                nominal_value=nominal,
                mu_star=mu_star,
                sigma=sigma,
                classification=classification,
                sensitivity=mu_star,  # backward compat: mu_star as sensitivity
                rank=rank,
            )
        )

    return SensitivityResult(
        sensor_name=sensor.name,
        estimation_task=estimation_task or baseline_result.estimation_task,
        baseline_crb=baseline_crb,
        num_trajectories=num_trajectories,
        entries=tuple(entries),
    )
