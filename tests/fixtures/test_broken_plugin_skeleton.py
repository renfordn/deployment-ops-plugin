"""
Phase 10a (tasks.md): fixture plugin skeleton sanity check.

Confirms `tests/fixtures/broken-plugin/` is itself a valid,
`claude plugin validate`-passing plugin (minimal manifest + one skill, zero
agents) *before* Phase 10b adds any deliberately broken agent files. Zero
agents is expected/fine at this point per Phase 3's zero-components-but-
valid-manifest edge case (pass, not fail).
"""

import json
import os
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIXTURE_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def _claude_available():
    return shutil.which("claude") is not None


@pytest.mark.skipif(not _claude_available(), reason="claude CLI not available in this environment")
def test_broken_plugin_fixture_validates_cleanly():
    assert os.path.isdir(FIXTURE_DIR), f"expected fixture directory at {FIXTURE_DIR}"
    assert os.path.isfile(os.path.join(FIXTURE_DIR, ".claude-plugin", "plugin.json")), (
        "fixture must have a .claude-plugin/plugin.json manifest"
    )
    assert os.path.isfile(
        os.path.join(FIXTURE_DIR, "skills", "sample-skill", "SKILL.md")
    ), "fixture must have skills/sample-skill/SKILL.md"

    result = subprocess.run(
        ["claude", "plugin", "validate", FIXTURE_DIR, "--strict", "--json"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"expected `claude plugin validate --strict` to pass for the fixture skeleton "
        f"(zero agents is fine); stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    report = json.loads(result.stdout)
    assert report["success"] is True
    assert report["manifest"]["errors"] == []


def test_broken_plugin_manifest_has_minimal_valid_shape():
    manifest_path = os.path.join(FIXTURE_DIR, ".claude-plugin", "plugin.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("name"), "manifest must have a non-empty `name`"
    assert manifest.get("skills"), "manifest must declare at least one skill"
    assert "agents" not in manifest or manifest["agents"] == [], (
        "Phase 10a fixture must have zero agents; defect agents land in Phase 10b"
    )
