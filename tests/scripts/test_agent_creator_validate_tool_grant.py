"""
Phase 6a (tasks.md / design.md): agent-creator.md's Validate mode -- the
tool-grant cross-check loop, wired into scripts/validate_plugin.py.

Test Intent (from the Slice Spec): for a given plugin path, build the
plugin's "known tool universe" (Claude Code built-in tools + any
MCP-server-exposed tools declared in `.mcp.json`/manifest `mcpServers` + any
hooks-declared capabilities), then for every agent file in the plugin, parse
its declared `tools:` frontmatter and flag any tool name not resolvable
against that known universe as a "Per-Agent Plugin-Context Findings" /
"Tool-Grant" finding, attributed to the offending agent file.

Fixture: tests/fixtures/broken-plugin/agents/
  - bad-tool-agent.md declares `mcp__release-notes-service__fetch_changelog`,
    an MCP tool with no corresponding `mcpServers` entry anywhere in the
    fixture plugin -> exactly one tool-grant finding, attributed to this
    file, naming the undeclared tool.
  - bad-sibling-agent.md and bad-style-agent.md only declare `Read`/`Bash`
    (both resolvable built-ins) -> no tool-grant finding for either file.

This test only pins down the *entry point and behavior* of the tool-grant
check (`validate_plugin.check_tool_grants`), not agent-creator.md's Validate
mode prose itself (out of scope for an automated test). It calls that
function directly, since it doesn't yet exist -- expected to fail with an
AttributeError until the implementer adds it.
"""

import os

from scripts import validate_plugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BROKEN_PLUGIN_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def test_tool_grant_check_flags_only_the_undeclared_mcp_tool():
    """
    Running the tool-grant check against tests/fixtures/broken-plugin/
    should produce exactly one finding across the whole report, attributed
    to bad-tool-agent.md, naming the undeclared tool
    `mcp__release-notes-service__fetch_changelog`. bad-sibling-agent.md and
    bad-style-agent.md (Read/Bash only) must not produce any finding.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)

    validate_plugin.check_tool_grants(BROKEN_PLUGIN_FIXTURE, report)

    all_findings = [
        finding
        for buckets in report.sections.values()
        for findings in buckets.values()
        for finding in findings
    ]

    assert len(all_findings) == 1, (
        f"expected exactly one tool-grant finding, got {len(all_findings)}: {all_findings!r}"
    )

    finding = all_findings[0]
    assert finding.file is not None and finding.file.endswith("bad-tool-agent.md"), (
        f"expected the finding attributed to bad-tool-agent.md, got file={finding.file!r}"
    )
    assert "mcp__release-notes-service__fetch_changelog" in finding.message, (
        f"expected the undeclared tool name in the finding message, got: {finding.message!r}"
    )

    # No finding anywhere should be attributed to either sibling agent file --
    # both only declare resolvable built-in tools (Read, Bash).
    for finding in all_findings:
        assert not (finding.file or "").endswith("bad-sibling-agent.md")
        assert not (finding.file or "").endswith("bad-style-agent.md")


def test_tool_grant_check_uses_minor_severity_for_ambiguous_tool_names():
    """
    An ambiguous/unresolvable tool name is a warning, not a hard block --
    the Slice Spec calls for using judgment on where "warning" falls in the
    critical/major/minor scheme. This test pins that judgment call down to
    "minor" (not critical/major), since the existing scheme reserves
    critical for manifest-breaking defects and major for a single
    component being structurally broken -- an unresolvable tool reference
    is neither; it's advisory until confirmed. If the implementer disagrees
    with "minor", they must update this assertion and state why in their
    handoff, not silently change severity without the test reflecting it.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)

    validate_plugin.check_tool_grants(BROKEN_PLUGIN_FIXTURE, report)

    all_findings_by_severity = {
        severity: findings
        for buckets in report.sections.values()
        for severity, findings in buckets.items()
        if findings
    }

    assert set(all_findings_by_severity.keys()) == {"minor"}, (
        f"expected the sole tool-grant finding at 'minor' severity only, "
        f"got severities: {list(all_findings_by_severity.keys())!r}"
    )
