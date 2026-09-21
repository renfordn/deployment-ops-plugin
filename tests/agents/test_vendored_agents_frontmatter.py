"""
Phase 1a (tasks.md): vendored plugin-dev agent source files.

Confirms `agents/plugin-validator.md`, `agents/skill-reviewer.md`, and
`agents/agent-creator.md` exist on disk and each parses as a valid
YAML-frontmatter + Markdown agent file -- mirroring the frontmatter schema
`claude plugin validate` expects: a `---`-delimited frontmatter block with at
least `name` and `description` fields, followed by a non-empty Markdown body.
"""

import os

import pytest
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")

VENDORED_AGENT_FILES = [
    "plugin-validator.md",
    "skill-reviewer.md",
    "agent-creator.md",
]


def _split_frontmatter(text):
    """Split a `---`-delimited frontmatter block from the Markdown body.

    Returns (frontmatter_dict, body_str). Raises AssertionError if the file
    does not start with a `---` frontmatter block.
    """
    assert text.startswith("---\n"), "file must start with a `---` frontmatter delimiter"
    remainder = text[len("---\n"):]
    end_index = remainder.find("\n---")
    assert end_index != -1, "file must have a closing `---` frontmatter delimiter"
    frontmatter_raw = remainder[:end_index]
    body = remainder[end_index + len("\n---"):].lstrip("\n")
    frontmatter = yaml.safe_load(frontmatter_raw)
    return frontmatter, body


@pytest.mark.parametrize("filename", VENDORED_AGENT_FILES)
def test_vendored_agent_file_exists(filename):
    path = os.path.join(AGENTS_DIR, filename)
    assert os.path.isfile(path), f"expected vendored agent file at {path}"


@pytest.mark.parametrize("filename", VENDORED_AGENT_FILES)
def test_vendored_agent_has_valid_frontmatter_and_body(filename):
    path = os.path.join(AGENTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    frontmatter, body = _split_frontmatter(text)

    assert isinstance(frontmatter, dict), "frontmatter must parse as a YAML mapping"
    assert "name" in frontmatter and frontmatter["name"], "frontmatter must have a non-empty `name`"
    assert "description" in frontmatter and frontmatter["description"], (
        "frontmatter must have a non-empty `description`"
    )
    assert body.strip(), "Markdown body must be non-empty"
