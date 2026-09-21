"""
Phase 4 (tasks.md): scripts/validate_plugin.py's Per-Skill Quality section.

Ports agents/skill-reviewer.md's checks -- trigger-phrase quality, word
count, progressive disclosure -- into validate_plugin.py's per-skill pass.

Covers:
- Each of the three checks fails in isolation against a purpose-built
  fixture skill (own tmp_path fixtures, not the shared broken-plugin fixture
  -- tests/fixtures/broken-plugin/skills/sample-skill/SKILL.md is a "good"
  skill and is not repurposed as a defect target here).
- A fixture skill that passes all three checks -> no findings.
- Zero-skills plugin -> an empty Per-Skill Quality section, not an error.
"""

import json
import subprocess

from scripts import validate_plugin

GOOD_DESCRIPTION = (
    "Use this skill when the user asks to deploy a service, roll back a release, "
    "or check deployment health status across environments."
)


def _fake_run_structural_check(plugin_path):
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(
            {
                "success": True,
                "manifest": {"file": "plugin.json", "errors": [], "warnings": [], "notes": []},
                "contents": [],
            }
        ),
        stderr="",
    )


def _write_plugin(tmp_path, skills=None):
    """
    Build a minimal, structurally-valid plugin directory under `tmp_path`.

    `skills` is a dict of skill_name -> dict(description=..., body_words=N,
    supporting_dirs=[...]). Omit or pass {} for a zero-skills plugin.
    """
    plugin_dir = tmp_path / "plugin"
    claude_plugin_dir = plugin_dir / ".claude-plugin"
    claude_plugin_dir.mkdir(parents=True)
    (claude_plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "quality-fixture-plugin",
                "version": "0.1.0",
                "description": "Fixture plugin for Per-Skill Quality tests.",
                "author": {"name": "Fixture Author"},
            }
        )
    )

    for skill_name, spec in (skills or {}).items():
        skill_dir = plugin_dir / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        body = " ".join(f"word{i}" for i in range(spec["body_words"]))
        content = f"---\nname: {skill_name}\ndescription: {spec['description']}\n---\n\n{body}\n"
        (skill_dir / "SKILL.md").write_text(content)
        for supporting_dir in spec.get("supporting_dirs", []):
            (skill_dir / supporting_dir).mkdir()

    return str(plugin_dir)


def _validate(monkeypatch, plugin_path):
    monkeypatch.setattr(validate_plugin, "_run_structural_check", _fake_run_structural_check)
    return validate_plugin.validate(plugin_path)


def test_per_skill_quality_flags_vague_trigger_phrase_in_isolation(tmp_path, monkeypatch):
    plugin_path = _write_plugin(
        tmp_path,
        skills={
            "vague-skill": {
                "description": "Does stuff.",
                "body_words": 1500,
            }
        },
    )

    report = _validate(monkeypatch, plugin_path)

    quality = report.sections["Per-Skill Quality"]
    all_messages = [f.message for f in quality["major"] + quality["minor"] + quality["critical"]]

    assert any("vague" in m.lower() for m in all_messages), all_messages
    # Word count (1500) and progressive disclosure (under threshold) must stay clean.
    assert not any("wildly over budget" in m or "too thin" in m for m in all_messages)
    assert not any("progressive disclosure" in m for m in all_messages)


def test_per_skill_quality_flags_word_count_in_isolation(tmp_path, monkeypatch):
    plugin_path = _write_plugin(
        tmp_path,
        skills={
            "thin-skill": {
                "description": GOOD_DESCRIPTION,
                "body_words": 50,
            }
        },
    )

    report = _validate(monkeypatch, plugin_path)

    quality = report.sections["Per-Skill Quality"]
    all_messages = [f.message for f in quality["major"] + quality["minor"] + quality["critical"]]

    assert any("too thin" in m for m in all_messages), all_messages
    assert not any("vague" in m.lower() for m in all_messages)
    assert not any("progressive disclosure" in m for m in all_messages)


def test_per_skill_quality_flags_missing_progressive_disclosure_in_isolation(tmp_path, monkeypatch):
    plugin_path = _write_plugin(
        tmp_path,
        skills={
            "bloated-skill": {
                "description": GOOD_DESCRIPTION,
                "body_words": 3500,
            }
        },
    )

    report = _validate(monkeypatch, plugin_path)

    quality = report.sections["Per-Skill Quality"]
    all_messages = [f.message for f in quality["major"] + quality["minor"] + quality["critical"]]

    assert any("progressive disclosure" in m for m in all_messages), all_messages
    assert not any("vague" in m.lower() for m in all_messages)
    assert not any("too thin" in m or "wildly over budget" in m for m in all_messages)


def test_per_skill_quality_bloated_skill_with_supporting_dir_is_not_flagged(tmp_path, monkeypatch):
    plugin_path = _write_plugin(
        tmp_path,
        skills={
            "well-organized-skill": {
                "description": GOOD_DESCRIPTION,
                "body_words": 3500,
                "supporting_dirs": ["references"],
            }
        },
    )

    report = _validate(monkeypatch, plugin_path)

    quality = report.sections["Per-Skill Quality"]
    all_messages = [f.message for f in quality["major"] + quality["minor"] + quality["critical"]]

    assert not any("progressive disclosure" in m for m in all_messages)


def test_per_skill_quality_good_skill_has_no_findings(tmp_path, monkeypatch):
    plugin_path = _write_plugin(
        tmp_path,
        skills={
            "good-skill": {
                "description": GOOD_DESCRIPTION,
                "body_words": 1200,
            }
        },
    )

    report = _validate(monkeypatch, plugin_path)

    quality = report.sections["Per-Skill Quality"]
    assert quality["critical"] == []
    assert quality["major"] == []
    assert quality["minor"] == []


def test_per_skill_quality_zero_skills_produces_empty_section_not_error(tmp_path, monkeypatch):
    plugin_path = _write_plugin(tmp_path, skills={})

    report = _validate(monkeypatch, plugin_path)

    assert report.fatal_error is None
    quality = report.sections["Per-Skill Quality"]
    assert quality == {"critical": [], "major": [], "minor": []}


def test_per_skill_quality_missing_description_is_critical(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugin"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "no-desc-plugin", "version": "0.1.0", "author": {"name": "Fixture"}})
    )
    skill_dir = plugin_dir / "skills" / "no-description-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# No Frontmatter\n\nJust a body, no frontmatter block at all.\n")

    report = _validate(monkeypatch, str(plugin_dir))

    quality = report.sections["Per-Skill Quality"]
    critical_messages = [f.message for f in quality["critical"]]
    assert any("Missing `description`" in m for m in critical_messages)
