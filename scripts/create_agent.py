#!/usr/bin/env python3
"""
Phase 5 (tasks.md): agent-creator.md's Create mode, implemented as executable
Python (agent-creator.md itself is a Claude Code agent definition, not
executable Python -- see its TODO). This module is the entry point Phase 9a
wires a slash command to.

`create_agent(agents_dir, name, description)` scaffolds a new
`agents/<name>.md` file with valid YAML frontmatter (name, description,
model, color, tools) and a body structure, following agent-creator.md's
upstream scaffolding guidance (persona, responsibilities, examples).

Name-collision edge case: if `agents/<name>.md` already exists, this refuses
to overwrite it and reports the conflicting path via `CreateResult.ok=False`.
"""

import os
from dataclasses import dataclass
from typing import Optional

import yaml

DEFAULT_MODEL = "inherit"
DEFAULT_COLOR = "blue"
DEFAULT_TOOLS = ["Read", "Write"]


@dataclass
class CreateResult:
    ok: bool
    path: Optional[str] = None
    error: Optional[str] = None


def _render_agent_markdown(name: str, description: str) -> str:
    frontmatter = {
        "name": name,
        "description": description,
        "model": DEFAULT_MODEL,
        "color": DEFAULT_COLOR,
        "tools": DEFAULT_TOOLS,
    }
    frontmatter_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False
    ).strip()

    title = name.replace("-", " ").title()

    body = f"""---
{frontmatter_yaml}
---

You are an expert {title.lower()}, a specialized agent focused on: {description}

## Responsibilities

1. **Understand the Request**: Analyze the task and identify the relevant scope.
2. **Plan the Approach**: Determine the steps needed to accomplish the goal.
3. **Execute**: Carry out the work using the tools available to you.
4. **Verify**: Confirm the outcome matches the intent before reporting back.

## Examples

<example>
Context: A user needs this agent's capability.
user: "Help me with a task related to {name}."
assistant: "I'll use the {name} agent to handle this."
<commentary>
The user's request matches this agent's declared purpose, so it should trigger.
</commentary>
</example>

## Output Format

Provide a concise summary of what was done, any files changed, and
recommended next steps.
"""
    return body


def create_agent(agents_dir: str, name: str, description: str) -> CreateResult:
    """
    Generate a new agents/<name>.md file with valid YAML frontmatter and a
    scaffolded body. Refuses to overwrite an existing file at that path.
    """
    if not name or not name.strip():
        return CreateResult(ok=False, error="Agent name must not be empty.")
    if not description or not description.strip():
        return CreateResult(ok=False, error="Agent description must not be empty.")

    target_path = os.path.join(agents_dir, f"{name}.md")

    if os.path.exists(target_path):
        return CreateResult(
            ok=False,
            path=target_path,
            error=f"Refusing to overwrite existing agent file: {target_path}",
        )

    os.makedirs(agents_dir, exist_ok=True)

    content = _render_agent_markdown(name, description)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)

    return CreateResult(ok=True, path=target_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: create_agent.py <agents_dir> <name> <description>", file=sys.stderr)
        sys.exit(2)

    result = create_agent(sys.argv[1], sys.argv[2], sys.argv[3])
    if not result.ok:
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Created: {result.path}")
