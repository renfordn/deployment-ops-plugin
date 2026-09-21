"""
Phase 9a (tasks.md): slash-command files.

Mirrors tests/agents/test_vendored_agents_frontmatter.py's pattern (Phase
1a): confirms each new `commands/*.md` file exists, parses as a valid
YAML-frontmatter + Markdown command file (a `---`-delimited frontmatter
block with a non-empty `description`, followed by a non-empty body -- per
the Claude Code command-file schema; commands have no `name` field, unlike
agents/skills -- the command name comes from the filename), and that its
body references the existing script/mode it wraps (Test Intent: "references
an existing script/mode").

`claude plugin validate ./commands --strict --json` is also run manually
(same no-manifest-required smoke-check pattern as Phase 1a's agents-only
validation) and confirmed clean before this test file was written; it
reports `"contents": []` for a bare directory outside a full plugin
manifest, same as Phase 1a's agents-only run, so the real assertion of
correctness lives in this pytest file, not the CLI smoke-check.
"""

import os

import pytest
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMMANDS_DIR = os.path.join(REPO_ROOT, "commands")

# filename -> a script (or agent) path, relative to REPO_ROOT, the command's
# body must mention -- confirming it wraps an existing implementation, not a
# dangling reference to something that doesn't exist.
COMMAND_FILES_AND_REFERENCED_PATHS = {
    "plugin-validate.md": os.path.join("scripts", "validate_plugin.py"),
    "plugin-scaffold-agent.md": os.path.join("scripts", "create_agent.py"),
    "plugin-refresh-docs.md": os.path.join("scripts", "refresh_docs.py"),
}


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


@pytest.mark.parametrize("filename", sorted(COMMAND_FILES_AND_REFERENCED_PATHS))
def test_command_file_exists(filename):
    path = os.path.join(COMMANDS_DIR, filename)
    assert os.path.isfile(path), f"expected command file at {path}"


@pytest.mark.parametrize("filename", sorted(COMMAND_FILES_AND_REFERENCED_PATHS))
def test_command_has_valid_frontmatter_and_body(filename):
    path = os.path.join(COMMANDS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    frontmatter, body = _split_frontmatter(text)

    assert isinstance(frontmatter, dict), "frontmatter must parse as a YAML mapping"
    assert "description" in frontmatter and frontmatter["description"], (
        "frontmatter must have a non-empty `description`"
    )
    if "allowed-tools" in frontmatter:
        assert isinstance(frontmatter["allowed-tools"], list), "`allowed-tools` must be a list when present"
    assert body.strip(), "Markdown body must be non-empty"


@pytest.mark.parametrize("filename,referenced_relative_path", sorted(COMMAND_FILES_AND_REFERENCED_PATHS.items()))
def test_command_references_an_existing_script(filename, referenced_relative_path):
    path = os.path.join(COMMANDS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    referenced_absolute_path = os.path.join(REPO_ROOT, referenced_relative_path)
    assert os.path.isfile(referenced_absolute_path), (
        f"{filename} is supposed to wrap {referenced_relative_path}, but that file doesn't exist"
    )
    assert referenced_relative_path.replace(os.sep, "/") in text.replace(os.sep, "/"), (
        f"{filename}'s body must reference {referenced_relative_path}"
    )


def test_commands_directory_has_exactly_the_three_new_command_files():
    actual_files = sorted(f for f in os.listdir(COMMANDS_DIR) if f.endswith(".md"))
    assert actual_files == sorted(COMMAND_FILES_AND_REFERENCED_PATHS), (
        f"expected exactly {sorted(COMMAND_FILES_AND_REFERENCED_PATHS)}, got {actual_files}"
    )
