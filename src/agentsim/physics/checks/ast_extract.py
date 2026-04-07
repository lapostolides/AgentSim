"""AST-based parameter extraction from generated Python simulation code.

Parses Python source to extract physics parameters (variable assignments,
dict literals, keyword arguments, subscript assignments), detect solver
types (implicit vs explicit), and find mesh file paths.
"""

from __future__ import annotations

import ast

from agentsim.physics.models import (
    ASTExtractionResult,
    CheckResult,
    ExtractedParameter,
    ExtractedSimulationParams,
    Severity,
)

# Solver classification sets
IMPLICIT_SOLVERS: frozenset[str] = frozenset(
    {"BDF", "Radau", "LSODA", "odeint", "solve_ivp_implicit"}
)

EXPLICIT_SOLVERS: frozenset[str] = frozenset(
    {"RK45", "RK23", "DOP853", "euler", "leapfrog"}
)

# Functions that load mesh files
MESH_LOAD_FUNCTIONS: frozenset[str] = frozenset(
    {"load", "load_mesh", "Trimesh", "import_mesh"}
)

# Known physics parameter names that map to ExtractedSimulationParams fields
PHYSICS_PARAM_PATTERNS: frozenset[str] = frozenset(
    {
        "dt",
        "timestep",
        "time_step",
        "delta_t",
        "velocity",
        "speed",
        "density",
        "viscosity",
        "dx",
        "mesh_spacing",
        "grid_spacing",
        "wavelength",
        "aperture",
        "focal_length",
    }
)

# Mapping from parameter names to ExtractedSimulationParams field names
_TIMESTEP_NAMES = frozenset({"dt", "timestep", "time_step", "delta_t"})
_VELOCITY_NAMES = frozenset({"velocity", "speed"})
_MESH_SPACING_NAMES = frozenset({"dx", "mesh_spacing", "grid_spacing"})


class PhysicsParameterVisitor(ast.NodeVisitor):
    """AST visitor that extracts physics parameters from Python source code.

    Handles simple assignments, dict literals, keyword arguments,
    subscript assignments, solver type detection, and mesh path discovery.
    """

    def __init__(self) -> None:
        self.parameters: list[ExtractedParameter] = []
        self.function_calls: list[str] = []
        self.solver_type: str = "unknown"
        self.mesh_paths: list[str] = []
        self.velocity: float | None = None
        self.timestep: float | None = None
        self.mesh_spacing: float | None = None

    def visit_Assign(self, node: ast.Assign) -> None:
        """Extract parameters from simple and subscript assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                value = self._extract_constant(node.value)
                if value is not None:
                    self.parameters.append(
                        ExtractedParameter(
                            name=target.id,
                            value=value,
                            line=node.lineno,
                        )
                    )
            elif isinstance(target, ast.Subscript):
                # Handle config["dt"] = 0.001
                if isinstance(target.slice, ast.Constant) and isinstance(
                    target.slice.value, str
                ):
                    value = self._extract_constant(node.value)
                    if value is not None:
                        self.parameters.append(
                            ExtractedParameter(
                                name=target.slice.value,
                                value=value,
                                line=node.lineno,
                            )
                        )
        # Also visit the value side for dict literals
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        """Extract parameters from dictionary literals."""
        for key, val in zip(node.keys, node.values):
            if (
                key is not None
                and isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                extracted = self._extract_constant(val)
                if extracted is not None:
                    self.parameters.append(
                        ExtractedParameter(
                            name=key.value,
                            value=extracted,
                            line=node.lineno,
                        )
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Extract keyword args, detect solver type, and find mesh loads."""
        func_name = self._get_call_name(node)
        if func_name is not None:
            self.function_calls.append(func_name)

        # Extract keyword arguments with numeric values
        for kw in node.keywords:
            if kw.arg is not None:
                if kw.arg == "method" and isinstance(kw.value, ast.Constant):
                    method_str = str(kw.value.value)
                    if method_str in IMPLICIT_SOLVERS:
                        self.solver_type = "implicit"
                    elif method_str in EXPLICIT_SOLVERS:
                        self.solver_type = "explicit"
                else:
                    value = self._extract_constant(kw.value)
                    if value is not None:
                        self.parameters.append(
                            ExtractedParameter(
                                name=kw.arg,
                                value=value,
                                line=node.lineno,
                            )
                        )

        # Detect mesh loading
        if func_name is not None:
            # Get the bare function name (last part after dots)
            bare_name = func_name.rsplit(".", maxsplit=1)[-1]
            if bare_name in MESH_LOAD_FUNCTIONS:
                # Extract first positional string argument as mesh path
                if node.args and isinstance(node.args[0], ast.Constant):
                    arg_val = node.args[0].value
                    if isinstance(arg_val, str):
                        self.mesh_paths.append(arg_val)

        self.generic_visit(node)

    def _extract_constant(self, node: ast.expr) -> float | None:
        """Extract a numeric constant from an AST node.

        Handles ast.Constant (int/float) and ast.UnaryOp(USub) for negatives.
        Returns None for non-numeric nodes.
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = self._extract_constant(node.operand)
            if inner is not None:
                return -inner
        return None

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the full dotted name of a function call.

        Handles ast.Name (simple calls) and ast.Attribute (method calls).
        """
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts = []
            current: ast.expr = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _map_known_params(self) -> None:
        """Map known physics parameter names to typed fields.

        Scans extracted parameters and populates velocity, timestep,
        and mesh_spacing fields from recognized names.
        """
        for param in self.parameters:
            lower_name = param.name.lower()
            if lower_name in _TIMESTEP_NAMES and self.timestep is None:
                self.timestep = param.value
            elif lower_name in _VELOCITY_NAMES and self.velocity is None:
                self.velocity = param.value
            elif lower_name in _MESH_SPACING_NAMES and self.mesh_spacing is None:
                self.mesh_spacing = param.value


def extract_physics_from_ast(code: str) -> ASTExtractionResult:
    """Extract physics parameters from Python source code via AST analysis.

    Args:
        code: Python source code string to analyze.

    Returns:
        ASTExtractionResult with extracted parameters and any issues found.
        On syntax error, returns a result with an ERROR-level issue.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return ASTExtractionResult(
            params=ExtractedSimulationParams(),
            issues=(
                CheckResult(
                    check="ast_extract",
                    severity=Severity.ERROR,
                    message=f"Failed to parse code: {exc}",
                ),
            ),
        )

    visitor = PhysicsParameterVisitor()
    visitor.visit(tree)
    visitor._map_known_params()

    return ASTExtractionResult(
        params=ExtractedSimulationParams(
            parameters=tuple(visitor.parameters),
            solver_type=visitor.solver_type,
            velocity=visitor.velocity,
            timestep=visitor.timestep,
            mesh_spacing=visitor.mesh_spacing,
            mesh_paths=tuple(visitor.mesh_paths),
            function_calls=tuple(visitor.function_calls),
        ),
    )
