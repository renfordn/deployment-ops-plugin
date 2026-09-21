#!/usr/bin/env python3
"""
Phase 3 (tasks.md): scripts/validate_plugin.py -- the release-readiness-gate
orchestrator's first pass.

`validate(plugin_path)` returns a `Report`: a severity-grouped (critical /
major / minor) structure, organized into named sections. This slice only
populates the "Structural" section (delegating to `claude plugin validate
--strict --json`). Later phases (4, 6a/6b/6c, 7, 8) extend the same `Report`
object with additional sections (Dangling References, Security/Sanitization,
Per-Skill Quality, Per-Agent Plugin-Context Findings, Self-Check Gate) --
see design.md's Data Contracts And Interfaces.

Severity mapping for the Structural section (our own judgment call, since
`claude plugin validate`'s error/warning split doesn't map 1:1 onto
critical/major/minor):
  - manifest-level errors   -> critical (the manifest is the plugin's core
    contract; a manifest error usually means the plugin cannot load at all)
  - component-level errors  -> major (a single agent/skill/command file is
    broken, but the manifest itself is still structurally sound)
  - any warnings or notes (manifest or component level) -> minor

IMPORTANT: this module must never import or call `scripts/refresh_docs.py`
(design.md's Risks section: the "never fetch live during a validator run"
contract must be enforced structurally, not just by convention). See
tests/scripts/test_validate_plugin.py's static-analysis test.
"""

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

SEVERITIES = ("critical", "major", "minor")

# Phase 4 (tasks.md): Per-Skill Quality thresholds, ported from
# agents/skill-reviewer.md's own standards.
_VAGUE_DESCRIPTION_MIN_WORDS = 6
_DESCRIPTION_MIN_CHARS = 50
_DESCRIPTION_MAX_CHARS = 500
_WORD_COUNT_TOO_SHORT = 300
_WORD_COUNT_TOO_LONG = 6000
_PROGRESSIVE_DISCLOSURE_THRESHOLD = 3000
_SUPPORTING_DIRS = ("references", "examples", "scripts")


@dataclass
class Finding:
    """A single reportable item within a report section."""

    message: str
    path: Optional[str] = None
    file: Optional[str] = None


def _empty_severity_buckets() -> Dict[str, List[Finding]]:
    return {severity: [] for severity in SEVERITIES}


@dataclass
class Report:
    """
    Severity-grouped, section-named validation report.

    `sections` maps a section name (e.g. "Structural") to a dict of
    critical/major/minor -> list[Finding]. New sections can be added by
    later phases without changing this shape.
    """

    plugin_path: str
    success: Optional[bool] = None
    fatal_error: Optional[str] = None
    sections: Dict[str, Dict[str, List[Finding]]] = field(default_factory=dict)
    parse_errors: Dict[str, str] = field(default_factory=dict)

    def add_finding(
        self,
        section: str,
        severity: str,
        message: str,
        path: Optional[str] = None,
        file: Optional[str] = None,
    ) -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"Unknown severity {severity!r}; expected one of {SEVERITIES}")
        bucket = self.sections.setdefault(section, _empty_severity_buckets())
        bucket[severity].append(Finding(message=message, path=path, file=file))

    def has_findings(self, section: Optional[str] = None) -> bool:
        sections = [self.sections[section]] if section else self.sections.values()
        return any(findings for bucket in sections for findings in bucket.values())

    def to_dict(self) -> dict:
        return {
            "plugin_path": self.plugin_path,
            "success": self.success,
            "fatal_error": self.fatal_error,
            "parse_errors": dict(self.parse_errors),
            "sections": {
                name: {severity: [asdict(f) for f in findings] for severity, findings in buckets.items()}
                for name, buckets in self.sections.items()
            },
        }


def _manifest_path(plugin_path: str) -> str:
    return os.path.join(plugin_path, ".claude-plugin", "plugin.json")


def _run_structural_check(plugin_path: str) -> subprocess.CompletedProcess:
    """Shell out to `claude plugin validate <path> --strict --json`."""
    return subprocess.run(
        ["claude", "plugin", "validate", plugin_path, "--strict", "--json"],
        capture_output=True,
        text=True,
    )


def _add_entries(report: Report, section: str, severity: str, entries, default_file: Optional[str]) -> None:
    for entry in entries or []:
        if isinstance(entry, dict):
            message = entry.get("message", "Unknown finding")
            path = entry.get("path")
            file = entry.get("file", default_file)
        else:
            message = str(entry)
            path = None
            file = default_file
        report.add_finding(section, severity, message, path=path, file=file)


def _populate_structural_section(report: Report, stdout: str) -> None:
    """
    Parse `claude plugin validate --json`'s stdout into the report's
    Structural section. Degrades gracefully (records a parse failure, never
    raises) if the output isn't valid JSON or isn't shaped as expected.
    """
    try:
        data = json.loads(stdout)
    except (TypeError, ValueError) as exc:
        message = f"Failed to parse `claude plugin validate --json` output: {exc}"
        report.parse_errors["Structural"] = message
        report.add_finding("Structural", "critical", message)
        return

    if not isinstance(data, dict):
        message = "`claude plugin validate --json` output was not a JSON object as expected."
        report.parse_errors["Structural"] = message
        report.add_finding("Structural", "critical", message)
        return

    report.success = data.get("success")

    manifest = data.get("manifest") or {}
    manifest_file = manifest.get("file")
    _add_entries(report, "Structural", "critical", manifest.get("errors"), manifest_file)
    _add_entries(report, "Structural", "minor", manifest.get("warnings"), manifest_file)
    _add_entries(report, "Structural", "minor", manifest.get("notes"), manifest_file)

    for item in data.get("contents") or []:
        item_file = item.get("file") if isinstance(item, dict) else None
        _add_entries(report, "Structural", "major", item.get("errors") if isinstance(item, dict) else None, item_file)
        _add_entries(report, "Structural", "minor", item.get("warnings") if isinstance(item, dict) else None, item_file)
        _add_entries(report, "Structural", "minor", item.get("notes") if isinstance(item, dict) else None, item_file)


def _enumerate_skill_md_files(plugin_path: str) -> List[str]:
    """Enumerate `skills/*/SKILL.md` under `plugin_path`, in sorted order."""
    skills_dir = os.path.join(plugin_path, "skills")
    if not os.path.isdir(skills_dir):
        return []
    paths = []
    for entry in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, entry, "SKILL.md")
        if os.path.isfile(skill_md):
            paths.append(skill_md)
    return paths


def _split_frontmatter(text: str) -> Tuple[Optional[dict], str]:
    """
    Split a `---`-delimited YAML frontmatter block from a Markdown file's
    body. Returns (frontmatter_dict_or_None, body). `frontmatter` is `None`
    when the file has no frontmatter block, or the block doesn't parse as a
    YAML mapping -- callers should treat that the same as "no frontmatter".
    """
    if not text.startswith("---\n"):
        return None, text
    remainder = text[len("---\n"):]
    end_index = remainder.find("\n---")
    if end_index == -1:
        return None, text
    frontmatter_raw = remainder[:end_index]
    body = remainder[end_index + len("\n---"):].lstrip("\n")
    try:
        frontmatter = yaml.safe_load(frontmatter_raw)
    except yaml.YAMLError:
        return None, body
    if not isinstance(frontmatter, dict):
        return None, body
    return frontmatter, body


def _split_skill_frontmatter(text: str) -> Tuple[Optional[dict], str]:
    """Backward-compatible alias for `_split_frontmatter` (SKILL.md usage)."""
    return _split_frontmatter(text)


def _check_trigger_phrase_quality(description: Optional[str]) -> List[Tuple[str, str]]:
    """
    Ported from agents/skill-reviewer.md's description-evaluation standard:
    concrete trigger phrases, appropriate length (50-500 chars).
    """
    if not description or not description.strip():
        return [(
            "critical",
            "Missing `description`; a skill cannot be discovered without concrete "
            "trigger phrases describing when to use it.",
        )]

    stripped = description.strip()
    findings: List[Tuple[str, str]] = []

    word_count = len(stripped.split())
    if word_count < _VAGUE_DESCRIPTION_MIN_WORDS:
        findings.append((
            "major",
            f"Description is too vague/generic ({word_count} word(s)); needs concrete "
            "trigger phrases (e.g. \"Use this skill when...\" with specific user scenarios), "
            "per skill-reviewer.md's description-quality standard.",
        ))

    if len(stripped) < _DESCRIPTION_MIN_CHARS:
        findings.append((
            "minor",
            f"Description is shorter than the recommended minimum of "
            f"{_DESCRIPTION_MIN_CHARS} characters ({len(stripped)} chars).",
        ))
    elif len(stripped) > _DESCRIPTION_MAX_CHARS:
        findings.append((
            "minor",
            f"Description is longer than the recommended maximum of "
            f"{_DESCRIPTION_MAX_CHARS} characters ({len(stripped)} chars).",
        ))

    return findings


def _check_word_count(body: str) -> List[Tuple[str, str]]:
    """
    Ported from agents/skill-reviewer.md's content-quality standard: SKILL.md
    body should be roughly 1,000-3,000 words. Only flags when wildly outside
    that range.
    """
    count = len(body.split())
    if count < _WORD_COUNT_TOO_SHORT:
        return [(
            "major",
            f"SKILL.md body is only {count} word(s); skill-reviewer.md's standard is "
            "roughly 1,000-3,000 words -- likely too thin to be useful.",
        )]
    if count > _WORD_COUNT_TOO_LONG:
        return [(
            "major",
            f"SKILL.md body is {count} words; skill-reviewer.md's standard is roughly "
            "1,000-3,000 words -- wildly over budget.",
        )]
    return []


def _check_progressive_disclosure(skill_dir: str, body: str) -> List[Tuple[str, str]]:
    """
    Ported from agents/skill-reviewer.md's progressive-disclosure standard:
    detailed content belongs in references/examples/scripts, not bloating
    SKILL.md itself.
    """
    count = len(body.split())
    if count <= _PROGRESSIVE_DISCLOSURE_THRESHOLD:
        return []
    has_supporting_dir = any(
        os.path.isdir(os.path.join(skill_dir, name)) for name in _SUPPORTING_DIRS
    )
    if has_supporting_dir:
        return []
    return [(
        "major",
        f"SKILL.md body is {count} words with no references/examples/scripts "
        "subdirectory to offload detail into -- apply progressive disclosure by moving "
        "detailed content out of SKILL.md.",
    )]


def _populate_per_skill_quality_section(report: Report, plugin_path: str) -> None:
    """
    Populate the report's "Per-Skill Quality" section: one pass per
    `skills/*/SKILL.md`, checking trigger-phrase quality, word count, and
    progressive disclosure. A plugin with zero skills still gets the section
    (empty severity buckets), not an error.
    """
    section = "Per-Skill Quality"
    report.sections.setdefault(section, _empty_severity_buckets())

    for skill_md_path in _enumerate_skill_md_files(plugin_path):
        skill_dir = os.path.dirname(skill_md_path)
        try:
            with open(skill_md_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            report.add_finding(section, "critical", f"Failed to read SKILL.md: {exc}", file=skill_md_path)
            continue

        frontmatter, body = _split_skill_frontmatter(text)
        description = frontmatter.get("description") if frontmatter else None

        checks = (
            _check_trigger_phrase_quality(description)
            + _check_word_count(body)
            + _check_progressive_disclosure(skill_dir, body)
        )
        for severity, message in checks:
            report.add_finding(section, severity, message, file=skill_md_path)


# Phase 6a (tasks.md): the tool-grant cross-check loop.
#
# Claude Code's own built-in tool names (per code.claude.com/docs/en/hooks &
# the agent-file `tools:` frontmatter convention). This is a static allowlist
# maintained here since there's no importable manifest of built-ins to
# introspect at plugin-validation time -- see design.md's Risks section for
# why this loop has no upstream reference implementation.
_BUILTIN_TOOLS = frozenset(
    {
        "Task",
        "Bash",
        "BashOutput",
        "KillShell",
        "Glob",
        "Grep",
        "Read",
        "Edit",
        "Write",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
        "SlashCommand",
        "ExitPlanMode",
    }
)

_MCP_TOOL_PREFIX = "mcp__"


def _enumerate_agent_md_files(plugin_path: str) -> List[str]:
    """Enumerate `agents/*.md` files under `plugin_path`, in sorted order."""
    agents_dir = os.path.join(plugin_path, "agents")
    if not os.path.isdir(agents_dir):
        return []
    paths = []
    for entry in sorted(os.listdir(agents_dir)):
        if entry.endswith(".md"):
            full_path = os.path.join(agents_dir, entry)
            if os.path.isfile(full_path):
                paths.append(full_path)
    return paths


def _load_manifest(plugin_path: str) -> dict:
    manifest_path = _manifest_path(plugin_path)
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _mcp_server_names(plugin_path: str) -> set:
    """
    Collect declared MCP server names from `.mcp.json` and/or the manifest's
    `mcpServers` field. Server names are the keys of the `mcpServers` mapping
    (e.g. `{"release-notes-service": {...}}` -> `"release-notes-service"`).
    """
    names = set()

    mcp_json_path = os.path.join(plugin_path, ".mcp.json")
    if os.path.isfile(mcp_json_path):
        try:
            with open(mcp_json_path, "r", encoding="utf-8") as fh:
                mcp_data = json.load(fh)
        except (OSError, ValueError):
            mcp_data = None
        if isinstance(mcp_data, dict):
            servers = mcp_data.get("mcpServers")
            if isinstance(servers, dict):
                names.update(servers.keys())

    manifest = _load_manifest(plugin_path)
    manifest_servers = manifest.get("mcpServers")
    if isinstance(manifest_servers, dict):
        names.update(manifest_servers.keys())

    return names


def _hooks_declared_capabilities(plugin_path: str) -> set:
    """
    Collect any tool-shaped names declared by `hooks/hooks.json`. Hooks don't
    themselves grant agent tool access, but a plugin could plausibly document
    hook-exposed capabilities there; this is a conservative placeholder that
    returns an empty set when there's nothing tool-shaped to add, so it never
    widens the known universe based on guesswork.
    """
    hooks_path = os.path.join(plugin_path, "hooks", "hooks.json")
    if not os.path.isfile(hooks_path):
        return set()
    try:
        with open(hooks_path, "r", encoding="utf-8") as fh:
            json.load(fh)
    except (OSError, ValueError):
        pass
    # No documented hooks.json schema field maps to agent tool names today;
    # nothing further to extract.
    return set()


def _resolve_tool_name(tool_name: str, mcp_server_names: set) -> bool:
    """Return True if `tool_name` resolves against the known tool universe."""
    if tool_name in _BUILTIN_TOOLS:
        return True
    if tool_name.startswith(_MCP_TOOL_PREFIX):
        remainder = tool_name[len(_MCP_TOOL_PREFIX):]
        server_name = remainder.split("__", 1)[0]
        return server_name in mcp_server_names
    return False


def _parse_agent_tools(frontmatter: Optional[dict]) -> List[str]:
    """
    Extract a list of declared tool names from an agent's `tools:`
    frontmatter, which may be a YAML list or a comma-separated string.
    """
    if not frontmatter:
        return []
    tools = frontmatter.get("tools")
    if tools is None:
        return []
    if isinstance(tools, str):
        return [t.strip() for t in tools.split(",") if t.strip()]
    if isinstance(tools, list):
        return [str(t).strip() for t in tools if str(t).strip()]
    return []


def check_tool_grants(plugin_path: str, report: Report) -> None:
    """
    Populate the report's "Per-Agent Plugin-Context Findings" section: for
    every agent under `agents/`, cross-check its declared `tools:`
    frontmatter against the plugin's known tool universe (Claude Code
    built-ins + declared MCP servers + hooks-declared capabilities). Any
    unresolvable tool name is flagged at `minor` severity (advisory, not a
    hard block -- see the Slice Spec's Test Intent) and attributed to the
    offending agent file. A plugin with zero agents still gets the section
    (empty severity buckets), not an error.
    """
    section = "Per-Agent Plugin-Context Findings"
    report.sections.setdefault(section, _empty_severity_buckets())

    mcp_server_names = _mcp_server_names(plugin_path)
    # Hooks-declared capabilities are folded into the same resolution check
    # as MCP servers today (both are named-capability sources); currently a
    # no-op set, kept as its own call site so a future hooks schema addition
    # doesn't require touching `_resolve_tool_name`'s call sites.
    _hooks_declared_capabilities(plugin_path)

    for agent_path in _enumerate_agent_md_files(plugin_path):
        try:
            with open(agent_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            report.add_finding(section, "critical", f"Failed to read agent file: {exc}", file=agent_path)
            continue

        frontmatter, _body = _split_frontmatter(text)
        for tool_name in _parse_agent_tools(frontmatter):
            if not _resolve_tool_name(tool_name, mcp_server_names):
                report.add_finding(
                    section,
                    "minor",
                    f"Agent declares tool `{tool_name}`, which does not resolve against this "
                    "plugin's known tool universe (Claude Code built-ins + declared MCP "
                    "servers + hooks-declared capabilities). Confirm it's a valid grant, not "
                    "a typo or a missing MCP server declaration.",
                    file=agent_path,
                )


def validate(plugin_path: str) -> Report:
    """
    Run the Structural validation pass against `plugin_path`.

    Returns a `Report`. If `<plugin_path>/.claude-plugin/plugin.json` is
    missing, no subprocess is invoked and `report.fatal_error` is set
    instead.
    """
    report = Report(plugin_path=plugin_path)

    manifest_path = _manifest_path(plugin_path)
    if not os.path.isfile(manifest_path):
        report.fatal_error = (
            f"Not a plugin directory: {manifest_path} does not exist."
        )
        return report

    result = _run_structural_check(plugin_path)
    _populate_structural_section(report, result.stdout)
    _populate_per_skill_quality_section(report, plugin_path)
    check_tool_grants(plugin_path, report)
    return report


def _print_report(report: Report) -> None:
    print(json.dumps(report.to_dict(), indent=2))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: validate_plugin.py <plugin_path>", file=sys.stderr)
        return 2

    report = validate(argv[0])
    _print_report(report)

    if report.fatal_error is not None:
        return 1
    if report.success is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
