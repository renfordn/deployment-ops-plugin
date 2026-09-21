# broken-plugin (fixture)

A deliberately broken fixture plugin used by Phase 10 tests to exercise
`validate_plugin.py`'s structural, agent-context, dangling-reference, and
security/sanitization checks.

It ships the `sample-skill` skill for baseline structural validity, and its
own `bad-tool-agent` agent for release-note review.

It also documents the `nonexistent-plugin-command` command for triggering an
ad hoc health check -- a command that doesn't exist anywhere in this fixture
plugin, the "doc-named component" defect exercised by Phase 7's
dangling-reference cross-check loop.
