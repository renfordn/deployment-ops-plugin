"""
Phase 10b (tasks.md): fixture defect agents.

Structural sanity check for the deliberately broken agent files added to
`tests/fixtures/broken-plugin/agents/` (bad-tool-agent.md, bad-sibling-agent.md,
bad-style-agent.md, and Phase 7's bad-dangling-ref-agent.md). These are
fixture inputs for Phase 10d's e2e assertions, not directly tested for their
*defect* here -- this only confirms the fixture files exist and are
otherwise well-formed (parseable YAML frontmatter with a non-empty
name/description), so Phase 10d doesn't discover a malformed fixture file at
the last minute.
"""

import os

import pytest
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIXTURE_AGENTS_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin", "agents")

EXPECTED_DEFECT_AGENT_FILES = [
    "bad-tool-agent.md",
    "bad-sibling-agent.md",
    "bad-style-agent.md",
    "bad-dangling-ref-agent.md",
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


def test_fixture_agents_dir_has_exactly_the_expected_defect_agents():
    assert os.path.isdir(FIXTURE_AGENTS_DIR), f"expected fixture agents dir at {FIXTURE_AGENTS_DIR}"
    actual_files = sorted(
        f for f in os.listdir(FIXTURE_AGENTS_DIR) if f.endswith(".md")
    )
    assert actual_files == sorted(EXPECTED_DEFECT_AGENT_FILES), (
        f"expected exactly {sorted(EXPECTED_DEFECT_AGENT_FILES)}, got {actual_files}"
    )


@pytest.mark.parametrize("filename", EXPECTED_DEFECT_AGENT_FILES)
def test_defect_agent_file_exists(filename):
    path = os.path.join(FIXTURE_AGENTS_DIR, filename)
    assert os.path.isfile(path), f"expected fixture defect agent file at {path}"


@pytest.mark.parametrize("filename", EXPECTED_DEFECT_AGENT_FILES)
def test_defect_agent_has_valid_frontmatter_and_body(filename):
    path = os.path.join(FIXTURE_AGENTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    frontmatter, body = _split_frontmatter(text)

    assert isinstance(frontmatter, dict), "frontmatter must parse as a YAML mapping"
    assert "name" in frontmatter and frontmatter["name"], "frontmatter must have a non-empty `name`"
    assert "description" in frontmatter and frontmatter["description"], (
        "frontmatter must have a non-empty `description`"
    )
    assert body.strip(), "body must be non-empty"
