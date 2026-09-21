"""
Phase 6c (tasks.md / design.md): agent-creator.md's Validate mode -- the
best-practice-doc conformance loop, wired into scripts/validate_plugin.py.

Test Intent (from the Slice Spec): for a given plugin, lazily load only the
specific `references/anthropic-docs/*.md` snapshot file(s) it needs (never
eagerly), and check each agent's persona/examples/tool-selection/model-choice
structure against that guidance. If the snapshot directory/file is missing
entirely, the check must be SKIPPED with a clear notice (not a failure and
not silently ignored) -- no crash, no silent zero-findings.

Fixture: tests/fixtures/broken-plugin/
  - references/anthropic-docs/sub-agents.md is a stubbed best-practice
    snapshot covering: persona/role statement requirement, "Use this agent
    when..." trigger-phrase convention, least-privilege tool scoping, and an
    examples requirement.
  - agents/bad-style-agent.md deliberately has NO "Use this agent when..."
    trigger phrase and no persona/role opening statement -> exactly one
    best-practice-doc finding, attributed to this file.
  - agents/bad-tool-agent.md and agents/bad-sibling-agent.md both follow the
    trigger-phrase and persona conventions -> no best-practice-doc finding
    for either file.

This test only pins down the *entry point and behavior* of the
best-practice-doc check (`validate_plugin.check_best_practice_doc`), not
agent-creator.md's Validate mode prose itself (out of scope for an automated
test). It calls that function directly, since it doesn't yet exist --
expected to fail with an AttributeError until the implementer adds it.
"""

import os
import shutil

from scripts import validate_plugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BROKEN_PLUGIN_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def test_best_practice_doc_check_flags_only_the_style_deviation():
    """
    Running the best-practice-doc check against tests/fixtures/broken-plugin/
    (whose references/anthropic-docs/sub-agents.md snapshot is present)
    should produce exactly one finding across the whole report, attributed
    to bad-style-agent.md (missing both the "Use this agent when..."
    trigger phrase and a persona/role opening statement). bad-tool-agent.md
    and bad-sibling-agent.md, which both follow those conventions, must not
    produce any finding.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)

    validate_plugin.check_best_practice_doc(BROKEN_PLUGIN_FIXTURE, report)

    all_findings = [
        finding
        for buckets in report.sections.values()
        for findings in buckets.values()
        for finding in findings
    ]

    assert len(all_findings) == 1, (
        f"expected exactly one best-practice-doc finding, got {len(all_findings)}: {all_findings!r}"
    )

    finding = all_findings[0]
    assert finding.file is not None and finding.file.endswith("bad-style-agent.md"), (
        f"expected the finding attributed to bad-style-agent.md, got file={finding.file!r}"
    )

    # No finding anywhere should be attributed to either non-offending agent
    # file -- both already follow the trigger-phrase and persona conventions.
    for finding in all_findings:
        assert not (finding.file or "").endswith("bad-tool-agent.md")
        assert not (finding.file or "").endswith("bad-sibling-agent.md")


def test_best_practice_doc_check_is_skipped_with_clear_notice_when_snapshot_missing(tmp_path):
    """
    If references/anthropic-docs/ is missing entirely, the best-practice-doc
    check must not crash and must not silently produce zero findings. It
    must record a clear, distinguishable skip notice -- not indistinguishable
    from "no defects found" -- and must not touch any pre-existing findings
    in other sections of the same report.

    We copy the fixture into a temp dir and remove its
    references/anthropic-docs/ directory so this test doesn't mutate the
    shared fixture on disk.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    anthropic_docs_dir = plugin_copy / "references" / "anthropic-docs"
    assert anthropic_docs_dir.is_dir(), "fixture setup assumption broken: snapshot dir should exist pre-removal"
    shutil.rmtree(anthropic_docs_dir)

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    # A pre-existing finding in an unrelated section, to confirm the skip
    # path doesn't clobber or otherwise affect other sections' findings.
    report.add_finding("Structural", "major", "pre-existing unrelated finding", file="agents/bad-tool-agent.md")

    validate_plugin.check_best_practice_doc(str(plugin_copy), report)

    best_practice_findings = [
        finding
        for name, buckets in report.sections.items()
        if name != "Structural"
        for findings in buckets.values()
        for finding in findings
    ]

    # Must not be silently empty: some clear, skip-specific notice must be
    # recorded (not indistinguishable from "no best-practice-doc defects
    # found"). We look for it either as a Finding whose message clearly
    # marks it a skip, or via a dedicated skip-tracking attribute on the
    # report -- whichever the implementer provides, it must be observable
    # and must reference the missing snapshot.
    skip_notices = [
        finding for finding in best_practice_findings if "skip" in finding.message.lower()
    ]
    skip_attr_notices = {
        key: value
        for key, value in vars(report).items()
        if "skip" in key.lower()
    }

    assert skip_notices or skip_attr_notices, (
        "expected a clear, distinguishable skip notice (a Finding whose message "
        "mentions 'skip', or a dedicated skip-tracking report attribute) when "
        "references/anthropic-docs/ is missing -- got neither. "
        f"best_practice_findings={best_practice_findings!r} report={report!r}"
    )

    if skip_notices:
        notice = skip_notices[0]
        assert "anthropic-docs" in notice.message or "snapshot" in notice.message.lower(), (
            f"expected the skip notice to reference the missing snapshot, got: {notice.message!r}"
        )
        assert notice.message.lower().count("skip") >= 1

    # The pre-existing, unrelated Structural finding must survive untouched.
    structural_findings = [
        finding for findings in report.sections["Structural"].values() for finding in findings
    ]
    assert len(structural_findings) == 1
    assert structural_findings[0].message == "pre-existing unrelated finding"
