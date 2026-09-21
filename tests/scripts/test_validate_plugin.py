"""
Phase 3 (tasks.md): scripts/validate_plugin.py's Structural validation pass.

Covers:
- "Not a plugin directory" edge case: no `.claude-plugin/plugin.json` ->
  a clear fatal error, no subprocess invoked, no exception.
- Mocked `claude plugin validate --json` known-good output -> report's
  Structural section reflects the manifest/component errors/warnings.
- Mocked malformed/non-JSON subprocess output -> report records a parse
  failure for the Structural section, no unhandled exception.
- Zero-components-but-valid-manifest fixture (tests/fixtures/broken-plugin,
  from Phase 10a) -> pass, not failure (exercises the real CLI directly,
  per this slice's Test Intent).
- Static check: validate_plugin.py's source never imports/calls
  refresh_docs (design.md's Risks section: structural, not conventional,
  enforcement).
"""

import ast
import subprocess

from scripts import validate_plugin

REPO_ROOT = validate_plugin.os.path.abspath(
    validate_plugin.os.path.join(validate_plugin.os.path.dirname(__file__), "..", "..")
)
BROKEN_PLUGIN_FIXTURE = validate_plugin.os.path.join(REPO_ROOT, "tests", "fixtures", "broken-plugin")


def test_validate_reports_fatal_error_when_not_a_plugin_directory(tmp_path, monkeypatch):
    called = False

    def fake_run(plugin_path):
        nonlocal called
        called = True
        raise AssertionError("subprocess should not be invoked when manifest is missing")

    monkeypatch.setattr(validate_plugin, "_run_structural_check", fake_run)

    report = validate_plugin.validate(str(tmp_path))

    assert called is False
    assert report.fatal_error is not None
    assert "not a plugin directory" in report.fatal_error.lower()
    assert report.sections == {}


def test_validate_parses_known_good_structural_json(monkeypatch):
    fake_stdout = """
    {
      "success": false,
      "manifest": {
        "file": "/fake/.claude-plugin/plugin.json",
        "errors": [{"path": "author", "message": "Invalid input", "code": null}],
        "warnings": [{"path": "schemaVersion", "message": "Unknown field", "code": null}],
        "notes": []
      },
      "contents": [
        {
          "file": "/fake/agents/broken.md",
          "type": "agent",
          "errors": [{"path": "frontmatter", "message": "Bad frontmatter", "code": null}],
          "warnings": [],
          "notes": []
        }
      ]
    }
    """

    def fake_run(plugin_path):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(validate_plugin, "_run_structural_check", fake_run)
    monkeypatch.setattr(
        validate_plugin.os.path, "isfile", lambda path: path.endswith("plugin.json")
    )

    report = validate_plugin.validate("/fake")

    assert report.fatal_error is None
    assert report.success is False

    structural = report.sections["Structural"]
    critical_messages = [f.message for f in structural["critical"]]
    major_messages = [f.message for f in structural["major"]]
    minor_messages = [f.message for f in structural["minor"]]

    assert "Invalid input" in critical_messages
    assert "Bad frontmatter" in major_messages
    assert "Unknown field" in minor_messages


def test_validate_degrades_gracefully_on_malformed_json(monkeypatch):
    def fake_run(plugin_path):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not json at all", stderr="")

    monkeypatch.setattr(validate_plugin, "_run_structural_check", fake_run)
    monkeypatch.setattr(
        validate_plugin.os.path, "isfile", lambda path: path.endswith("plugin.json")
    )

    report = validate_plugin.validate("/fake")

    assert report.fatal_error is None
    assert "Structural" in report.parse_errors
    structural = report.sections["Structural"]
    assert structural["critical"], "expected a critical finding recording the parse failure"


def test_validate_zero_components_valid_manifest_passes_not_fails():
    report = validate_plugin.validate(BROKEN_PLUGIN_FIXTURE)

    assert report.fatal_error is None
    assert report.parse_errors == {}
    assert report.success is not False
    structural = report.sections.get("Structural", {})
    assert not structural.get("critical")
    assert not structural.get("major")


def test_validate_plugin_source_never_imports_or_calls_refresh_docs():
    """
    Structural (not just conventional) enforcement of design.md's Risks
    section: validate_plugin.py must never import or call into
    refresh_docs. Walks the parsed AST (ignoring comments/docstrings, which
    may legitimately mention the module name in prose) rather than doing a
    naive substring search over the raw source.
    """
    with open(validate_plugin.__file__, "r", encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)

    offending_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "refresh_docs" in alias.name:
                    offending_names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and "refresh_docs" in node.module:
                offending_names.add(node.module)
            for alias in node.names:
                if "refresh_docs" in alias.name:
                    offending_names.add(alias.name)
        elif isinstance(node, ast.Name) and "refresh_docs" in node.id:
            offending_names.add(node.id)
        elif isinstance(node, ast.Attribute) and "refresh_docs" in node.attr:
            offending_names.add(node.attr)

    assert not offending_names, f"validate_plugin.py references refresh_docs via: {offending_names}"
