"""
Phase 8 (tasks.md / design.md): bump_version.py's --self-check code path.

Test Intent (from the Slice Spec): `bump_version.py --self-check` refuses
the bump when the self-check gate blocks, and proceeds when it doesn't --
run before bump_version.py moves CHANGELOG.md's Unreleased section or
updates plugin.json.

bump_version.py lives at skills/release-planner/bump_version.py -- a
hyphenated directory name, so it can't be imported via a normal dotted
package path. Loaded here via importlib from its file path instead.
"""

import importlib.util
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUMP_VERSION_PATH = os.path.join(REPO_ROOT, "skills", "release-planner", "bump_version.py")


def _load_bump_version_module():
    spec = importlib.util.spec_from_file_location("bump_version_under_test", BUMP_VERSION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_self_check_flag_blocks_bump_when_gate_blocks(monkeypatch):
    bump_version = _load_bump_version_module()

    bump_calls = []
    monkeypatch.setattr(bump_version, "bump", lambda version: bump_calls.append(version) or (True, ["should not run"]))
    monkeypatch.setattr(
        bump_version,
        "run_self_check_gate",
        lambda repo_root: (True, ["✗ release-planner: BLOCKED (missing) -- ...", "✗ Self-check gate blocked: release-planner (missing)"]),
    )

    exit_code = bump_version.main(["9.9.9", "--self-check"])

    assert exit_code == 1
    assert bump_calls == [], "bump() must not run when the self-check gate blocks"


def test_self_check_flag_proceeds_to_bump_when_gate_passes(monkeypatch):
    bump_version = _load_bump_version_module()

    bump_calls = []
    monkeypatch.setattr(
        bump_version, "bump", lambda version: bump_calls.append(version) or (True, ["✓ Release version prepared"])
    )
    monkeypatch.setattr(
        bump_version,
        "run_self_check_gate",
        lambda repo_root: (False, ["✓ Self-check gate passed: all skills fresh and at 100% pass rate"]),
    )

    exit_code = bump_version.main(["9.9.9", "--self-check"])

    assert exit_code == 0
    assert bump_calls == ["9.9.9"], "bump() must run once the self-check gate passes"


def test_without_self_check_flag_bump_runs_directly_without_consulting_the_gate(monkeypatch):
    bump_version = _load_bump_version_module()

    gate_calls = []
    monkeypatch.setattr(bump_version, "run_self_check_gate", lambda repo_root: gate_calls.append(repo_root) or (True, []))
    monkeypatch.setattr(bump_version, "bump", lambda version: (True, ["✓ ok"]))

    exit_code = bump_version.main(["9.9.9"])

    assert exit_code == 0
    assert gate_calls == [], "the self-check gate must only run when --self-check is passed"
