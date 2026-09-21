"""
Phase 6b (tasks.md / design.md): agent-creator.md's Validate mode -- the
sibling-component cross-check loop, wired into scripts/validate_plugin.py.

Test Intent (from the Slice Spec): enumerate a plugin's actual components
(agents, skills, commands) by name, then for every agent file found, parse
named references to other agents/skills/commands in its description/examples/
body, and flag any reference that doesn't resolve to an actual component in
the same plugin as a sibling-component finding, attributed to the offending
agent file.

Fixture: tests/fixtures/broken-plugin/
  - agents/bad-sibling-agent.md deliberately references a `nonexistent-helper`
    agent that doesn't exist anywhere in the fixture (no such agent, skill, or
    command) -> exactly one sibling-component finding, attributed to this
    file, naming `nonexistent-helper`.
  - agents/bad-tool-agent.md and agents/bad-style-agent.md do not reference
    any nonexistent sibling -> no sibling-component finding for either file.

This test only pins down the *entry point and behavior* of the
sibling-component check (`validate_plugin.check_sibling_components`), not
agent-creator.md's Validate mode prose itself (out of scope for an automated
test). It calls that function directly, since it doesn't yet exist --
expected to fail with an AttributeError until the implementer adds it.
"""

import os

from scripts import validate_plugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BROKEN_PLUGIN_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def test_sibling_component_check_flags_only_the_nonexistent_reference():
    """
    Running the sibling-component check against tests/fixtures/broken-plugin/
    should produce exactly one finding across the whole report, attributed
    to bad-sibling-agent.md, naming the nonexistent sibling
    `nonexistent-helper`. bad-tool-agent.md and bad-style-agent.md must not
    produce any finding.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)

    validate_plugin.check_sibling_components(BROKEN_PLUGIN_FIXTURE, report)

    all_findings = [
        finding
        for buckets in report.sections.values()
        for findings in buckets.values()
        for finding in findings
    ]

    assert len(all_findings) == 1, (
        f"expected exactly one sibling-component finding, got {len(all_findings)}: {all_findings!r}"
    )

    finding = all_findings[0]
    assert finding.file is not None and finding.file.endswith("bad-sibling-agent.md"), (
        f"expected the finding attributed to bad-sibling-agent.md, got file={finding.file!r}"
    )
    assert "nonexistent-helper" in finding.message, (
        f"expected the nonexistent sibling name in the finding message, got: {finding.message!r}"
    )

    # No finding anywhere should be attributed to either non-offending agent
    # file -- neither references a nonexistent sibling.
    for finding in all_findings:
        assert not (finding.file or "").endswith("bad-tool-agent.md")
        assert not (finding.file or "").endswith("bad-style-agent.md")
