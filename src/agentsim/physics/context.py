"""Generic context formatters for agent prompts.

Renders domain, paradigm, and sensor data into structured prompt text
for any physics domain and experimental paradigm. No paradigm-specific
code paths -- formatters iterate over model fields generically.

Replaces hardcoded format_nlos_*_context() functions from hypothesis.py,
analyst.py, and physics_advisor.py with paradigm-agnostic equivalents.
"""

from __future__ import annotations

from agentsim.physics.domains.schema import (
    DomainKnowledge,
    ParadigmKnowledge,
    SensorCatalog,
    SensorProfile,
)


def _format_governing_equations(domain: DomainKnowledge) -> list[str]:
    """Render governing equations section from domain knowledge.

    Args:
        domain: Domain knowledge model.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    if not domain.governing_equations:
        return lines
    lines.append("### Governing Equations")
    for eq in domain.governing_equations:
        lines.append(f"- **{eq.name}**: {eq.description}")
        if eq.latex:
            lines.append(f"  LaTeX: `{eq.latex}`")
        if eq.variables:
            for var, desc in eq.variables.items():
                lines.append(f"  - {var}: {desc}")
    lines.append("")
    return lines


def _format_dimensionless_groups(domain: DomainKnowledge) -> list[str]:
    """Render dimensionless groups section.

    Args:
        domain: Domain knowledge model.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    if not domain.dimensionless_groups:
        return lines
    lines.append("### Dimensionless Groups")
    for dg in domain.dimensionless_groups:
        lines.append(f"- **{dg.name}**: `{dg.formula}` -- {dg.description}")
    lines.append("")
    return lines


def _format_reconstruction_algorithms(domain: DomainKnowledge) -> list[str]:
    """Render reconstruction algorithms section.

    Args:
        domain: Domain knowledge model.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    if not domain.reconstruction_algorithms:
        return lines
    lines.append("### Reconstruction Algorithms")
    for key, algo in domain.reconstruction_algorithms.items():
        confocal_note = " (requires confocal)" if algo.requires_confocal else ""
        lines.append(
            f"- **{algo.name}** ({algo.reference}){confocal_note}"
        )
        if algo.spatial_resolution:
            lines.append(f"  Resolution: {algo.spatial_resolution}")
        if algo.frequency_constraint:
            lines.append(f"  Frequency constraint: {algo.frequency_constraint}")
    lines.append("")
    return lines


def _format_paradigm_section(paradigm: ParadigmKnowledge) -> list[str]:
    """Render paradigm-specific section generically.

    Iterates over geometry_constraints dict, transfer_functions tuple,
    and published_baselines dict without any paradigm-specific branches.

    Args:
        paradigm: Paradigm knowledge model.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    lines.append(f"### {paradigm.paradigm} Paradigm")
    lines.append(f"{paradigm.description}")
    lines.append("")

    # Geometry constraints
    if paradigm.geometry_constraints:
        lines.append("#### Geometry Constraints")
        for constraint_name, params in paradigm.geometry_constraints.items():
            lines.append(f"- **{constraint_name}**:")
            for param_key, param_val in params.items():
                lines.append(f"  - {param_key}: {param_val}")
        lines.append("")

    # Transfer functions
    if paradigm.transfer_functions:
        lines.append("#### Transfer Functions")
        for tf in paradigm.transfer_functions:
            lines.append(
                f"- {tf.input} -> {tf.output} ({tf.relationship})"
            )
            if tf.formula:
                lines.append(f"  Formula: `{tf.formula}`")
            if tf.description:
                lines.append(f"  {tf.description}")
            if tf.coupling_strength:
                lines.append(f"  Coupling: {tf.coupling_strength}")
        lines.append("")

    # Published baselines
    if paradigm.published_baselines:
        lines.append("#### Published Baselines")
        for baseline_key, baseline_data in paradigm.published_baselines.items():
            paper = baseline_data.get("paper", baseline_key)
            venue = baseline_data.get("venue", "")
            venue_str = f" ({venue})" if venue else ""
            lines.append(f"- **{baseline_key}**: {paper}{venue_str}")
            for bk, bv in baseline_data.items():
                if bk not in ("paper", "venue"):
                    lines.append(f"  - {bk}: {bv}")
        lines.append("")

    return lines


def _format_sensor_section(
    sensor_catalog: SensorCatalog,
    paradigm: ParadigmKnowledge | None = None,
) -> list[str]:
    """Render available sensors section.

    Filters sensors by paradigm.compatible_sensor_types if paradigm
    is provided. Otherwise lists all sensors.

    Args:
        sensor_catalog: Sensor catalog model.
        paradigm: Optional paradigm for sensor type filtering.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    if not sensor_catalog.sensors:
        return lines

    compatible_types: set[str] | None = None
    if paradigm and paradigm.compatible_sensor_types:
        compatible_types = set(paradigm.compatible_sensor_types)

    filtered: dict[str, SensorProfile] = {}
    for sensor_id, profile in sensor_catalog.sensors.items():
        if compatible_types is None or profile.sensor_type in compatible_types:
            filtered[sensor_id] = profile

    if not filtered:
        return lines

    lines.append("### Available Sensors")
    for sensor_id, profile in filtered.items():
        lines.append(f"- **{profile.name}** ({sensor_id})")
        lines.append(f"  Type: {profile.sensor_type}")
        if profile.manufacturer:
            lines.append(f"  Manufacturer: {profile.manufacturer}")
        # Timing parameters
        timing = profile.timing
        if timing.temporal_resolution_ps:
            tr = timing.temporal_resolution_ps
            lines.append(
                f"  Temporal resolution: {tr.typical} ps "
                f"(range: {tr.min}-{tr.max} ps)"
            )
        if timing.jitter_fwhm_ps:
            jt = timing.jitter_fwhm_ps
            lines.append(f"  Jitter FWHM: {jt.typical} ps")
        # Spatial parameters
        spatial = profile.spatial
        lines.append(
            f"  Array: {spatial.array_size[0]}x{spatial.array_size[1]}, "
            f"pitch: {spatial.pixel_pitch_um} um, "
            f"fill factor: {spatial.fill_factor}"
        )
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_physics_context(
    domain: DomainKnowledge | None,
    *,
    paradigm: ParadigmKnowledge | None = None,
    sensor_catalog: SensorCatalog | None = None,
) -> str:
    """Render a complete physics context section for any domain/paradigm.

    The base formatter that other role-specific formatters wrap. Produces
    a structured Markdown section with governing equations, dimensionless
    groups, reconstruction algorithms, and optional paradigm/sensor data.

    Args:
        domain: Domain knowledge model (None returns empty string).
        paradigm: Optional paradigm knowledge for geometry/transfer data.
        sensor_catalog: Optional sensor catalog for hardware parameters.

    Returns:
        Formatted Markdown string, or "" if domain is None.
    """
    if domain is None:
        return ""

    lines: list[str] = []
    lines.append(f"## {domain.domain} Physics Context")
    lines.append("")
    if domain.description:
        lines.append(domain.description)
        lines.append("")

    lines.extend(_format_governing_equations(domain))
    lines.extend(_format_dimensionless_groups(domain))
    lines.extend(_format_reconstruction_algorithms(domain))

    if paradigm is not None:
        lines.extend(_format_paradigm_section(paradigm))

    if sensor_catalog is not None:
        lines.extend(_format_sensor_section(sensor_catalog, paradigm))

    return "\n".join(lines)


def format_hypothesis_context(
    domain: DomainKnowledge | None,
    *,
    paradigm: ParadigmKnowledge | None = None,
) -> str:
    """Render physics context for the hypothesis generation agent.

    Wraps format_physics_context with hypothesis-specific framing.
    Does not include sensor catalog -- hypothesis agent does not need
    hardware details.

    Args:
        domain: Domain knowledge model (None returns empty string).
        paradigm: Optional paradigm knowledge.

    Returns:
        Formatted Markdown string for hypothesis prompt.
    """
    if domain is None:
        return ""

    lines: list[str] = []
    lines.append("## Physics Context for Hypothesis Generation")
    lines.append("")
    lines.append(
        "Ground your hypothesis in the following physics. Use governing "
        "equations and dimensionless groups to constrain your proposed "
        "experiments."
    )
    lines.append("")
    lines.append(format_physics_context(domain, paradigm=paradigm))

    return "\n".join(lines)


def format_analysis_context(
    domain: DomainKnowledge | None,
    *,
    paradigm: ParadigmKnowledge | None = None,
) -> str:
    """Render physics context for the result analysis agent.

    Wraps format_physics_context with analysis-specific framing,
    adding signal physics expectations, reconstruction quality checks,
    and common failure modes.

    Args:
        domain: Domain knowledge model (None returns empty string).
        paradigm: Optional paradigm knowledge.

    Returns:
        Formatted Markdown string for analyst prompt.
    """
    if domain is None:
        return ""

    lines: list[str] = []
    lines.append("## Physics Context for Result Analysis")
    lines.append("")
    lines.append(
        "When analyzing experiment results, check these physics expectations:"
    )
    lines.append("")

    # Signal physics (generic)
    lines.append("### Signal Physics Expectations")
    lines.append(
        "- Signal should follow expected falloff patterns "
        "(inverse-square for geometric optics)"
    )
    lines.append(
        "- Peak locations should match expected path lengths"
    )
    lines.append(
        "- Signal amplitude should decrease for more distant targets"
    )
    lines.append("")

    # Paradigm-specific validation
    if paradigm is not None and paradigm.geometry_constraints:
        lines.append("### Paradigm-Specific Validation")
        for constraint_name, params in paradigm.geometry_constraints.items():
            lines.append(f"- **{constraint_name}** bounds:")
            for pk, pv in params.items():
                lines.append(f"  - {pk}: {pv}")
        lines.append("")

    # Reconstruction quality from domain
    if domain.reconstruction_algorithms:
        lines.append("### Reconstruction Quality Checks")
        for key, algo in domain.reconstruction_algorithms.items():
            checks: list[str] = []
            if algo.requires_confocal:
                checks.append("requires confocal scanning data")
            if algo.spatial_resolution:
                checks.append(algo.spatial_resolution)
            if algo.frequency_constraint:
                checks.append(algo.frequency_constraint)
            check_str = "; ".join(checks) if checks else "no specific constraints"
            lines.append(f"- **{algo.name}**: {check_str}")
        lines.append("")

    # Common failure modes (generic)
    lines.append("### Common Failure Modes")
    lines.append("- Missing or unexpected peaks in temporal data (geometry error)")
    lines.append("- Reconstruction artifacts outside physically possible volume")
    lines.append("- Resolution worse than theoretical limit (undersampled data)")
    lines.append("")

    lines.append(
        "Flag any results that violate these physics expectations "
        "as potential simulation errors."
    )

    return "\n".join(lines)


def format_scene_context(
    domain: DomainKnowledge | None,
    *,
    paradigm: ParadigmKnowledge | None = None,
    sensor_catalog: SensorCatalog | None = None,
) -> str:
    """Render full physics context for the scene generation agent (D-06).

    The scene agent gets EVERYTHING: geometry constraints, sensor parameters,
    published baselines, reconstruction requirements, and transfer functions.

    Args:
        domain: Domain knowledge model (None returns empty string).
        paradigm: Optional paradigm knowledge.
        sensor_catalog: Optional sensor catalog.

    Returns:
        Formatted Markdown string for scene prompt.
    """
    if domain is None:
        return ""

    lines: list[str] = []
    lines.append("## Physics Constraints for Scene Generation")
    lines.append("")
    lines.append(
        "Your generated simulation code MUST respect these physics "
        "constraints. Violating them will cause validation failures."
    )
    lines.append("")

    # Full physics context
    lines.append(
        format_physics_context(domain, paradigm=paradigm, sensor_catalog=sensor_catalog)
    )

    # Explicit constraint summary from paradigm
    if paradigm is not None and paradigm.geometry_constraints:
        lines.append("### Hard Constraint Summary")
        for constraint_name, params in paradigm.geometry_constraints.items():
            min_val = params.get("min_m") or params.get("min_size_m") or params.get(
                "min_width_m"
            )
            max_val = params.get("max_m") or params.get("max_size_m") or params.get(
                "max_width_m"
            )
            typical = params.get("typical_m") or params.get(
                "typical_size_m"
            ) or params.get("typical_width_m")
            if min_val is not None or max_val is not None:
                lines.append(
                    f"- **{constraint_name}**: "
                    f"min={min_val}, max={max_val}, typical={typical}"
                )
        lines.append("")

    # Sensor selection guidance
    if paradigm is not None and sensor_catalog is not None:
        if paradigm.compatible_sensor_types:
            types_str = ", ".join(paradigm.compatible_sensor_types)
            lines.append("### Sensor Selection Guidance")
            lines.append(f"Compatible sensor types: {types_str}")
            lines.append(
                "Select a named sensor profile from the catalog above "
                "and use its parameters."
            )
            lines.append("")

    # Published baselines callout
    if paradigm is not None and paradigm.published_baselines:
        lines.append("### Known-Good Starting Points")
        lines.append(
            "These published configurations are known-good starting points. "
            "Use them as defaults unless your hypothesis requires deviation."
        )
        for baseline_key, baseline_data in paradigm.published_baselines.items():
            paper = baseline_data.get("paper", baseline_key)
            lines.append(f"- {baseline_key}: {paper}")
        lines.append("")

    return "\n".join(lines)
