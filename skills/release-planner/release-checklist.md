# Release Checklist

## Pre-Release (Code Readiness)

- [ ] Code review complete (all commits approved by code-reviewer or peer)
- [ ] Tests passing (unit + integration tests green)
- [ ] Documentation updated (README, SKILL.md, INTEROP.md reflect changes)
- [ ] CHANGELOG.md updated (all changes documented under `## [Unreleased]`)
- [ ] No blocking security findings (code-reviewer cleared)
- [ ] Commit history clean (clear messages, logical chunks)

## Release (Version Bump & Commit)

- [ ] Run version bump: `claude deploy release bump <version>`
  - Validates semver X.Y.Z format
  - Moves CHANGELOG [Unreleased] → [version]
  - Syncs plugin.json version
  - Verifies lockstep
- [ ] Commit: `git add -A && git commit -m "Release X.Y.Z"`
- [ ] Tag: `git tag vX.Y.Z`
- [ ] Push: `git push origin main --tags`

## Post-Release (Deployment & Cache Clear)

- [ ] Update plugin in Claude Code marketplace: `claude plugin update deployment-ops-plugin@<version>`
- [ ] Clear stale cache: `rm -rf ~/.claude/plugins/cache/<marketplace>/deployment-ops-plugin/<old-version>`
- [ ] Verify plugin loads: `claude plugin list | grep deployment-ops-plugin`
- [ ] Run quick E2E test: `npm test` or manual smoke test

## Rollback (If Release Issues Found)

- [ ] Revert tag: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
- [ ] Revert commit: `git revert <commit-hash> && git push origin main`
- [ ] Bump version again after fix: `claude deploy release bump X.Y.(Z+1)`
- [ ] Re-release with fixes

## CUPS Workflow (User Shorthand)

**Release = Bump + Commit + Push + Update + Cache-Clear**

```bash
# 1. Bump
claude deploy release bump 0.2.0

# 2. Commit
git add -A && git commit -m "Release 0.2.0"
git tag v0.2.0
git push origin main --tags

# 3. Update
claude plugin update deployment-ops-plugin@0.2.0

# 4. Cache-Clear
rm -rf ~/.claude/plugins/cache/*/deployment-ops-plugin/*

# Done!
```

## Notes

- **Semver:** Use X.Y.Z format (e.g., 0.1.0, 1.2.3)
  - Major (X): Breaking changes
  - Minor (Y): New features, backward compatible
  - Patch (Z): Bug fixes, no new features
- **CHANGELOG:** Unreleased section must exist before bumping
- **Plugin Marketplace:** Update step ensures latest version available to all users
- **Cache Clear:** Removes stale cached versions, avoids version confusion
