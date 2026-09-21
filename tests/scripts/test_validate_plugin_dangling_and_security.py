"""
Phase 7 (tasks.md / design.md): validate_plugin.py's general
dangling-reference resolution and security/sanitization scan, adapted from
upstream plugin-validator.md's Security Checks section.

Test Intent (from the Slice Spec):
  - Fixture hook referencing a missing script -> finding.
  - Fixture README naming a nonexistent command -> finding.
  - Fixture MCP server config with an HTTP (not HTTPS) URL -> critical finding.
  - Fixture file with a hardcoded absolute path (not using
    ${CLAUDE_PLUGIN_ROOT}) -> finding.
  - Fixture with no LICENSE file -> finding; invalid semver in plugin.json
    -> finding; empty description -> finding.
  - Fixture with a placeholder string resembling a secret in an example
    file -> finding with file/line/match context, explicitly reviewable,
    not a hard block.
  - No duplication of Phase 6a/6b's agent-level tool-grant/sibling findings.

Fixture additions for this phase (tests/fixtures/broken-plugin/):
  - hooks/hooks.json: one command hook using ${CLAUDE_PLUGIN_ROOT} that
    points at a script that doesn't exist (missing-hook.sh), and one using a
    hardcoded absolute path (/Users/someone/...) instead of the placeholder.
  - README.md: mentions a `nonexistent-plugin-command` command that doesn't
    exist anywhere in the fixture.
  - .mcp.json: declares `insecure-metrics-service` over an insecure
    http:// URL, and it's never referenced by any agent's tools frontmatter.
  - skills/sample-skill/examples/sample-request.md: embeds a Stripe-shaped
    placeholder secret.
  - No LICENSE file anywhere in the fixture (already true before this phase).

This test only pins down the *entry point and behavior* of
`validate_plugin.check_dangling_references` and
`validate_plugin.check_security_sanitization`, which don't exist yet --
expected to fail with an AttributeError until the implementer adds them.
"""

import json
import os
import shutil

from scripts import validate_plugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BROKEN_PLUGIN_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def _findings_in(report, section):
    buckets = report.sections.get(section, {})
    return [finding for findings in buckets.values() for finding in findings]


def _all_findings(report):
    return [finding for name in report.sections for finding in _findings_in(report, name)]


def test_dangling_reference_check_flags_missing_hook_script():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_dangling_references(BROKEN_PLUGIN_FIXTURE, report)

    hook_findings = [f for f in _findings_in(report, "Dangling References") if "missing-hook.sh" in f.message]
    assert len(hook_findings) == 1, f"expected one missing-hook-script finding, got {hook_findings!r}"
    assert (hook_findings[0].file or "").endswith("hooks.json")


def test_dangling_reference_check_does_not_flag_the_hardcoded_absolute_hook_path():
    """
    The second hooks.json entry uses a hardcoded absolute path instead of
    ${CLAUDE_PLUGIN_ROOT} -- that's the security check's defect to flag (a
    hardcoded path is the problem, regardless of whether it happens to
    exist on this machine), not the dangling-reference check's.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_dangling_references(BROKEN_PLUGIN_FIXTURE, report)

    assert not any("rollback.sh" in f.message for f in _findings_in(report, "Dangling References"))


def test_dangling_reference_check_flags_readme_naming_a_nonexistent_command():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_dangling_references(BROKEN_PLUGIN_FIXTURE, report)

    doc_findings = [
        f for f in _findings_in(report, "Dangling References") if "nonexistent-plugin-command" in f.message
    ]
    assert len(doc_findings) == 1, f"expected one doc-named-component finding, got {doc_findings!r}"
    assert (doc_findings[0].file or "").endswith("README.md")


def test_dangling_reference_check_flags_mcp_server_configured_but_unreferenced():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_dangling_references(BROKEN_PLUGIN_FIXTURE, report)

    mcp_findings = [
        f for f in _findings_in(report, "Dangling References") if "insecure-metrics-service" in f.message
    ]
    assert len(mcp_findings) == 1, f"expected one unreferenced-mcp-server finding, got {mcp_findings!r}"


def test_security_scan_flags_insecure_http_mcp_url_as_critical():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_security_sanitization(BROKEN_PLUGIN_FIXTURE, report)

    critical = report.sections.get("Security/Sanitization", {}).get("critical", [])
    assert any("insecure-metrics-service" in f.message and "http://" in f.message for f in critical)


def test_security_scan_flags_hardcoded_absolute_path_as_critical():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_security_sanitization(BROKEN_PLUGIN_FIXTURE, report)

    critical = report.sections.get("Security/Sanitization", {}).get("critical", [])
    assert any("/Users/someone" in f.message for f in critical)


def test_security_scan_flags_secret_in_example_file_with_context_and_review_note():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_security_sanitization(BROKEN_PLUGIN_FIXTURE, report)

    critical = report.sections.get("Security/Sanitization", {}).get("critical", [])
    secret_findings = [f for f in critical if (f.file or "").endswith("sample-request.md")]
    assert len(secret_findings) == 1, f"expected one secret finding, got {secret_findings!r}"

    finding = secret_findings[0]
    assert "line" in finding.message.lower()
    assert "review" in finding.message.lower()
    assert "not an automatic block" in finding.message.lower()


def test_security_scan_flags_vendor_shaped_secrets(tmp_path):
    """
    Exercises the AWS-access-key/Stripe-key/private-key-block patterns via
    an ephemeral tmp_path file rather than a committed fixture -- a
    matching literal in a git-tracked file trips real hosting-provider push
    protection (GitHub blocked an earlier version of this fixture that used
    a Stripe-shaped literal), even for an obviously fake placeholder value.
    tmp_path is never written to git, so this is safe.
    """
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)

    # Built from parts so no single literal in this source file itself is a
    # vendor-shaped secret pattern.
    aws_key = "AKIA" + "Z" * 16
    stripe_key = "sk_" + "test_" + "Q" * 20
    (plugin_copy / "references" / "vendor-secret-example.md").write_text(
        f"aws example: {aws_key}\nstripe example: {stripe_key}\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
    )

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_security_sanitization(str(plugin_copy), report)

    critical = report.sections.get("Security/Sanitization", {}).get("critical", [])
    vendor_findings = [f for f in critical if (f.file or "").endswith("vendor-secret-example.md")]
    assert len(vendor_findings) == 3, f"expected 3 vendor-shaped secret findings, got {vendor_findings!r}"


def test_security_scan_flags_missing_license():
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_security_sanitization(BROKEN_PLUGIN_FIXTURE, report)

    assert any("LICENSE" in f.message for f in _findings_in(report, "Security/Sanitization"))


def test_security_scan_flags_invalid_semver(tmp_path):
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    manifest_path = plugin_copy / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = "not-a-semver"
    manifest_path.write_text(json.dumps(manifest))

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_security_sanitization(str(plugin_copy), report)

    findings = _findings_in(report, "Security/Sanitization")
    assert any("semver" in f.message.lower() for f in findings)


def test_security_scan_flags_empty_description(tmp_path):
    plugin_copy = tmp_path / "broken-plugin"
    shutil.copytree(BROKEN_PLUGIN_FIXTURE, plugin_copy)
    manifest_path = plugin_copy / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["description"] = ""
    manifest_path.write_text(json.dumps(manifest))

    report = validate_plugin.Report(plugin_path=str(plugin_copy))
    validate_plugin.check_security_sanitization(str(plugin_copy), report)

    findings = _findings_in(report, "Security/Sanitization")
    assert any("description" in f.message.lower() for f in findings)


def test_dangling_and_security_checks_do_not_duplicate_phase_6a_6b_agent_findings():
    """
    Phase 6a/6b already own agent-level tool-grant/sibling-component
    findings (bad-tool-agent.md's undeclared MCP tool, bad-sibling-agent.md's
    nonexistent sibling). Phase 7's checks must not re-report those same
    issues under Dangling References or Security/Sanitization.
    """
    report = validate_plugin.Report(plugin_path=BROKEN_PLUGIN_FIXTURE)
    validate_plugin.check_dangling_references(BROKEN_PLUGIN_FIXTURE, report)
    validate_plugin.check_security_sanitization(BROKEN_PLUGIN_FIXTURE, report)

    phase7_findings = _findings_in(report, "Dangling References") + _findings_in(report, "Security/Sanitization")
    assert not any("release-notes-service" in f.message for f in phase7_findings)
    assert not any("nonexistent-helper" in f.message for f in phase7_findings)
