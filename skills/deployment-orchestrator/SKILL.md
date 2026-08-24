# Deployment Orchestrator Skill

Automates deployment strategy with pre-checks, artifact validation, go/no-go decisions, and rollback support.

## Entry Mode: Deploy to Environment

Command: `claude deploy <environment> [--rollback] [--dry-run]`

Validates environment readiness, verifies artifact integrity, decides go/no-go, executes deployment, and tracks rollback state.

### Pre-Deployment Checks

1. **Environment Readiness**
   - Required permissions (IAM, network, secrets)
   - Service connectivity (targets reachable)
   - Configuration consistency (env vars, secrets configured)
   - Previous deployment state (no stale processes)

2. **Artifact Integrity**
   - Artifact exists and matches deployment version
   - Checksum verified (if available)
   - All dependencies resolved
   - No missing configuration files

3. **Monitoring Configuration**
   - Health checks configured
   - Alerting enabled
   - Incident escalation routing ready

### Go/No-Go Decision Schema

Mirrors code-reviewer's JSON handoff pattern:

```json
{
  "go_no_go": "go" | "no_go",
  "blockers": [
    {
      "category": "environment|artifact|monitoring",
      "severity": "high|medium",
      "description": "What's blocking deployment",
      "resolution": "How to fix it"
    }
  ],
  "deployment_checks": {
    "environment_readiness": "pass" | "fail",
    "artifact_integrity": "pass" | "fail",
    "monitoring_configured": "pass" | "fail"
  },
  "deployment_state": {
    "previous_version": "0.1.0",
    "previous_state": "healthy|degraded|failed",
    "rollback_available": true | false
  },
  "agent_nelly_updates": {
    "new_facts": [],
    "error_lesson": null
  }
}
```

### Execution Flow

1. **Pre-Flight Checks** → Go/No-Go Decision
2. **If Go:** Execute Deployment
3. **Post-Deployment:** Verify Health
4. **If Healthy:** Success
5. **If Degraded/Failed:** Rollback Trigger

### Rollback Strategy

- **Automatic Rollback:** Triggered if post-deployment health checks fail
- **Manual Rollback:** User can request `--rollback` flag
- **Rollback Guard:** Previous version must be healthy before rollback
- **State Tracking:** Deployment state persisted to agent-nelly (for cross-session context)

## Environment Contracts

### Development
- Permissions: relaxed (test deployments expected)
- Artifact Requirements: minimal
- Monitoring: basic health checks
- Rollback: same-version redeploy OK

### Staging
- Permissions: moderate (staging owner)
- Artifact Requirements: checksums verified, all deps present
- Monitoring: full health checks, error rate tracking
- Rollback: previous version available

### Production
- Permissions: strict (prod owner + on-call)
- Artifact Requirements: signed artifacts, checksums, full audit trail
- Monitoring: comprehensive, real-time alerting
- Rollback: immediate if health drops below SLA

## Integration

- **Agent-UX:** breadcrumb_only events (checks → decision → deployment → health)
- **Agent-Nelly:** persists go/no-go decisions, rollback reasons, deployment patterns
- **Agent-Cache-Plugin:** ephemeral tracking of last deployment status (not authoritative)

## Error Scenarios

### Missing Permissions
```json
{
  "go_no_go": "no_go",
  "blockers": [{
    "category": "environment",
    "severity": "high",
    "description": "IAM role missing CloudFormation permissions",
    "resolution": "Add iam:PassRole, cloudformation:* to role"
  }]
}
```

### Artifact Missing
```json
{
  "go_no_go": "no_go",
  "blockers": [{
    "category": "artifact",
    "severity": "high",
    "description": "Artifact not found: deployment-ops-plugin-0.2.0.tar.gz",
    "resolution": "Run release pipeline, verify artifact generated"
  }]
}
```

### Health Check Failed (Post-Deployment)
```json
{
  "go_no_go": "go",
  "deployment_checks": { /* all pass */ }
}
→ [Post-deployment health check fails]
→ [Automatic rollback triggered]
→ agent-nelly persists error_lesson: "Health check failed after deploy 0.2.0, rolled back to 0.1.0"
```

## Testing

See `tests/e2e/deployment.test.js` for:
- Success case (all checks pass, deployment succeeds)
- Permission-denied block (pre-flight check fails)
- Artifact-missing block (artifact validation fails)
- Rollback scenario (post-deployment health fails, automatic rollback)
- Rollback failure (previous version also unhealthy, manual intervention needed)
