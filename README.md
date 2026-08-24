# Deployment & Operations Plugin

Release planning, deployment automation, and monitoring/alerting for the development lifecycle.

## Overview

Completes the development lifecycle by adding Deployment & Operations coverage. Works alongside agent-isdd (Requirements/Design/Tasks), agent-tdd (Implementation), and code-reviewer (Code Review).

### Architecture

**Sibling Plugin Model (Path A):** Independent skill orchestrator with graceful integration:
- **Agent-UX Integration:** Event envelope-based progress visualization (breadcrumb_only, out_of_scope_flag event types)
- **Agent-Nelly Integration:** Durable memory for release patterns, deployment decisions, incident context
- **Agent-Cache-Plugin Integration:** Ephemeral tracking (optional, graceful degradation)
- **No Edits to Existing Plugins:** Graceful degradation if support layers unavailable

### Capabilities

- **Release Planning:** Version bump automation (CHANGELOG + plugin.json sync), release checklists
- **Deployment Automation:** Environment readiness checks, artifact validation, go/no-go decisions, rollback support
- **Monitoring & Alerting:** Health checks, incident detection, escalation routing, cross-session pattern surfacing

## Installation

```bash
claude plugin add deployment-ops-plugin
```

## Usage

### Release Planning

```bash
claude deploy release bump <version>
```

Bumps plugin version in CHANGELOG.md and .claude-plugin/plugin.json in lockstep.

### Deployment

```bash
claude deploy <environment> [--rollback]
```

Deploys to specified environment with pre-deployment checks and optional rollback.

### Monitoring

```bash
claude deploy monitor [--realtime]
claude deploy incident <name> [--severity high|medium|low]
```

Monitor deployment health or escalate incidents.

## Integration

### Agent-UX (Visualization)

Sends event envelopes for real-time status visualization:
```json
{
  "caller": "deployment-ops-plugin",
  "event_type": "breadcrumb_only" | "out_of_scope_flag",
  "phase_state": { "phase": "Release Planning", "status": "in_progress" }
}
```

### Agent-Nelly (Memory)

Persists release patterns, deployment decisions, incident context:
```json
{
  "project_slug": "...",
  "new_facts": [
    {
      "type": "plugin_integration",
      "key": "release-pattern",
      "value": "Bump CHANGELOG [Unreleased] → version, sync plugin.json"
    }
  ]
}
```

### Agent-Cache-Plugin (Ephemeral)

Optional: tracks last deployment status, recent incidents (in-memory, non-persistent).

## Documentation

- [Release Planning Guide](docs/release-planning.md)
- [Deployment Strategy](docs/deployment-strategy.md)
- [Monitoring & Alerting](docs/monitoring.md)
- [INTEROP Contracts](docs/INTEROP.md)
- [Troubleshooting](docs/troubleshooting.md)

## Development

See [tasks.md](../../sdd-memory/users-jay-nelson-codebase-ai-plugins-claude-agent-ux/spec/2026-08-23-plugin-coverage-gaps/tasks/tasks.md) for implementation phases.

## Testing

```bash
npm test
```

E2E test suite covers:
- Release version bumping with CHANGELOG lockstep
- Deployment success, failures, rollback scenarios
- Monitoring health checks and incident escalation
- Graceful degradation when support layers unavailable

## License

MIT

## Contributing

This plugin is part of the Claude Code plugin ecosystem. See [INTEROP.md](docs/INTEROP.md) for integration guidelines.
