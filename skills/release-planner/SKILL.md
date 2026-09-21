---
name: release-planner
description: Use this skill when the user wants to bump a plugin's release version, sync CHANGELOG.md with plugin.json, or run the pre-release checklist. Automates semantic version bumping with CHANGELOG and plugin manifest lockstep sync.
---

# Release Planner Skill

Automates semantic version bumping with CHANGELOG and plugin manifest sync.

## Entry Mode: Bump Release Version

Command: `claude deploy release bump <version>`

Moves CHANGELOG.md's `## [Unreleased]` section under a new `## [X.Y.Z]` heading and syncs `.claude-plugin/plugin.json`'s `version` field to match. Validates semver (X.Y.Z only).

### Acceptance Criteria
- [x] Detects and validates semver input (X.Y.Z format only)
- [x] Requires non-empty `## [Unreleased]` section in CHANGELOG.md
- [x] Moves Unreleased entries under new version heading with today's date
- [x] Updates plugin.json version field
- [x] Verifies CHANGELOG and plugin.json stay in sync (lockstep validation)
- [x] Handles edge cases: missing Unreleased section, malformed version, file permission errors
- [x] Graceful degradation: if files missing, report specific error (don't crash)
- [x] Integration: emit agent-ux event (phase_started → phase_complete or phase_blocked)
- [x] Integration: persist release pattern to agent-nelly on success

### Usage Example

```bash
$ claude deploy release bump 0.1.0

[ux-event] release-planner phase started
✓ CHANGELOG.md: moved [Unreleased] → [0.1.0]
✓ plugin.json: version bumped to 0.1.0
✓ Files in sync: CHANGELOG [0.1.0], plugin.json version 0.1.0
✓ Release version 0.1.0 prepared
[nelly-facts] Release pattern persisted
```

### Error Scenarios

**Missing Unreleased section:**
```bash
✗ CHANGELOG.md: missing ## [Unreleased] section
→ Add entries under ## [Unreleased] before bumping version
```

**Version mismatch after bump:**
```bash
✗ Lockstep validation failed
   CHANGELOG shows: [0.1.0]
   plugin.json shows: 0.0.9
→ Manual sync required
```

**Semver validation:**
```bash
✗ Invalid version format: 0.1
→ Use semver X.Y.Z format (e.g., 0.1.0)
```

### Worked Example (Before / After)

**CHANGELOG.md, before:**

```markdown
## [Unreleased]

### Added
- Incident pattern surfacing for the monitoring skill

## [0.4.1] - 2026-08-30
...
```

**Command:**

```bash
$ python3 skills/release-planner/bump_version.py 0.5.0
✓ CHANGELOG.md: moved [Unreleased] → [0.5.0]
✓ plugin.json: version bumped to 0.5.0
✓ Files in sync: CHANGELOG [0.5.0], plugin.json version 0.5.0
✓ Release version 0.5.0 prepared
```

**CHANGELOG.md, after:**

```markdown
## [Unreleased]

## [0.5.0] - 2026-08-31

### Added
- Incident pattern surfacing for the monitoring skill

## [0.4.1] - 2026-08-30
...
```

`## [Unreleased]` is left empty (not deleted) so the next round of work has somewhere to land, and
`.claude-plugin/plugin.json`'s `version` field is updated to match in the same operation --
CHANGELOG.md and plugin.json never drift apart, by construction.

## Semver Guidance

- **Major (X):** breaking changes -- a consumer's existing usage could stop working.
- **Minor (Y):** new features, backward compatible.
- **Patch (Z):** bug fixes only, no new behavior.

This skill validates the *format* (X.Y.Z), not which segment is "correct" to bump -- that's a
judgment call for whoever is releasing, based on what actually changed.

## Self-Check Gate (`--self-check`)

Pass `--self-check` to run this plugin's release-readiness gate *before* touching CHANGELOG.md or
plugin.json at all:

```bash
$ python3 skills/release-planner/bump_version.py 0.5.0 --self-check
```

For each of this plugin's own skills (`release-planner`, `deployment-orchestrator`,
`monitoring`), it reads `skills/release-planner/eval-results/<skill>.json` and blocks the bump if
that skill's record is:

- **missing** -- no eval-results file recorded yet
- **stale** -- the recorded content hash doesn't match the skill's current tracked-file contents
  (it changed since the last recorded eval). This hash (`compute_skill_git_hash`) is a SHA-256
  over the skill directory's git-tracked files and their current on-disk bytes -- it detects
  drift, but it is not a `git`-verifiable object (no `git cat-file`/`git hash-object` will
  reproduce it); the name reflects that it's scoped to `git ls-files`, not that it's a real git
  hash.
- **parse-error** -- the eval-results JSON is malformed or missing required fields
- **vacuous** -- `summary.total` is zero or missing, so the record can't actually attest to any
  graded scenario
- **below-threshold** -- the recorded `pass_rate` is under 100%
- **missing-evidence** -- no `eval-results/<skill>.grading.json` file exists. A `<skill>.json`
  summary alone is just a self-reported number; a matching content hash only proves the skill
  hasn't changed since *some* number was recorded, not that an eval ever really ran. The gate
  additionally requires a committed grading-evidence file: one real grader-agent record per
  scenario in the skill's `evals/evals.json`, each independently produced by a separate grader
  subagent (per `anthropic-skills:skill-creator`'s `agents/grader.md` pattern), so there's an
  actual, auditable artifact behind the number, not just the number itself.
- **evidence-parse-error** -- the evidence file or the skill's `evals/evals.json` is malformed
- **evidence-mismatch** -- the evidence doesn't cover every scenario `evals.json` defines, a
  covered scenario didn't pass all its graded expectations, or the evidence's scenario count
  doesn't match `summary.total`

This still doesn't make fabrication *impossible* -- it's a local file-consistency check, not a
cryptographic attestation of a real model run -- but it raises the bar from "edit one JSON
summary" to "produce a plausible per-scenario grading record naming every real scenario in
evals.json", and it gives a human auditor a concrete artifact to spot-check against the actual
eval prompts and expectations.

Every failing skill and its specific reason are reported together in one combined result, not
one at a time. The same gate is reachable without a version bump via `/plugin-validate
--self-check` or `scripts/validate_plugin.py <path> --self-check`, for checking status without
committing to a release.

## When NOT to Use This Skill

- **First-time (0.0.0 → 0.1.0) releases** with no `## [Unreleased]` content yet -- add entries
  first, then bump.
- **Major/breaking-change releases** -- this skill mechanically syncs version numbers; it doesn't
  judge whether a change is actually breaking. Decide the semver segment yourself before invoking
  it.
- **When the self-check gate is blocking** -- don't route around a `--self-check` failure by
  bumping without it; fix whatever the eval flagged (or record a fresh eval) instead.

## Release Checklist

See `release-checklist.md` for pre-release, release, and post-release procedures, including the
CUPS shorthand (Bump + Commit + Push + Update + Cache-Clear) for a full release cycle.

## Integration

- **Agent-UX:** breadcrumb_only events (phase_started, phase_complete, phase_blocked)
- **Agent-Nelly:** persists release pattern as new_fact on success
- **Error Handling:** phase_blocked event if any validation fails
- **Validator:** `scripts/validate_plugin.py`'s `--self-check` mode reads eval-results this
  skill's directory centrally stores for all three of this plugin's skills (see Self-Check Gate
  above)
