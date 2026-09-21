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

## Release Checklist

See `release-checklist.md` for pre-release, release, and post-release procedures.

## Integration

- **Agent-UX:** breadcrumb_only events (phase_started, phase_complete, phase_blocked)
- **Agent-Nelly:** persists release pattern as new_fact on success
- **Error Handling:** phase_blocked event if any validation fails
