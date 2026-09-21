"""
Phase 8 (tasks.md / design.md): validate_plugin.py's self-check gate --
git-hash staleness + centralized eval-results storage, preserved as one
mode of the broader validator, scoped to this plugin's own three skills
(release-planner, deployment-orchestrator, monitoring).

Test Intent (from the Slice Spec):
  - git-hash helper: stable for an unchanged skill dir, different after a
    tracked file changes.
  - gate check: missing eval-results -> "missing"; hash mismatch ->
    "stale"; malformed JSON -> "parse-error" (no unhandled exception);
    pass_rate < 100% -> "below-threshold"; fresh + 100% -> allowed.
  - multi-failure case reports every failing skill/reason together, not
    one-at-a-time.

Uses a throwaway git repo under tmp_path (not the real deployment-ops-plugin
repo) so these tests are independent of whatever eval-results this plugin's
own skills do or don't have recorded yet.
"""

import json
import subprocess
import time

from scripts import validate_plugin


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo_with_skills(tmp_path, skill_names=("release-planner",), content="hello"):
    repo = tmp_path / "plugin"
    repo.mkdir()
    for skill_name in skill_names:
        skill_dir = repo / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)

    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "initial", cwd=repo)
    return repo


def _write_eval_results(repo, skill_name, git_hash, pass_rate=1.0):
    eval_dir = repo / "skills" / "release-planner" / "eval-results"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / f"{skill_name}.json").write_text(
        json.dumps(
            {
                "skill_name": skill_name,
                "git_hash": git_hash,
                "summary": {"passed": 1 if pass_rate >= 1.0 else 0, "failed": 0 if pass_rate >= 1.0 else 1, "total": 1, "pass_rate": pass_rate},
            }
        )
    )


def test_git_hash_stable_for_unchanged_skill_dir(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    first = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    second = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    assert first is not None
    assert first == second


def test_git_hash_changes_after_tracked_file_edit(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    before = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")

    (repo / "skills" / "release-planner" / "SKILL.md").write_text("changed content")

    after = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    assert after is not None
    assert after != before


def test_git_hash_excludes_the_eval_results_directory_itself(tmp_path):
    """
    Recording release-planner's own hash writes a new file inside
    skills/release-planner/eval-results/ -- that must not change
    release-planner's own computed hash, or recording the hash would
    immediately invalidate itself.
    """
    repo = _init_repo_with_skills(tmp_path)
    before = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")

    _write_eval_results(repo, "release-planner", git_hash=before, pass_rate=1.0)

    after = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    assert after == before


def test_gate_blocks_with_missing_reason_when_eval_results_absent(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    result = validate_plugin.check_self_check_gate(str(repo), ("release-planner",))[0]
    assert result.blocked
    assert result.reason == "missing"


def test_gate_blocks_with_stale_reason_on_hash_mismatch(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    _write_eval_results(repo, "release-planner", git_hash="0" * 64, pass_rate=1.0)

    result = validate_plugin.check_self_check_gate(str(repo), ("release-planner",))[0]
    assert result.blocked
    assert result.reason == "stale"


def test_gate_blocks_with_parse_error_reason_on_malformed_json(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    eval_dir = repo / "skills" / "release-planner" / "eval-results"
    eval_dir.mkdir(parents=True)
    (eval_dir / "release-planner.json").write_text("{not valid json")

    result = validate_plugin.check_self_check_gate(str(repo), ("release-planner",))[0]
    assert result.blocked
    assert result.reason == "parse-error"


def test_gate_blocks_with_below_threshold_reason_when_pass_rate_under_100(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    current_hash = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    _write_eval_results(repo, "release-planner", git_hash=current_hash, pass_rate=0.5)

    result = validate_plugin.check_self_check_gate(str(repo), ("release-planner",))[0]
    assert result.blocked
    assert result.reason == "below-threshold"


def test_gate_allows_when_fresh_and_100_percent(tmp_path):
    repo = _init_repo_with_skills(tmp_path)
    current_hash = validate_plugin.compute_skill_git_hash(str(repo), "release-planner")
    _write_eval_results(repo, "release-planner", git_hash=current_hash, pass_rate=1.0)

    result = validate_plugin.check_self_check_gate(str(repo), ("release-planner",))[0]
    assert not result.blocked
    assert result.reason is None


def test_gate_reports_every_failing_skill_in_one_combined_result(tmp_path):
    skill_names = ("release-planner", "deployment-orchestrator", "monitoring")
    repo = _init_repo_with_skills(tmp_path, skill_names=skill_names)

    # release-planner: missing entirely.
    # deployment-orchestrator: stale (wrong hash).
    _write_eval_results(repo, "deployment-orchestrator", git_hash="f" * 64, pass_rate=1.0)
    # monitoring: fresh and 100%, should not be blocked.
    monitoring_hash = validate_plugin.compute_skill_git_hash(str(repo), "monitoring")
    _write_eval_results(repo, "monitoring", git_hash=monitoring_hash, pass_rate=1.0)

    results = validate_plugin.check_self_check_gate(str(repo), skill_names)
    by_skill = {r.skill: r for r in results}

    assert by_skill["release-planner"].blocked and by_skill["release-planner"].reason == "missing"
    assert by_skill["deployment-orchestrator"].blocked and by_skill["deployment-orchestrator"].reason == "stale"
    assert not by_skill["monitoring"].blocked

    blocked, messages = validate_plugin.run_self_check_gate(str(repo), skill_names)
    assert blocked
    combined = "\n".join(messages)
    assert "release-planner" in combined and "missing" in combined
    assert "deployment-orchestrator" in combined and "stale" in combined
    # Reported together in one combined result, not requiring several separate calls.
    summary_lines = [m for m in messages if m.startswith("✗ Self-check gate blocked")]
    assert len(summary_lines) == 1
    assert "release-planner" in summary_lines[0] and "deployment-orchestrator" in summary_lines[0]


def test_gate_overhead_stays_under_one_second_on_a_representative_fixture(tmp_path):
    """
    Non-Functional Constraint: three small JSON reads + three git-hash
    computations should add well under ~1 second to bump_version.py.
    """
    skill_names = ("release-planner", "deployment-orchestrator", "monitoring")
    repo = _init_repo_with_skills(tmp_path, skill_names=skill_names)
    for skill_name in skill_names:
        current_hash = validate_plugin.compute_skill_git_hash(str(repo), skill_name)
        _write_eval_results(repo, skill_name, git_hash=current_hash, pass_rate=1.0)

    started = time.monotonic()
    blocked, _messages = validate_plugin.run_self_check_gate(str(repo), skill_names)
    elapsed = time.monotonic() - started

    assert not blocked
    assert elapsed < 1.0, f"self-check gate took {elapsed:.3f}s, expected well under 1s"


def test_populate_self_check_gate_section_adds_one_critical_finding_per_blocked_skill(tmp_path):
    """Uses `populate_self_check_gate_section`'s default skill set (all three real skills)."""
    repo = _init_repo_with_skills(
        tmp_path, skill_names=("release-planner", "deployment-orchestrator", "monitoring")
    )
    for skill_name in ("deployment-orchestrator", "monitoring"):
        current_hash = validate_plugin.compute_skill_git_hash(str(repo), skill_name)
        _write_eval_results(repo, skill_name, git_hash=current_hash, pass_rate=1.0)
    # release-planner is left with no eval-results file at all -> "missing".

    report = validate_plugin.Report(plugin_path=str(repo))
    validate_plugin.populate_self_check_gate_section(str(repo), report)

    critical = report.sections["Self-Check Gate"]["critical"]
    assert len(critical) == 1
    assert "release-planner" in critical[0].message
