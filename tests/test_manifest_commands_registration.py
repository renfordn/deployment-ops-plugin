"""
Phase 9b (tasks.md): register the three Phase 9a slash commands in
`.claude-plugin/plugin.json`'s `commands` array.

Test Intent: `.claude-plugin/plugin.json`'s `commands` array lists all
three new commands (path-shaped entries, matching the `skills`/`agents`
array convention -- confirmed empirically against `claude plugin validate`:
a `{name, description}` object, the pre-existing `"deploy"` entry's shape,
is actually "Invalid input" against the real schema, and there was never a
corresponding `commands/deploy.md` file backing it. That stale, always-broken
entry is dropped here rather than kept, since keeping it would make
`commands` fail --strict validation regardless of how the 3 new entries are
formatted -- see the Slice Spec discussion in this phase's implementation).
"""

import json
import os
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")

EXPECTED_COMMAND_PATHS = {
    "./commands/plugin-validate.md",
    "./commands/plugin-scaffold-agent.md",
    "./commands/plugin-refresh-docs.md",
}


def _load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_commands_array_lists_the_three_new_commands():
    manifest = _load_manifest()
    commands = manifest.get("commands")

    assert isinstance(commands, list), "`commands` must be a list"
    assert set(commands) == EXPECTED_COMMAND_PATHS, (
        f"expected commands {EXPECTED_COMMAND_PATHS}, got {commands!r}"
    )


def test_every_registered_command_path_resolves_to_a_real_file():
    manifest = _load_manifest()
    for entry in manifest["commands"]:
        relative = entry[2:] if entry.startswith("./") else entry
        assert os.path.isfile(os.path.join(REPO_ROOT, relative)), (
            f"plugin.json lists command `{entry}`, which doesn't resolve to a real file"
        )


def _claude_available():
    return shutil.which("claude") is not None


@pytest.mark.skipif(not _claude_available(), reason="claude CLI not available in this environment")
def test_claude_plugin_validate_reports_no_commands_manifest_errors():
    result = subprocess.run(
        ["claude", "plugin", "validate", REPO_ROOT, "--strict", "--json"],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    manifest_errors = (data.get("manifest") or {}).get("errors") or []

    commands_errors = [e for e in manifest_errors if str(e.get("path", "")).startswith("commands")]
    assert commands_errors == [], f"expected no `commands`-path manifest errors, got {commands_errors!r}"
