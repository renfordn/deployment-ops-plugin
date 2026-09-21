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

import hashlib
import json
import os
import re
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


# Phase 6b (tasks.md): the sibling-component cross-check loop.
#
# A named reference to another component reads as either a backtick-quoted
# name immediately followed by "agent"/"skill"/"command" (e.g. `` `foo`
# agent ``), or the bare phrase "the foo agent"/"the foo skill"/"the foo
# command". Both forms are how agent-creator.md's own vendored examples
# (and this plugin's own agent files) name a sibling component.
_SIBLING_NAME = r"[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*"
_SIBLING_REFERENCE_PATTERN = re.compile(
    rf"`({_SIBLING_NAME})`\s+(?:agent|skill|command)\b"
    rf"|\bthe\s+({_SIBLING_NAME})\s+(?:agent|skill|command)\b",
    re.IGNORECASE,
)

# The bare-phrase form ("the X agent/skill/command") also matches ordinary
# English prose that isn't naming a sibling component at all -- "the calling
# skill", "invoke the next command". The backtick-quoted form is explicit
# enough to trust as-is, so this stoplist only suppresses bare-phrase
# matches (see `_find_sibling_references`).
_SIBLING_BARE_PHRASE_STOPWORDS = {
    "calling", "next", "spawned", "completing", "current", "same", "given",
    "resulting", "corresponding", "existing", "actual", "new", "final",
    "first", "last", "other", "specific", "underlying", "requesting",
    "invoking", "returning",
}

# Claude Code platform-level agent types -- legitimately named in plugin
# prose (e.g. `` `Plan` agent ``) but not a component of any plugin.
_BUILTIN_AGENT_NAMES = {"plan", "explore", "general-purpose"}


def _enumerate_command_md_files(plugin_path: str) -> List[str]:
    """Enumerate `commands/*.md` files under `plugin_path`, in sorted order."""
    commands_dir = os.path.join(plugin_path, "commands")
    if not os.path.isdir(commands_dir):
        return []
    paths = []
    for entry in sorted(os.listdir(commands_dir)):
        if entry.endswith(".md"):
            full_path = os.path.join(commands_dir, entry)
            if os.path.isfile(full_path):
                paths.append(full_path)
    return paths


def _sibling_plugin_names(plugin_path: str) -> set:
    """
    Collect the lowercased directory names of other plugins living next to
    `plugin_path` in the same repo (siblings that themselves have a
    `.claude-plugin/` marker). A doc naming another plugin by its directory
    name (e.g. `` `code-reviewer` skill `` from a plugin that hands off to
    it) is a legitimate cross-plugin reference, not a dangling one -- this
    validator only ever receives a single plugin path, so it has no other
    way to know the sibling exists.
    """
    parent = os.path.dirname(os.path.normpath(plugin_path))
    if not os.path.isdir(parent):
        return set()
    names = set()
    try:
        entries = os.listdir(parent)
    except OSError:
        return set()
    for entry in entries:
        candidate = os.path.join(parent, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, ".claude-plugin")):
            names.add(entry.lower())
    return names


def _known_component_names(plugin_path: str) -> set:
    """
    Collect the plugin's actual component names (agents, skills, commands),
    lowercased by filename/directory-name stem -- the identity a reference
    like "the X agent" or `` `X` `` skill would name. Also includes sibling
    plugins in the same repo (`_sibling_plugin_names`) and Claude Code's
    built-in agent types (`_BUILTIN_AGENT_NAMES`), both of which are
    legitimate references this single-plugin scan can otherwise never
    resolve. Historical/removed component names mentioned in prose (e.g. "the
    former artifact-scaffolder skill") are a known limitation and still
    surface as findings -- there's no way to distinguish that from a genuine
    stale reference without parsing tense/qualifiers.
    """
    names = set()
    for agent_path in _enumerate_agent_md_files(plugin_path):
        names.add(os.path.splitext(os.path.basename(agent_path))[0].lower())
    for skill_md_path in _enumerate_skill_md_files(plugin_path):
        names.add(os.path.basename(os.path.dirname(skill_md_path)).lower())
    for command_path in _enumerate_command_md_files(plugin_path):
        names.add(os.path.splitext(os.path.basename(command_path))[0].lower())
    names |= _sibling_plugin_names(plugin_path)
    names |= _BUILTIN_AGENT_NAMES
    return names


def _find_sibling_references(text: str) -> set:
    """Extract lowercased candidate sibling-component names referenced in `text`."""
    names = set()
    for match in _SIBLING_REFERENCE_PATTERN.finditer(text or ""):
        if match.group(1) is None and match.group(2) is not None:
            if match.group(2).lower() in _SIBLING_BARE_PHRASE_STOPWORDS:
                continue
        name = match.group(1) or match.group(2)
        if name:
            names.add(name.lower())
    return names


def check_sibling_components(plugin_path: str, report: Report) -> None:
    """
    Populate the report's "Per-Agent Plugin-Context Findings" section: for
    every agent under `agents/`, parse named references to other
    agents/skills/commands in its `description` frontmatter and body, and
    flag any reference that doesn't resolve to an actual component in the
    same plugin (a `minor`, advisory finding -- consistent with the
    tool-grant loop's severity choice), attributed to the offending agent
    file. Multiple mentions of the same unresolved name in one file produce
    a single finding. A plugin with zero agents still gets the section
    (empty severity buckets), not an error.
    """
    section = "Per-Agent Plugin-Context Findings"
    report.sections.setdefault(section, _empty_severity_buckets())

    known_names = _known_component_names(plugin_path)

    for agent_path in _enumerate_agent_md_files(plugin_path):
        try:
            with open(agent_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            report.add_finding(section, "critical", f"Failed to read agent file: {exc}", file=agent_path)
            continue

        frontmatter, body = _split_frontmatter(text)
        description = frontmatter.get("description") if frontmatter else None
        description = description if isinstance(description, str) else ""

        referenced_names = _find_sibling_references(description) | _find_sibling_references(body)
        for name in sorted(referenced_names - known_names):
            report.add_finding(
                section,
                "minor",
                f"Agent references a sibling component `{name}`, which does not resolve to any "
                "agent, skill, or command in this plugin. Confirm it's a valid sibling "
                "reference, not a typo or a stale/removed component name.",
                file=agent_path,
            )


# Phase 6c (tasks.md): the best-practice-doc conformance loop. Lazily reads
# only this one snapshot file -- never fetches live (design.md's Risks
# section) -- and is SKIPPED with a clear notice if it's absent.
_BEST_PRACTICE_SNAPSHOT_RELATIVE_PATH = os.path.join("references", "anthropic-docs", "sub-agents.md")
_TRIGGER_PHRASE = "use this agent when"


def _agent_body_opens_with_persona(body: str) -> bool:
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.lower().startswith("you are ")
    return False


def _agent_has_example_block(description: str) -> bool:
    return "<example>" in (description or "").lower()


def _agent_has_trigger_phrase(description: str) -> bool:
    return _TRIGGER_PHRASE in (description or "").lower()


def check_best_practice_doc(plugin_path: str, report: Report) -> None:
    """
    Populate the report's "Per-Agent Plugin-Context Findings" section: for
    every agent under `agents/`, check its persona/trigger-phrase/examples
    structure against the best-practice snapshot at
    `references/anthropic-docs/sub-agents.md` (see scripts/refresh_docs.py
    for how that snapshot is refreshed; this module never fetches it live).
    If the snapshot is missing entirely, the check is SKIPPED with a clear,
    dedicated notice -- never silently zero-findings -- and no per-agent
    checks run. At most one finding is recorded per agent file, combining
    every deviation detected into a single message.
    """
    section = "Per-Agent Plugin-Context Findings"
    report.sections.setdefault(section, _empty_severity_buckets())

    snapshot_path = os.path.join(plugin_path, _BEST_PRACTICE_SNAPSHOT_RELATIVE_PATH)
    if not os.path.isfile(snapshot_path):
        report.add_finding(
            section,
            "minor",
            "Skipping best-practice-doc conformance check: no best-practice snapshot found at "
            f"`{_BEST_PRACTICE_SNAPSHOT_RELATIVE_PATH}`. Run `scripts/refresh_docs.py` to "
            "populate it, then re-run validation.",
        )
        return

    for agent_path in _enumerate_agent_md_files(plugin_path):
        try:
            with open(agent_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            report.add_finding(section, "critical", f"Failed to read agent file: {exc}", file=agent_path)
            continue

        frontmatter, body = _split_frontmatter(text)
        description = frontmatter.get("description") if frontmatter else None
        description = description if isinstance(description, str) else ""

        deviations = []
        if not _agent_has_trigger_phrase(description):
            deviations.append(
                'its `description` doesn\'t follow the "Use this agent when..." trigger-phrase '
                "convention"
            )
        if not _agent_body_opens_with_persona(body):
            deviations.append('its body doesn\'t open with a persona/role statement ("You are a...")')
        if not _agent_has_example_block(description):
            deviations.append("its `description` has no `<example>` block")

        if deviations:
            report.add_finding(
                section,
                "minor",
                "Deviates from agents/agent-creator.md's best-practice-doc conventions: "
                + "; ".join(deviations) + ".",
                file=agent_path,
            )


# Phase 7 (tasks.md): dangling-reference resolution and the
# security/sanitization scan, adapted from upstream plugin-validator.md's
# Security Checks section. Two new sections: "Dangling References" and
# "Security/Sanitization". Deliberately does not re-derive Phase 6a/6b's
# agent-level tool-grant/sibling-component findings -- the MCP cross-check
# below only looks in the "configured but never referenced" direction,
# since "referenced but not configured" is already check_tool_grants's job.
_CLAUDE_PLUGIN_ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"


# Path-segment allowlist (alnum/dot/dash/underscore/slash) rather than a
# blocklist: a blocklist wide enough to admit regex metacharacters like
# `[`, `]`, `^`, `\` made this pattern match its own source definition
# (dogfooded against this plugin's own scripts/validate_plugin.py) -- a
# real file path never contains those characters.
_HARDCODED_USER_PATH_PATTERN = re.compile(
    r"/Users/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*"
    r"|/home/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*"
    r"|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+(?:\\[A-Za-z0-9._-]+)*"
)

_SECRET_PATTERNS = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), "an AWS-shaped access key ID"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "a private key block"),
    (re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}"), "a Stripe-shaped secret key"),
    (
        re.compile(r"(?i)\b(?:api[_-]?key|secret|password)\b\s*[:=]\s*[\"']([A-Za-z0-9_\-]{16,})[\"']"),
        "a hardcoded credential-shaped value",
    ),
)

_INSECURE_URL_SCHEMES = ("http://", "ws://")
_SCANNABLE_EXTENSIONS = (".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt")
# "tests" is dev-only content (this plugin's own fixtures/test files,
# deliberately full of fake-but-realistic-looking secrets and example
# paths for testing this very scanner) -- not what ships to a customer, so
# it isn't scanned for customer-facing secrets/hardcoded paths.
_SCAN_SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", "tests"})


def _iter_plugin_text_files(plugin_path: str):
    """Yield (relative_path, text) for every scannable text file under `plugin_path`."""
    for root, dirs, files in os.walk(plugin_path):
        dirs[:] = [d for d in dirs if d not in _SCAN_SKIP_DIRS]
        for name in files:
            if not name.endswith(_SCANNABLE_EXTENSIONS):
                continue
            full_path = os.path.join(root, name)
            try:
                with open(full_path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            yield os.path.relpath(full_path, plugin_path), text


def _scan_for_secrets(plugin_path: str, report: Report, section: str) -> None:
    for rel_path, text in _iter_plugin_text_files(plugin_path):
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, description in _SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    report.add_finding(
                        section,
                        "critical",
                        f"Line {line_number} looks like it embeds {description} "
                        f"(`{match.group(0)[:40]}`) -- flagged for human review, not an "
                        "automatic block; confirm it's a placeholder, not a live credential.",
                        file=rel_path,
                    )


def _mcp_server_configs(plugin_path: str) -> Dict[str, dict]:
    """Merge `.mcp.json` and manifest `mcpServers` into one name -> config dict."""
    configs: Dict[str, dict] = {}

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
                configs.update({name: cfg for name, cfg in servers.items() if isinstance(cfg, dict)})

    manifest_servers = _load_manifest(plugin_path).get("mcpServers")
    if isinstance(manifest_servers, dict):
        for name, cfg in manifest_servers.items():
            if isinstance(cfg, dict):
                configs.setdefault(name, cfg)

    return configs


def _scan_mcp_urls(plugin_path: str, report: Report, section: str) -> None:
    mcp_json_file = ".mcp.json" if os.path.isfile(os.path.join(plugin_path, ".mcp.json")) else None
    for server_name, config in _mcp_server_configs(plugin_path).items():
        url = config.get("url")
        if isinstance(url, str) and url.lower().startswith(_INSECURE_URL_SCHEMES):
            report.add_finding(
                section,
                "critical",
                f"MCP server `{server_name}` is configured with an insecure URL (`{url}`); "
                "use https:// or wss:// instead of http:// or ws://.",
                file=mcp_json_file,
            )


def _scan_for_hardcoded_paths(plugin_path: str, report: Report, section: str) -> None:
    for rel_path, text in _iter_plugin_text_files(plugin_path):
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = _HARDCODED_USER_PATH_PATTERN.search(line)
            if match:
                report.add_finding(
                    section,
                    "critical",
                    f"Line {line_number} hardcodes a user-machine-specific absolute path "
                    f"(`{match.group(0)}`) instead of `{_CLAUDE_PLUGIN_ROOT_PLACEHOLDER}` -- "
                    "this will break on any other machine.",
                    file=rel_path,
                )


def _check_enterprise_manifest_fields(plugin_path: str, report: Report, section: str) -> None:
    manifest_file = os.path.join(".claude-plugin", "plugin.json")
    manifest = _load_manifest(plugin_path)

    version = manifest.get("version")
    if not isinstance(version, str) or not re.match(r"^\d+\.\d+\.\d+$", version):
        report.add_finding(
            section,
            "major",
            f"plugin.json's `version` ({version!r}) is not a valid semver (X.Y.Z) string.",
            file=manifest_file,
        )

    description = manifest.get("description")
    if not isinstance(description, str) or not description.strip():
        report.add_finding(
            section,
            "major",
            "plugin.json's `description` is missing or empty.",
            file=manifest_file,
        )


def _check_license_present(plugin_path: str, report: Report, section: str) -> None:
    candidates = ("LICENSE", "LICENSE.md", "LICENSE.txt")
    if not any(os.path.isfile(os.path.join(plugin_path, name)) for name in candidates):
        report.add_finding(
            section,
            "major",
            "No LICENSE file found at the plugin root -- required for a customer-facing release.",
        )


def check_security_sanitization(plugin_path: str, report: Report) -> None:
    """
    Populate the report's "Security/Sanitization" section: hardcoded
    credential/secret patterns and hardcoded user-machine-specific absolute
    paths anywhere in the plugin, non-HTTPS/WSS MCP server URLs, and
    enterprise-class manifest/LICENSE checks. Secret/path findings are
    `critical` but always name the file/line/match so a human can quickly
    confirm a false positive -- never a silent, unreviewable hard block.
    """
    section = "Security/Sanitization"
    report.sections.setdefault(section, _empty_severity_buckets())

    _scan_for_secrets(plugin_path, report, section)
    _scan_mcp_urls(plugin_path, report, section)
    _scan_for_hardcoded_paths(plugin_path, report, section)
    _check_enterprise_manifest_fields(plugin_path, report, section)
    _check_license_present(plugin_path, report, section)


def _hook_script_relative_paths(plugin_path: str) -> List[str]:
    """
    Extract `${CLAUDE_PLUGIN_ROOT}`-relative script paths from
    `hooks/hooks.json`'s `command`-type hook entries. A hardcoded absolute
    path (not using the placeholder) is the security check's concern, not
    this one -- see `_scan_for_hardcoded_paths`.
    """
    hooks_path = os.path.join(plugin_path, "hooks", "hooks.json")
    if not os.path.isfile(hooks_path):
        return []
    try:
        with open(hooks_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []

    events = data.get("hooks")
    if not isinstance(events, dict):
        return []

    paths = []
    for matcher_entries in events.values():
        if not isinstance(matcher_entries, list):
            continue
        for matcher_entry in matcher_entries:
            if not isinstance(matcher_entry, dict):
                continue
            hook_list = matcher_entry.get("hooks")
            if not isinstance(hook_list, list):
                continue
            for hook in hook_list:
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or _CLAUDE_PLUGIN_ROOT_PLACEHOLDER not in command:
                    continue
                remainder = command.split(_CLAUDE_PLUGIN_ROOT_PLACEHOLDER, 1)[1].split()[0]
                remainder = remainder.rstrip("\"'")
                paths.append(remainder.lstrip("/"))
    return paths


def _check_hook_scripts_exist(plugin_path: str, report: Report, section: str) -> None:
    hooks_file = os.path.join("hooks", "hooks.json")
    for relative_path in _hook_script_relative_paths(plugin_path):
        if not os.path.isfile(os.path.join(plugin_path, relative_path)):
            report.add_finding(
                section,
                "major",
                f"hooks/hooks.json references script `{relative_path}`, which does not exist "
                "in this plugin.",
                file=hooks_file,
            )


def _check_doc_named_components(plugin_path: str, report: Report, section: str) -> None:
    """
    For each command/agent/skill named in README.md or any SKILL.md file,
    verify it resolves to an actual plugin component. Reuses the same
    reference-parsing pattern as `check_sibling_components`, but over doc
    files rather than agent files.
    """
    known_names = _known_component_names(plugin_path)
    doc_paths = []
    readme_path = os.path.join(plugin_path, "README.md")
    if os.path.isfile(readme_path):
        doc_paths.append(readme_path)
    doc_paths.extend(_enumerate_skill_md_files(plugin_path))

    for doc_path in doc_paths:
        try:
            with open(doc_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        for name in sorted(_find_sibling_references(text) - known_names):
            report.add_finding(
                section,
                "minor",
                f"References a component `{name}`, which does not resolve to any agent, "
                "skill, or command in this plugin.",
                file=os.path.relpath(doc_path, plugin_path),
            )


def _check_manifest_named_components(plugin_path: str, report: Report, section: str) -> None:
    """
    For each path-shaped `skills`/`agents` manifest entry (e.g.
    `./skills/foo`), verify it resolves to an actual file. Bare-name
    entries (this plugin's own manifest convention) are skipped -- there's
    no agreed-upon resolution convention for those yet (a known, separately
    tracked gap), so flagging them here would be a guess, not a finding.
    """
    manifest_file = os.path.join(".claude-plugin", "plugin.json")
    manifest = _load_manifest(plugin_path)

    for entry in manifest.get("skills") or []:
        if isinstance(entry, str) and "/" in entry:
            relative = entry[2:] if entry.startswith("./") else entry
            if not os.path.isfile(os.path.join(plugin_path, relative, "SKILL.md")):
                report.add_finding(
                    section,
                    "minor",
                    f"plugin.json lists skill `{entry}`, which does not resolve to a `SKILL.md` file.",
                    file=manifest_file,
                )

    for entry in manifest.get("agents") or []:
        if isinstance(entry, str) and "/" in entry:
            relative = entry[2:] if entry.startswith("./") else entry
            if not os.path.isfile(os.path.join(plugin_path, relative)):
                report.add_finding(
                    section,
                    "minor",
                    f"plugin.json lists agent `{entry}`, which does not resolve to an agent file.",
                    file=manifest_file,
                )


def _referenced_mcp_server_names(plugin_path: str) -> set:
    """
    MCP server names actually referenced by some agent's `tools:`
    frontmatter (`mcp__<server>__...`). "Referenced but not configured" is
    already `check_tool_grants`'s finding -- this only looks the other way.
    """
    referenced = set()
    for agent_path in _enumerate_agent_md_files(plugin_path):
        try:
            with open(agent_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        frontmatter, _body = _split_frontmatter(text)
        for tool_name in _parse_agent_tools(frontmatter):
            if tool_name.startswith(_MCP_TOOL_PREFIX):
                referenced.add(tool_name[len(_MCP_TOOL_PREFIX):].split("__", 1)[0])
    return referenced


def _check_mcp_servers_configured_but_unreferenced(plugin_path: str, report: Report, section: str) -> None:
    mcp_json_file = ".mcp.json" if os.path.isfile(os.path.join(plugin_path, ".mcp.json")) else None
    configured = _mcp_server_configs(plugin_path)
    referenced = _referenced_mcp_server_names(plugin_path)
    for server_name in sorted(set(configured) - referenced):
        report.add_finding(
            section,
            "minor",
            f"MCP server `{server_name}` is configured but not referenced by any agent's "
            "declared tools -- confirm it's still needed.",
            file=mcp_json_file,
        )


def check_dangling_references(plugin_path: str, report: Report) -> None:
    """
    Populate the report's "Dangling References" section: hook script paths,
    doc-named components (README.md/SKILL.md mentions of a command/agent/
    skill), and MCP servers configured but never referenced. Deliberately
    excludes what Phase 6a/6b's agent-specific checks already own (agent
    tool-grants, agent-body sibling references).
    """
    section = "Dangling References"
    report.sections.setdefault(section, _empty_severity_buckets())

    _check_hook_scripts_exist(plugin_path, report, section)
    _check_doc_named_components(plugin_path, report, section)
    _check_manifest_named_components(plugin_path, report, section)
    _check_mcp_servers_configured_but_unreferenced(plugin_path, report, section)


# Phase 8 (tasks.md): the self-check gate -- preserves the original
# skill-creator-eval + git-hash-staleness + centralized eval-results
# self-check as one mode of the broader validator, scoped to this plugin's
# own three skills (not a generic check for arbitrary plugins, unlike every
# other check in this module). Synchronous and fast by design: it only
# reads pre-recorded `eval-results/<skill>.json` files and hashes tracked
# files -- it never runs a skill-creator eval live.
_SELF_CHECK_SKILLS = ("release-planner", "deployment-orchestrator", "monitoring")
_EVAL_RESULTS_DIR = os.path.join("skills", "release-planner", "eval-results")


def _eval_results_path(plugin_path: str, skill_name: str) -> str:
    return os.path.join(plugin_path, _EVAL_RESULTS_DIR, f"{skill_name}.json")


def _grading_evidence_path(plugin_path: str, skill_name: str) -> str:
    return os.path.join(plugin_path, _EVAL_RESULTS_DIR, f"{skill_name}.grading.json")


def _evals_path(plugin_path: str, skill_name: str) -> str:
    return os.path.join(plugin_path, "skills", skill_name, "evals", "evals.json")


def compute_skill_git_hash(plugin_path: str, skill_name: str) -> Optional[str]:
    """
    A stable hash over a skill directory's git-tracked files' current
    on-disk content (not the last-committed blob), so an uncommitted edit
    is detected immediately -- exactly when staleness matters most, right
    before a release. Returns None if `plugin_path` isn't a git repo or the
    skill directory has no tracked files.

    Excludes `_EVAL_RESULTS_DIR` itself: that directory lives inside the
    `release-planner` skill dir, but stores a hash *of* that skill's
    content -- including it in the hash it's stored alongside would make
    recording the hash immediately invalidate itself.
    """
    skill_dir_rel = os.path.join("skills", skill_name)
    eval_results_prefix = _EVAL_RESULTS_DIR + os.sep
    try:
        result = subprocess.run(
            ["git", "ls-files", skill_dir_rel],
            cwd=plugin_path,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None

    tracked_files = sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith(eval_results_prefix)
    )
    if not tracked_files:
        return None

    hasher = hashlib.sha256()
    for rel_file in tracked_files:
        hasher.update(rel_file.encode("utf-8"))
        try:
            with open(os.path.join(plugin_path, rel_file), "rb") as fh:
                hasher.update(fh.read())
        except OSError:
            continue
    return hasher.hexdigest()


@dataclass
class SelfCheckSkillResult:
    """One skill's self-check gate outcome."""

    skill: str
    blocked: bool
    # "missing" | "stale" | "parse-error" | "below-threshold" | "vacuous" |
    # "missing-evidence" | "evidence-parse-error" | "evidence-mismatch"
    reason: Optional[str] = None
    detail: Optional[str] = None


def _verify_grading_evidence(
    plugin_path: str, skill_name: str, recorded_summary: dict
) -> Tuple[Optional[str], Optional[str]]:
    """
    Cross-checks the eval-results summary against a committed grading-evidence
    file (`<skill>.grading.json`): one real grader-agent record per scenario
    defined in the skill's `evals/evals.json`, not just a single self-reported
    number.

    `eval-results/<skill>.json` alone can't tell a genuinely-graded run from a
    hand-edited one with a matching `git_hash` -- the hash only detects skill
    *content* drift, never whether an eval was ever actually executed. Evidence
    doesn't make fabrication impossible, but it raises the bar from "edit one
    JSON summary" to "produce a plausible per-scenario grading record naming
    every real scenario in evals.json", and it gives a human auditor something
    concrete to spot-check.

    Returns (reason, detail), both None when the evidence is present, parses,
    and covers every scenario in evals.json with a full pass.
    """
    evals_path = _evals_path(plugin_path, skill_name)
    try:
        with open(evals_path, "r", encoding="utf-8") as fh:
            evals_data = json.load(fh)
        scenario_names = {entry["name"] for entry in evals_data["evals"]}
    except (OSError, ValueError, KeyError, TypeError):
        return "evidence-parse-error", f"Could not read/parse evals.json at {evals_path}."
    if not scenario_names:
        return "evidence-parse-error", f"evals.json at {evals_path} defines no scenarios."

    evidence_path = _grading_evidence_path(plugin_path, skill_name)
    if not os.path.isfile(evidence_path):
        return "missing-evidence", f"No grading evidence file found at {evidence_path}."

    try:
        with open(evidence_path, "r", encoding="utf-8") as fh:
            evidence = json.load(fh)
        scenarios = evidence["scenarios"]
    except (OSError, ValueError, KeyError, TypeError):
        return "evidence-parse-error", f"Could not parse grading evidence JSON at {evidence_path}."

    if not isinstance(scenarios, list) or not scenarios:
        return "evidence-mismatch", f"Grading evidence at {evidence_path} has no scenarios recorded."

    evidenced_names = set()
    for entry in scenarios:
        try:
            name = entry["name"]
            g_summary = entry["grading"]["summary"]
            passed, total = g_summary["passed"], g_summary["total"]
        except (KeyError, TypeError):
            return "evidence-mismatch", f"Malformed scenario entry in grading evidence: {entry!r}"
        if not isinstance(total, int) or total <= 0:
            return "evidence-mismatch", f"Scenario '{name}' in grading evidence has zero graded expectations."
        if passed != total:
            return (
                "evidence-mismatch",
                f"Scenario '{name}' in grading evidence did not pass all expectations ({passed}/{total}).",
            )
        evidenced_names.add(name)

    missing = scenario_names - evidenced_names
    if missing:
        return (
            "evidence-mismatch",
            f"Grading evidence is missing scenario(s) defined in evals.json: {sorted(missing)}.",
        )
    extra = evidenced_names - scenario_names
    if extra:
        return (
            "evidence-mismatch",
            f"Grading evidence references scenario(s) not in evals.json: {sorted(extra)}.",
        )

    recorded_total = recorded_summary.get("total")
    if recorded_total != len(scenario_names):
        return (
            "evidence-mismatch",
            f"eval-results summary.total ({recorded_total}) doesn't match the number of scenarios "
            f"in evals.json ({len(scenario_names)}).",
        )

    return None, None


def _self_check_one_skill(plugin_path: str, skill_name: str) -> SelfCheckSkillResult:
    eval_path = _eval_results_path(plugin_path, skill_name)
    if not os.path.isfile(eval_path):
        return SelfCheckSkillResult(
            skill_name, True, "missing", f"No eval-results file found at {eval_path}."
        )

    try:
        with open(eval_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return SelfCheckSkillResult(skill_name, True, "parse-error", f"Could not parse eval-results JSON: {exc}")

    if not isinstance(data, dict):
        return SelfCheckSkillResult(skill_name, True, "parse-error", "eval-results JSON is not an object.")

    recorded_hash = data.get("git_hash")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else None
    pass_rate = summary.get("pass_rate") if summary else None
    total = summary.get("total") if summary else None
    if not isinstance(recorded_hash, str) or not recorded_hash:
        return SelfCheckSkillResult(skill_name, True, "parse-error", "eval-results JSON missing `git_hash`.")
    if not isinstance(pass_rate, (int, float)):
        return SelfCheckSkillResult(skill_name, True, "parse-error", "eval-results JSON missing `summary.pass_rate`.")
    if not isinstance(total, int) or total <= 0:
        return SelfCheckSkillResult(
            skill_name, True, "vacuous",
            "eval-results JSON's `summary.total` is missing or not a positive integer -- "
            "a record of zero graded scenarios can't establish release-readiness.",
        )

    current_hash = compute_skill_git_hash(plugin_path, skill_name)
    if current_hash is None or current_hash != recorded_hash:
        return SelfCheckSkillResult(
            skill_name, True, "stale",
            "Recorded `git_hash` doesn't match this skill's current tracked-file contents; "
            "re-run the skill-creator eval and refresh eval-results.",
        )

    if pass_rate < 1.0:
        return SelfCheckSkillResult(
            skill_name, True, "below-threshold", f"`summary.pass_rate` is {pass_rate}, below the required 1.0 (100%)."
        )

    evidence_reason, evidence_detail = _verify_grading_evidence(plugin_path, skill_name, summary)
    if evidence_reason is not None:
        return SelfCheckSkillResult(skill_name, True, evidence_reason, evidence_detail)

    return SelfCheckSkillResult(skill_name, False)


def check_self_check_gate(
    plugin_path: str, skill_names: Tuple[str, ...] = _SELF_CHECK_SKILLS
) -> List[SelfCheckSkillResult]:
    """Run the self-check gate for each of this plugin's own skills."""
    return [_self_check_one_skill(plugin_path, skill_name) for skill_name in skill_names]


def populate_self_check_gate_section(plugin_path: str, report: Report) -> None:
    """Populate the report's "Self-Check Gate" section, one finding per blocked skill."""
    section = "Self-Check Gate"
    report.sections.setdefault(section, _empty_severity_buckets())
    for result in check_self_check_gate(plugin_path):
        if result.blocked:
            report.add_finding(
                section,
                "critical",
                f"{result.skill}: {result.reason} -- {result.detail}",
                file=_eval_results_path(plugin_path, result.skill),
            )


def format_self_check_results(results: List[SelfCheckSkillResult]) -> List[str]:
    lines = []
    for result in results:
        if result.blocked:
            lines.append(f"✗ {result.skill}: BLOCKED ({result.reason}) -- {result.detail}")
        else:
            lines.append(f"✓ {result.skill}: OK")
    return lines


def run_self_check_gate(
    plugin_path: str, skill_names: Tuple[str, ...] = _SELF_CHECK_SKILLS
) -> Tuple[bool, List[str]]:
    """
    Run the self-check gate and return (blocked, messages). Every failing
    skill and its specific reason is reported together in one combined
    result -- never one-at-a-time -- so a multi-skill failure is visible in
    a single blocked message.
    """
    results = check_self_check_gate(plugin_path, skill_names)
    blocked = any(result.blocked for result in results)
    messages = format_self_check_results(results)
    if blocked:
        failing = ", ".join(f"{result.skill} ({result.reason})" for result in results if result.blocked)
        messages.append(f"✗ Self-check gate blocked: {failing}")
    else:
        messages.append("✓ Self-check gate passed: all skills fresh and at 100% pass rate")
    return blocked, messages


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
    check_sibling_components(plugin_path, report)
    check_best_practice_doc(plugin_path, report)
    check_dangling_references(plugin_path, report)
    check_security_sanitization(plugin_path, report)
    return report


def _print_report(report: Report) -> None:
    print(json.dumps(report.to_dict(), indent=2))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: validate_plugin.py <plugin_path> [--self-check]", file=sys.stderr)
        return 2

    plugin_path = argv[0]

    if "--self-check" in argv[1:]:
        report = Report(plugin_path=plugin_path)
        populate_self_check_gate_section(plugin_path, report)
        _print_report(report)
        return 1 if report.sections.get("Self-Check Gate", {}).get("critical") else 0

    report = validate(plugin_path)
    _print_report(report)

    if report.fatal_error is not None:
        return 1
    if report.success is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
