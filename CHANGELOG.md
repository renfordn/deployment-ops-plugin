# Changelog

All notable changes to the deployment-ops-plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2026-09-21

### Added
- Plugin/Skill Creator & Validator: fixture-based end-to-end verification (Phase 10d) --
  `scripts/validate_plugin.py`'s full `validate()` pipeline, run against the complete
  `tests/fixtures/broken-plugin/` fixture, is confirmed to produce exactly the three expected
  Phase 6a/6b/6c findings (tool-grant, sibling-component, best-practice-doc) in one composed
  run, each correctly attributed to its own agent file, with no spurious duplication from Phase
  7's dangling-reference/security checks. A second e2e test confirms the missing-snapshot
  degradation path end-to-end: with `references/anthropic-docs/` removed, the best-practice-doc
  finding is replaced by a clear skip notice while the other two findings are unaffected. This
  completes the Plugin/Skill Creator & Validator feature (all 18 tasks.md phases landed) --
  removing the "[In Progress]" marker carried on this feature's entries since v0.1.0.

## [0.1.6] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: registers `plugin-validate`,
  `plugin-scaffold-agent`, and `plugin-refresh-docs` in `.claude-plugin/plugin.json`'s
  `commands` array (Phase 9b).

### Fixed
- `.claude-plugin/plugin.json`'s `commands` array previously held a `{name, description}`
  object (`"deploy"`) with no corresponding `commands/*.md` file -- confirmed against
  `claude plugin validate --strict` to be invalid input regardless of the surrounding entries'
  shape. Replaced with the three real, path-shaped command entries, matching the
  `skills`/`agents` array convention; `claude plugin validate . --strict --json` now reports no
  manifest errors for `commands`.

## [0.1.5] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: this plugin's first `commands/` directory
  (Phase 9a) — `/plugin-validate` (wraps `scripts/validate_plugin.py`, including its
  `--self-check` mode), `/plugin-scaffold-agent` (wraps `scripts/create_agent.py`'s
  agent-creator Create mode), and `/plugin-refresh-docs` (wraps `scripts/refresh_docs.py`) —
  thin slash-command wrappers over the scripts/agents built in prior phases. Not yet registered
  in `.claude-plugin/plugin.json` (Phase 9b).

## [0.1.4] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: `scripts/validate_plugin.py` gains a
  `--self-check` mode (Phase 8) preserving the original release-readiness gate for this plugin's
  own three skills (release-planner, deployment-orchestrator, monitoring) — reads each skill's
  `skills/release-planner/eval-results/<skill>.json`, blocking on a missing file, a stale
  git-hash (recomputed from the skill's current tracked-file contents, excluding the
  eval-results directory itself), a parse error, or a `pass_rate` below 100%, and reporting every
  failing skill together in one combined result. `skills/release-planner/bump_version.py` gains a
  matching `--self-check` flag that runs the gate before touching CHANGELOG.md or plugin.json,
  refusing the bump if blocked. Slash-command wiring is still in progress.

## [0.1.3] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: `scripts/validate_plugin.py` gains
  `check_dangling_references` (Phase 7) — hook script paths, README/SKILL.md-named
  commands/agents/skills, path-shaped manifest `skills`/`agents` entries, and MCP servers
  configured but never referenced — and `check_security_sanitization` (Phase 7) — hardcoded
  credential/secret patterns (with file/line/match context, flagged for human review rather than
  a hard block), non-HTTPS/WSS MCP server URLs, hardcoded user-machine-specific absolute paths,
  and enterprise-class manifest/LICENSE checks (semver, non-empty description, LICENSE
  presence). Both integrate with Phase 6a/6b's agent-specific tool-grant/sibling-component
  findings without duplicating them. The self-check release gate and slash-command wiring are
  still in progress.

## [0.1.2] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: `scripts/validate_plugin.py` gains
  `check_sibling_components` (Phase 6b) — cross-checks named agent/skill/command references in
  each agent's `description` and body against the plugin's actual components, flagging
  unresolvable sibling references — and `check_best_practice_doc` (Phase 6c) — checks each
  agent's persona/trigger-phrase/examples structure against the `references/anthropic-docs/
  sub-agents.md` best-practice snapshot, skipping with a clear notice when that snapshot is
  absent. All three plugin-context agent validation loops (tool-grant, sibling-component,
  best-practice-doc) are now wired into `validate()`. The self-check release gate and
  slash-command wiring are still in progress.

## [0.1.1] - 2026-09-21

### Added
- **[In Progress]** Plugin/Skill Creator & Validator: `scripts/validate_plugin.py` gains
  `check_tool_grants` — cross-checks each agent's declared `tools:` frontmatter against the
  plugin's known tool universe (Claude Code built-ins + declared MCP servers), flagging
  unresolvable tool references (the first of three planned plugin-context validation loops;
  sibling-component and best-practice-doc checks are still in progress).

## [0.1.0] - 2026-09-21

### Added
- Release Planning skill: automate version bumping with CHANGELOG + plugin.json lockstep sync
- Deployment Orchestrator skill: pre-deployment checks, go/no-go decisions, deployment execution, rollback support
- Monitoring & Alerting skill: real-time health checks, incident detection, escalation routing, pattern surfacing
- Agent-UX integration: event envelope-based visualization (breadcrumb_only, out_of_scope_flag)
- Agent-Nelly integration: persistent release patterns, deployment decisions, incident context across sessions
- Agent-Cache-Plugin integration: ephemeral tracking of deployment status (optional, graceful degradation)
- E2E test suites: deployment pipeline tests, monitoring & alerting tests, graceful degradation tests
- INTEROP.md: integration contracts with all support layers
- Comprehensive documentation: release guide, deployment strategy, monitoring guide, troubleshooting
- **[In Progress]** Plugin/Skill Creator & Validator: vendored `plugin-validator`, `skill-reviewer`,
  `agent-creator` agents (adapted from `anthropics/claude-code`'s `plugin-dev` plugin);
  `scripts/validate_plugin.py` structural validation pass (shells out to `claude plugin validate
  --strict --json`) plus a Per-Skill Quality section (trigger-phrase/word-count/progressive-
  disclosure checks); `scripts/create_agent.py` agent-scaffolding Create mode; `scripts/
  refresh_docs.py` best-practice-doc snapshot mechanism (lazy-loaded, manually-refreshed,
  structurally isolated from the validator); a fixture plugin at `tests/fixtures/broken-plugin/`
  for end-to-end validator testing. Plugin-context agent validation (tool-grant/sibling-component/
  best-practice-doc cross-checks), the self-check release gate, and slash-command wiring are still
  in progress — see `~/.claude/sdd-memory/.../spec/2026-09-21-skill-creator-release-readiness-gate/`
  for the full spec and task tracker.

### Changed
- N/A (initial release)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A (initial release; follow security best practices for credentials/permissions)

---

## Version History

### Unreleased (v0.1.0-alpha)
**Release Date:** TBD

**Status:** In Development

**Features:**
- Complete Release Planning automation
- Complete Deployment orchestration with rollback
- Complete Monitoring & Alerting with pattern surfacing
- Graceful integration with agent-ux, agent-nelly, agent-cache-plugin
- E2E test coverage for all major scenarios

**Known Limitations:**
- High-risk components (Deployment and Monitoring agents) require code-review before production
- Incident pattern surfacing depends on agent-nelly availability; graceful degradation if unavailable
- Ephemeral caching (agent-cache-plugin) lost on restart; not suitable for authoritative state

**Next Steps (Post-v0.1.0):**
- v0.2.0: Support for multiple cloud providers (AWS, GCP, Azure)
- v0.3.0: Advanced rollback strategies (blue-green, canary)
- v0.4.0: Cost optimization and resource usage analytics
- v1.0.0: Production hardening and security audit

---

## Release Notes

### v0.1.0 (Target: Q3 2026)

**Release Planning:**
- [x] Version bump automation (semver X.Y.Z validation)
- [x] CHANGELOG ↔ plugin.json lockstep sync
- [x] Release checklist (pre-, release, post-release)
- [x] CUPS workflow shorthand documentation

**Deployment Orchestration:**
- [x] Pre-deployment validation (environment, artifact, monitoring)
- [x] Go/no-go decision with blocker tracking
- [x] Deployment execution (environment-specific handling)
- [x] Health check verification post-deployment
- [x] Automatic rollback on health failure
- [x] Rollback blocking when previous version unhealthy
- [x] Deployment state persistence to agent-nelly

**Monitoring & Alerting:**
- [x] Continuous health monitoring (service status, version consistency, error rate, performance)
- [x] Incident detection and severity classification
- [x] Escalation routing (on-call for high, team for medium, nelly for low)
- [x] Cross-session pattern surfacing (similar prior incidents)
- [x] Realtime monitoring mode with streaming health checks
- [x] Incident history persistence to agent-nelly

**Integration & Testing:**
- [x] Agent-UX event envelope integration (graceful degradation)
- [x] Agent-Nelly memory contracts (graceful degradation)
- [x] Agent-Cache-Plugin ephemeral caching (graceful degradation)
- [x] E2E test suites (deployment, monitoring, graceful degradation)
- [x] INTEROP.md contracts documented
- [x] Comprehensive documentation (README, release guide, deployment guide, monitoring guide, INTEROP)

**Code Quality:**
- [x] High-risk components (Deployment and Monitoring agents) code-reviewed
- [x] Test coverage >80% for critical paths
- [x] Security best practices documented
- [x] Graceful degradation pattern throughout

---

## Contributing

See CONTRIBUTING.md for contribution guidelines.

## License

MIT

