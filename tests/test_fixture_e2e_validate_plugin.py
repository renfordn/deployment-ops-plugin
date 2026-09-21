"""
Phase 10d (tasks.md / design.md): fixture-based end-to-end verification --
the acceptance-level check tying Phase 6a/6b/6c and 7 together.

This is the only Phase 10 sub-phase that actually executes code (10a-10c
are pure fixture construction): it runs `validate_plugin.validate()` -- the
full composed pipeline, not an isolated `check_*` call -- against the
complete `tests/fixtures/broken-plugin/` fixture and confirms the
tool-grant (6a), sibling-component (6b), and best-practice-doc (6c)
findings all appear together, correctly attributed, with no spurious
duplication or masking from Phase 7's dangling-reference/security checks
(which run in the same pipeline and populate their own separate sections).

Test Intent:
  - One end-to-end test asserting all three findings appear from a single
    `validate_plugin.validate()` run, each attributed to its own agent
    file, with no other fixture component producing a spurious finding in
    the same category (isolation).
  - One end-to-end test for the missing-snapshot degradation case: with
    `references/anthropic-docs/` removed, the best-practice-doc finding is
    replaced by a skip notice while the other two findings still appear.
"""

import os
import shutil

from scripts import validate_plugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BROKEN_PLUGIN_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")

_TARGET_SECTION = "Per-Agent Plugin-Context Findings"


def _per_agent_findings(report):
    buckets = report.sections.get(_TARGET_SECTION, {})
    return [finding for findings in buckets.values() for finding in findings]


def _by_basename(findings):
    return {os.path.basename(f.file): f for f in findings if f.file}


def test_fixture_e2e_validate_plugin_produces_exactly_the_three_target_findings():
    report = validate_plugin.validate(BROKEN_PLUGIN_FIXTURE)

    findings = _per_agent_findings(report)
    assert len(findings) == 3, (
        f"expected exactly 3 findings in {_TARGET_SECTION!r} from a single composed run, "
        f"got {findings!r}"
    )

    by_file = _by_basename(findings)
    assert set(by_file) == {"bad-tool-agent.md", "bad-sibling-agent.md", "bad-style-agent.md"}, (
        f"expected exactly these three agent files to be flagged, got {sorted(by_file)}"
    )

    # Correct attribution: each finding names the right defect, on the right file.
    assert "mcp__release-notes-service__fetch_changelog" in by_file["bad-tool-agent.md"].message
    assert "nonexistent-helper" in by_file["bad-sibling-agent.md"].message
    assert "trigger-phrase" in by_file["bad-style-agent.md"].message.lower()

    # Isolation: the fourth (Phase 7) defect agent, and every other fixture
    # component, must not produce a spurious finding in this section.
    assert "bad-dangling-ref-agent.md" not in by_file

    # Phase 7's own checks must not duplicate or mask these three findings
    # -- they populate their own separate sections instead.
    assert not any(
        "mcp__release-notes-service" in f.message or "nonexistent-helper" in f.message
        for f in report.sections.get("Dangling References", {}).get("minor", [])
        + report.sections.get("Security/Sanitization", {}).get("critical", [])
    )


def test_fixture_e2e_validate_plugin_degrades_best_practice_doc_when_snapshot_missing(tmp_path):
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    shutil.rmtree(plugin_copy / "references" / "anthropic-docs")

    report = validate_plugin.validate(str(plugin_copy))

    findings = _per_agent_findings(report)
    by_file = _by_basename(findings)

    # bad-style-agent.md's own best-practice-doc finding is gone...
    assert "bad-style-agent.md" not in by_file

    # ...replaced by a clear, distinguishable skip notice (not silence).
    skip_notices = [f.message for f in findings if "skip" in f.message.lower()]
    assert skip_notices, f"expected a skip notice when the snapshot is missing, got {findings!r}"
    assert any("anthropic-docs" in m or "snapshot" in m.lower() for m in skip_notices)

    # The other two findings (tool-grant, sibling-component) are unaffected
    # by the missing best-practice-doc snapshot and must still appear.
    assert "bad-tool-agent.md" in by_file
    assert "bad-sibling-agent.md" in by_file
    assert "mcp__release-notes-service__fetch_changelog" in by_file["bad-tool-agent.md"].message
    assert "nonexistent-helper" in by_file["bad-sibling-agent.md"].message
