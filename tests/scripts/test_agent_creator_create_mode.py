"""
Phase 5 (tasks.md): agent-creator.md's Create mode, implemented as
scripts/create_agent.py.

Test Intent (from the Slice Spec):
  1. Create mode generates a new agent file with valid frontmatter
     (parseable YAML, non-empty name/description) for a fresh name that
     doesn't already exist.
  2. Name-collision: attempting to create an agent with a name that
     collides with an existing file refuses and reports the conflict,
     without modifying the existing file's contents.

Both cases are run against a temp directory (pytest's tmp_path), never
against this repo's own real agents/ directory, to avoid polluting it with
test-generated agent files.
"""

import os

import yaml

from scripts.create_agent import create_agent


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_create_mode_generates_agent_file_with_valid_frontmatter(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    result = create_agent(
        str(agents_dir), "widget-inspector", "Use this agent to inspect widgets."
    )

    assert result.ok is True
    target = agents_dir / "widget-inspector.md"
    assert result.path == str(target)
    assert target.exists()

    content = _read(target)
    assert content.startswith("---\n")

    parts = content.split("---\n")
    # parts[0] == "", parts[1] == frontmatter yaml, parts[2:] == body
    frontmatter = yaml.safe_load(parts[1])

    assert frontmatter["name"] == "widget-inspector"
    assert isinstance(frontmatter["description"], str)
    assert frontmatter["description"].strip() != ""
    assert isinstance(frontmatter["model"], str) and frontmatter["model"].strip()
    assert isinstance(frontmatter["color"], str) and frontmatter["color"].strip()
    assert isinstance(frontmatter["tools"], list) and len(frontmatter["tools"]) > 0


def test_create_mode_refuses_name_collision_without_modifying_existing_file(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    existing_path = agents_dir / "deployment-agent.md"
    original_contents = "# Deployment Agent\n\nOriginal untouched content.\n"
    existing_path.write_text(original_contents, encoding="utf-8")

    result = create_agent(
        str(agents_dir), "deployment-agent", "A conflicting new description."
    )

    assert result.ok is False
    assert result.path == str(existing_path)
    assert "deployment-agent.md" in result.error

    # Existing file must be untouched.
    assert _read(existing_path) == original_contents
