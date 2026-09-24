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

import json
import os
import shutil

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


def _all_findings(report):
    return [finding for buckets in report.sections.values() for findings in buckets.values() for finding in findings]


def _write_agent(plugin_dir, name, body):
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {body}\n---\n\nBody text.\n"
    )


def test_sibling_component_check_does_not_flag_common_english_bare_phrases(tmp_path):
    """
    Regression test: ordinary prose like "the calling skill" or "invoke the
    next command" must not be treated as a sibling-component reference just
    because it matches the bare "the X agent/skill/command" shape.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    _write_agent(
        plugin_copy,
        "prose-only-agent",
        "Returns control to the calling skill once done, and tells it to invoke the next command.",
    )

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("prose-only-agent.md")]
    assert findings == [], findings


def test_sibling_component_check_still_flags_backtick_quoted_common_word(tmp_path):
    """
    The bare-phrase stoplist must not weaken the explicit backtick-quoted
    form -- `` `next` agent `` naming an actual (nonexistent) sibling should
    still be flagged even though "next" is in the bare-phrase stoplist.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    _write_agent(plugin_copy, "backtick-agent", "Hands off to the `next` agent for follow-up.")

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("backtick-agent.md")]
    assert any("next" in f.message for f in findings), findings


def test_sibling_component_check_resolves_a_sibling_plugin_in_the_same_repo(tmp_path):
    """
    Regression test: a reference to another plugin living next to this one
    in the same repo (e.g. `` `code-reviewer` skill `` from a plugin that
    hands off to it) should resolve, not be flagged as dangling.
    """
    repo_copy = tmp_path / "repo"
    plugin_copy = repo_copy / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    sibling_plugin = repo_copy / "other-plugin"
    (sibling_plugin / ".claude-plugin").mkdir(parents=True)
    (sibling_plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "other-plugin", "version": "0.0.1", "description": "x"})
    )
    _write_agent(plugin_copy, "handoff-agent", "Hands off review to the `other-plugin` skill.")

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("handoff-agent.md")]
    assert findings == [], findings


def test_sibling_component_check_suppresses_historical_qualified_reference(tmp_path):
    """
    Regression test: a component named with a historical qualifier right
    before it (e.g. "the former `artifact-scaffolder` skill") isn't a claim
    that the component currently exists, so it must not be flagged as a
    dangling reference.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    _write_agent(
        plugin_copy,
        "historical-mentioner",
        "Replaces the former `artifact-scaffolder` skill, which has been removed.",
    )

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("historical-mentioner.md")]
    assert findings == [], findings


def test_sibling_component_check_still_flags_unqualified_removed_reference(tmp_path):
    """
    The historical-qualifier suppression must not swallow an unqualified
    reference to a nonexistent sibling -- only a qualifier word immediately
    before the match should suppress it.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    _write_agent(plugin_copy, "unqualified-mentioner", "Hands off to the `artifact-scaffolder` skill.")

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("unqualified-mentioner.md")]
    assert any("artifact-scaffolder" in f.message for f in findings), findings


def test_sibling_component_check_resolves_builtin_agent_types(tmp_path):
    """
    Regression test: Claude Code's own built-in agent types (e.g. `Plan`)
    are legitimate to name in prose and must not be flagged as an
    unresolved sibling component.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    _write_agent(plugin_copy, "planning-mentioner", "Cheaper than the built-in `Plan` agent for narrow checks.")

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_sibling_components(str(plugin_copy), report)

    findings = [f for f in _all_findings(report) if (f.file or "").endswith("planning-mentioner.md")]
    assert findings == [], findings
