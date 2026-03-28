"""Terminal-based intervention gate handler.

Displays formatted state summaries at each checkpoint and prompts
the user for an action (approve, edit, redo, quit, feedback).
"""

from __future__ import annotations

import platform
import subprocess
import textwrap

import click

from agentsim.orchestrator.gates import (
    GateAction,
    GateCheckpoint,
    GateContext,
    GateDecision,
)
from agentsim.state.edits import edit_hypothesis, edit_raw_hypothesis
from agentsim.state.models import ExperimentState


_DIVIDER = "─" * 60
_HEADER = "═" * 60


def _section(title: str) -> str:
    return f"\n{_DIVIDER}\n  {title}\n{_DIVIDER}"


def _truncate(text: str, max_lines: int = 30) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n  ... ({len(lines) - max_lines} more lines)"


def _open_image(path: str) -> None:
    """Open an image file in the default viewer (macOS/Linux)."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Linux":
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass  # silently skip if viewer unavailable


class CliInterventionHandler:
    """Interactive terminal handler for intervention gates."""

    async def handle_gate(self, context: GateContext) -> GateDecision:
        dispatch = {
            GateCheckpoint.PRE_HYPOTHESIS: self._gate_pre_hypothesis,
            GateCheckpoint.POST_HYPOTHESIS: self._gate_post_hypothesis,
            GateCheckpoint.PRE_EXECUTION: self._gate_pre_execution,
            GateCheckpoint.SCENE_VISUALIZATION: self._gate_scene_visualization,
            GateCheckpoint.POST_EXECUTION: self._gate_post_execution,
        }
        handler = dispatch[context.checkpoint]
        return handler(context)

    # ── Gate 1: Pre-hypothesis ───────────────────────────────────────

    def _gate_pre_hypothesis(self, ctx: GateContext) -> GateDecision:
        state = ctx.state
        click.echo(f"\n{_HEADER}")
        click.echo("  GATE: Pre-Hypothesis Review")
        click.echo(_HEADER)

        click.echo(f"\n  Raw hypothesis: {state.raw_hypothesis}")

        if state.literature_context:
            lit = state.literature_context
            click.echo(f"\n  Literature: {len(lit.entries)} papers found")
            if lit.summary:
                click.echo(f"  Summary: {lit.summary[:300]}...")
            if lit.open_questions:
                click.echo("  Open questions:")
                for q in lit.open_questions[:5]:
                    click.echo(f"    - {q.question}")

        click.echo(f"\n  {ctx.message}")

        action = self._prompt_action(["approve", "edit", "quit"])

        if action == "edit":
            new_text = click.prompt(
                "  Revised hypothesis",
                default=state.raw_hypothesis,
            )
            new_state = edit_raw_hypothesis(state, new_text)
            return GateDecision(action=GateAction.EDIT, updated_state=new_state)

        if action == "quit":
            return GateDecision(action=GateAction.ABORT, reason="User quit at pre-hypothesis")

        return GateDecision(action=GateAction.APPROVE)

    # ── Gate 2: Post-hypothesis ──────────────────────────────────────

    def _gate_post_hypothesis(self, ctx: GateContext) -> GateDecision:
        state = ctx.state
        hyp = state.hypothesis

        click.echo(f"\n{_HEADER}")
        click.echo("  GATE: Post-Hypothesis Review")
        click.echo(_HEADER)

        if hyp:
            click.echo(f"\n  Raw:        {hyp.raw_text[:120]}")
            click.echo(f"  Formalized: {hyp.formalized[:200]}")

            if hyp.variables:
                click.echo(f"  Variables:  {', '.join(hyp.variables)}")
            if hyp.predictions:
                click.echo("  Predictions:")
                for p in hyp.predictions:
                    click.echo(f"    - {p}")
            if hyp.assumptions:
                click.echo("  Assumptions:")
                for a in hyp.assumptions:
                    click.echo(f"    - {a}")

            if hyp.quality_ratings:
                qr = hyp.quality_ratings
                click.echo("\n  Quality Ratings:")
                click.echo(f"    Decision relevance:     {qr.decision_relevance:.2f}")
                click.echo(f"    Non-triviality:         {qr.non_triviality:.2f}")
                click.echo(f"    Informative either way: {qr.informative_either_way:.2f}")
                click.echo(f"    Actionability:          {qr.downstream_actionability:.2f}")
                click.echo(f"    Expected impact:        {qr.expected_impact:.2f}")
                click.echo(f"    Falsifiability:         {qr.falsifiability:.2f}")
                click.echo(f"    ── Composite:           {qr.composite_score:.2f}")

            if hyp.parameter_space:
                click.echo("\n  Parameter Space:")
                for ps in hyp.parameter_space:
                    if ps.values:
                        click.echo(f"    {ps.name}: {ps.values}")
                    elif ps.range_min is not None:
                        click.echo(f"    {ps.name}: [{ps.range_min}, {ps.range_max}] step={ps.step}")
        else:
            click.echo("  (No hypothesis produced)")

        click.echo(f"\n  {ctx.message}")

        action = self._prompt_action(["approve", "edit", "redo", "quit"])

        if action == "edit":
            new_formalized = click.prompt(
                "  Edit formalized hypothesis (Enter to keep)",
                default=hyp.formalized if hyp else "",
            )
            new_state = edit_hypothesis(state, formalized=new_formalized)
            return GateDecision(action=GateAction.EDIT, updated_state=new_state)

        if action == "redo":
            guidance = click.prompt("  Guidance for re-formalization")
            return GateDecision(action=GateAction.REDO, feedback_text=guidance)

        if action == "quit":
            return GateDecision(action=GateAction.ABORT, reason="User quit at post-hypothesis")

        return GateDecision(action=GateAction.APPROVE)

    # ── Gate 3: Pre-execution ────────────────────────────────────────

    def _gate_pre_execution(self, ctx: GateContext) -> GateDecision:
        state = ctx.state

        click.echo(f"\n{_HEADER}")
        click.echo("  GATE: Pre-Execution Review (Simulation Code & Parameters)")
        click.echo(_HEADER)

        for i, scene in enumerate(state.scenes):
            click.echo(f"\n  Scene {i + 1} (id: {scene.id}):")
            if scene.parameters:
                click.echo("  Parameters:")
                for k, v in scene.parameters.items():
                    if k == "scene_description":
                        click.echo(f"    {k}: <scene geometry dict>")
                    else:
                        val_str = str(v)[:100]
                        click.echo(f"    {k}: {val_str}")
            if scene.code:
                click.echo(_section("Code Preview"))
                click.echo(_truncate(scene.code, max_lines=40))

        click.echo(f"\n  {ctx.message}")

        action = self._prompt_action(["approve", "redo", "quit"])

        if action == "redo":
            feedback = click.prompt("  Feedback for scene re-generation")
            return GateDecision(action=GateAction.REDO, feedback_text=feedback)

        if action == "quit":
            return GateDecision(action=GateAction.ABORT, reason="User quit at pre-execution")

        return GateDecision(action=GateAction.APPROVE)

    # ── Gate 4: Scene visualization ──────────────────────────────────

    def _gate_scene_visualization(self, ctx: GateContext) -> GateDecision:
        click.echo(f"\n{_HEADER}")
        click.echo("  GATE: Scene Visualization Review")
        click.echo(_HEADER)

        if ctx.preview_paths:
            click.echo(f"\n  {len(ctx.preview_paths)} preview(s) rendered:")
            for path in ctx.preview_paths:
                click.echo(f"    {path}")
                _open_image(path)
            click.echo("\n  (Images opened in default viewer)")
        else:
            click.echo("\n  No preview images available.")

        # Show scene preview status
        for preview in ctx.state.scene_previews:
            status = "ok" if preview.is_valid else "FAILED"
            click.echo(f"  Scene {preview.scene_id}: {status}")
            for w in preview.warnings:
                click.echo(f"    warning: {w}")

        click.echo(f"\n  {ctx.message}")

        action = self._prompt_action(["approve", "feedback", "quit"])

        if action == "feedback":
            feedback = click.prompt(
                "  Describe what to change in the scene geometry"
            )
            return GateDecision(action=GateAction.FEEDBACK, feedback_text=feedback)

        if action == "quit":
            return GateDecision(action=GateAction.ABORT, reason="User quit at scene visualization")

        return GateDecision(action=GateAction.APPROVE)

    # ── Gate 5: Post-execution ───────────────────────────────────────

    def _gate_post_execution(self, ctx: GateContext) -> GateDecision:
        state = ctx.state

        click.echo(f"\n{_HEADER}")
        click.echo("  GATE: Post-Execution Review")
        click.echo(_HEADER)

        if state.execution_results:
            successes = sum(1 for r in state.execution_results if r.status == "success")
            failures = len(state.execution_results) - successes
            click.echo(f"\n  Results: {successes} success, {failures} failed")

            for r in state.execution_results:
                icon = "ok" if r.status == "success" else "FAIL"
                click.echo(f"\n  [{icon}] Scene {r.scene_id} ({r.duration_seconds:.1f}s)")
                if r.output_paths:
                    click.echo(f"    Outputs: {', '.join(r.output_paths[:5])}")
                if r.error_message:
                    click.echo(f"    Error: {r.error_message[:200]}")
                if r.stdout:
                    click.echo("    stdout (last 5 lines):")
                    for line in r.stdout.strip().splitlines()[-5:]:
                        click.echo(f"      {line}")
        else:
            click.echo("\n  No execution results yet.")

        click.echo(f"\n  {ctx.message}")

        action = self._prompt_action(["approve", "quit"])

        if action == "quit":
            return GateDecision(action=GateAction.ABORT, reason="User quit at post-execution")

        return GateDecision(action=GateAction.APPROVE)

    # ── Shared prompt ────────────────────────────────────────────────

    def _prompt_action(self, options: list[str]) -> str:
        """Show an action prompt and return the chosen action."""
        shortcuts = {
            "approve": ("a", "approve"),
            "edit": ("e", "edit"),
            "redo": ("r", "redo"),
            "quit": ("q", "quit"),
            "feedback": ("f", "feedback"),
        }

        labels = []
        valid_inputs: dict[str, str] = {}
        for opt in options:
            short, full = shortcuts[opt]
            labels.append(f"[{short}]{full[1:]}")
            valid_inputs[short] = opt
            valid_inputs[full] = opt

        prompt_text = "  " + "  ".join(labels)

        while True:
            choice = click.prompt(prompt_text, type=str).strip().lower()
            if choice in valid_inputs:
                return valid_inputs[choice]
            click.echo(f"  Invalid choice '{choice}'. Options: {', '.join(labels)}")
