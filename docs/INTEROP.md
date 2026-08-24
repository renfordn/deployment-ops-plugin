# INTEROP: Integration Contracts

Deployment-ops-plugin integration model with agent-ux, agent-nelly, agent-cache-plugin, and agent-isdd.

## Overview

Sibling plugin architecture (Path A): Independent skill orchestrator with graceful integration to support layers. No edits to existing plugins required.

### Plugin Ecosystem

```
Requirements → Design → Tasks    (agent-isdd)
           ↓
      Implementation             (agent-tdd)
           ↓
      Code Review                (code-reviewer)
           ↓
Release Planning → Deployment → Monitoring    (deployment-ops-plugin)

Support Layers (across all phases):
- agent-ux: Visualization (event envelopes)
- agent-nelly: Memory (facts, lessons, patterns)
- agent-cache-plugin: Ephemeral caching (optional, graceful degradation)
```

---

## Agent-UX Integration

**Contract: Event Envelope (INTEROP.md-style)**

### Envelope Schema

```json
{
  "caller": "deployment-ops-plugin",
  "event_type": "breadcrumb_only" | "out_of_scope_flag",
  "phase_state": {
    "phase": "Release Planning" | "Deployment" | "Monitoring",
    "status": "in_progress" | "complete" | "blocked"
  },
  "delta": {},
  "artifact_path": null
}
```

### Event Types Used

**breadcrumb_only:**
- Sent when phase starts, completes, or progresses
- Updates breadcrumb status without artifact changes
- No delta payload needed

**out_of_scope_flag:**
- Sent when phase is blocked by error/blocker
- Optional delta: `{ "reason": "Permission denied" }`
- Signals deployment cannot proceed

### Usage Examples

**Release Planning started:**
```json
{
  "caller": "deployment-ops-plugin",
  "event_type": "breadcrumb_only",
  "phase_state": { "phase": "Release Planning", "status": "in_progress" }
}
```

**Deployment blocked by permissions:**
```json
{
  "caller": "deployment-ops-plugin",
  "event_type": "out_of_scope_flag",
  "phase_state": { "phase": "Deployment", "status": "blocked" },
  "delta": { "reason": "Missing CloudFormation IAM role" }
}
```

**Monitoring complete:**
```json
{
  "caller": "deployment-ops-plugin",
  "event_type": "breadcrumb_only",
  "phase_state": { "phase": "Monitoring", "status": "complete" }
}
```

### Unavailability Handling

If agent-ux is unavailable:
- Log once per session: `[ux-event-unavailable] agent-ux not available`
- Continue deployment/monitoring without failing
- Graceful degradation: no visualization, but operations proceed

---

## Agent-Nelly Integration

**Contract: Memory Persistence (INTEROP.md-style)**

### Batch Schema: New Facts

```json
{
  "project_slug": "users-jay-nelson-codebase-ai-plugins-claude-agent-ux",
  "new_facts": [
    {
      "type": "plugin_integration" | "deployment_check" | "incident" | "monitoring_metric",
      "key": "unique-identifier",
      "value": "fact content or JSON object",
      "source": "deployment-ops-plugin"
    }
  ]
}
```

### Batch Schema: Error Lessons

```json
{
  "project_slug": "users-jay-nelson-codebase-ai-plugins-claude-agent-ux",
  "error_lesson": {
    "scenario": "What went wrong (e.g., 'Deployment 0.2.0 unhealthy, rolled back to 0.1.0')",
    "lesson": "How to avoid next time (e.g., 'Investigate health check failure in 0.2.0')",
    "plugin": "deployment-ops-plugin"
  }
}
```

### Fact Types & Examples

**Release Pattern:**
```json
{
  "type": "plugin_integration",
  "key": "release-pattern",
  "value": "Release: bump CHANGELOG [Unreleased] → [version], sync .claude-plugin/plugin.json, commit-push-update-cache-clear"
}
```

**Deployment Decision:**
```json
{
  "type": "deployment_check",
  "key": "go-no-go-decision-prod-0.2.0",
  "value": {
    "go_no_go": "go",
    "blockers": [],
    "deployment_checks": { "environment": "pass", "artifact": "pass", "monitoring": "pass" }
  }
}
```

**Incident:**
```json
{
  "type": "incident",
  "key": "incident-2026-08-25-001",
  "value": {
    "severity": "high",
    "triggered_by": "Error rate spike",
    "health_snapshot": {},
    "resolution": "Increased database connection pool"
  }
}
```

### Query Pattern: Incident History

```python
# Query agent-nelly for similar prior incidents
similar_incidents = agent_nelly.query(
    type="incident",
    environment="prod",
    severity="high",
    triggered_by="Error rate spike"
)

# Returns: List of prior incidents with resolution + lesson_learned
# Example: incident-2026-08-20-003 (error rate spike → increased DB pool)
```

### Usage Flow

1. **Release Planning:** Persist release pattern after successful version bump
2. **Deployment:** Persist go/no-go decision before executing deployment
3. **Rollback:** Persist error_lesson if rollback triggered (for cross-session context)
4. **Monitoring:** Query incident history to surface similar prior issues
5. **Incident:** Persist new incident + error_lesson after escalation

### Unavailability Handling

If agent-nelly is unavailable:
- Log once per session: `[nelly-unavailable] agent-nelly not available`
- Continue operations without failing
- Graceful degradation: no cross-session context, but deployment proceeds

---

## Agent-Cache-Plugin Integration

**Contract: Ephemeral Caching (optional, graceful degradation)**

### Use Cases (Ephemeral Only)

- **Last Deployment Status:** Cache current deployment version + health status (expires after 1 hour)
- **Recent Incident Count:** Track # of incidents in last hour (expires after 1 hour)
- **Health Check History:** Buffer last 10 health check results (expires after 30 minutes)

**DO NOT use for:**
- Release version history (use agent-nelly instead)
- Deployment state/rollback tracking (use agent-nelly instead)
- Incident records (use agent-nelly instead)
- Authoritative deployment decisions (use agent-nelly instead)

### HTTP MCP Interface

```
localhost:7771/cache/write
localhost:7771/cache/read
localhost:7771/cache/invalidate
localhost:7771/cache/stats
```

### Example: Cache Last Deployment Status

```python
# Write
requests.post('http://localhost:7771/cache/write', json={
    "key": "last-deployment-prod",
    "value": { "version": "0.1.0", "status": "healthy", "timestamp": "2026-08-25T10:30:00Z" },
    "ttl": 3600  # 1 hour expiration
})

# Read
response = requests.get('http://localhost:7771/cache/read', params={"key": "last-deployment-prod"})
```

### Unavailability Handling

If agent-cache-plugin is unavailable:
- Log once per session: `[cache-unavailable] agent-cache-plugin not available`
- Continue operations without failing
- Graceful degradation: no ephemeral caching, but deployment proceeds
- No fallback storage (ephemeral data is lost on restart)

---

## Agent-ISDD Handoff

**Contract: Code Review → Deployment Pipeline**

After code-reviewer approves deployment-ops-plugin:

1. **Code-Reviewer Output** (JSON schema):
   ```json
   {
     "merge_eligible": true,
     "blockers": [],
     "dimensions": { "correctness": "pass", "security": "pass", "efficiency": "pass" },
     "agent_nelly_updates": []
   }
   ```

2. **Deployment-Ops-Plugin Takes Over:**
   - Handles release planning (version bump, CHANGELOG sync)
   - Executes deployments (pre-checks → deploy → health check)
   - Manages monitoring (health, incidents, escalation)
   - Tracks state via agent-nelly (cross-session memory)

3. **No Phase Extension Required:**
   - Deployment-ops-plugin is independent (sibling architecture)
   - agent-isdd remains Requirements/Design/Tasks only
   - No edits to agent-isdd phase-gate table or state schema

---

## Rollback Signaling

**Contract: Deployment Failure → Manual Intervention**

If deployment health fails and rollback is blocked (previous version also unhealthy):

1. Emit out_of_scope_flag event to agent-ux:
   ```json
   {
     "caller": "deployment-ops-plugin",
     "event_type": "out_of_scope_flag",
     "phase_state": { "phase": "Deployment", "status": "blocked" },
     "delta": { "reason": "Rollback blocked: previous version also unhealthy. Manual intervention required." }
   }
   ```

2. Persist error_lesson to agent-nelly:
   ```json
   {
     "scenario": "Deployment 0.2.0 failed, rollback to 0.1.0 also failed",
     "lesson": "Both versions unhealthy — investigate root cause before attempting recovery"
   }
   ```

3. Stop: Do not continue. Require manual debugging and fix.

---

## Integration Checklist

- [x] Agent-UX event envelopes sent on phase state changes
- [x] Graceful degradation if agent-ux unavailable (log, continue)
- [x] Agent-Nelly facts persisted on release/deployment/incidents
- [x] Graceful degradation if agent-nelly unavailable (log, continue)
- [x] Agent-Cache-Plugin used for ephemeral data only (not authoritative state)
- [x] Graceful degradation if agent-cache-plugin unavailable (log, continue)
- [x] No edits to agent-isdd, agent-tdd, code-reviewer, agent-ux, agent-nelly
- [x] No edits to their SKILL.md files or INTEROP.md contracts
- [x] Deployment-ops-plugin works independently as sibling
- [x] Deployment-ops-plugin integrates better with support layers (optional)

