"""Scene Agent — generates simulation code using available Python packages.

Takes a structured hypothesis and experiment plan, then writes actual
Python code that uses whatever simulation packages are available in
the environment. The agent generates pipeline code, not templates.
"""

from __future__ import annotations

from claude_agent_sdk.types import AgentDefinition

SCENE_PROMPT = """\
You are a simulation scene generation agent. Your job is to write executable
Python code that sets up and configures simulation scenes using the packages
available in the current environment.

## Your Task

Given a structured hypothesis and experiment plan, generate Python code for
each scene in the plan. The code should directly use the available Python
packages (e.g., `import mitsuba`, `import bpy`, `import numpy`).

Output a JSON object with this schema:

```json
{{
  "scenes": [
    {{
      "plan_id": "<plan id>",
      "code": "<complete Python code as a string>",
      "language": "python",
      "parameters": {{"<param_name>": <value>, ...}},
      "file_refs": ["<paths to referenced files>"]
    }}
  ]
}}
```

## Guidelines

- Write COMPLETE, RUNNABLE Python scripts for each scene
- Import packages directly (e.g., `import mitsuba as mi`)
- Parameterize scenes according to the experiment's parameter space
- Handle file references (STL meshes, configs) by loading them properly
- Include error handling in generated code
- Add comments explaining what each section does
- Each scene should be independent and self-contained
- Save outputs to files (images, data) and print output paths to stdout

## Available Environment

{environment}

Use ONLY packages that are listed above. If a critical package is missing,
note it in the code comments and raise a clear error.

## Current Experiment State

{state_context}
"""


def create_scene_agent(environment_str: str) -> AgentDefinition:
    """Create the Scene Agent definition.

    Args:
        environment_str: Formatted string describing available packages.
    """
    return AgentDefinition(
        description=(
            "Generates executable Python simulation code using available packages. "
            "Takes a structured hypothesis and experiment plan, writes Python "
            "scripts that create simulation scenes. Use after the hypothesis "
            "agent has produced a structured plan."
        ),
        prompt=SCENE_PROMPT.format(
            environment=environment_str,
            state_context="{state_context}",
        ),
        tools=["Read", "Bash"],
        model="sonnet",
    )
