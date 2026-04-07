"""Deterministic physics check implementations.

Each check module exposes a pure function that takes parameters and
returns a tuple of CheckResult objects. No side effects, no LLM calls.
"""

from __future__ import annotations
