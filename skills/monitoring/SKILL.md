---
name: monitoring
description: Use this skill when the user wants to monitor deployment health, investigate an incident, or check for similar past incidents. Provides real-time health checks, incident detection, escalation routing, and cross-session pattern surfacing.
---

# Monitoring & Alerting Skill

Real-time health monitoring, incident detection, escalation routing, and cross-session pattern surfacing.

## Entry Modes

### Monitor Deployment Health
```
claude deploy monitor [--realtime]
```

Checks deployment health (service status, version consistency, error rate, performance).

### Report Incident
```
claude deploy incident <name> [--severity high|medium|low]
```

Log incident, escalate if needed, surface prior patterns from agent-nelly.

## Health Checks

### Service Status
- Service running and responsive
- No critical errors in logs
- CPU/memory/disk usage within limits

### Version Consistency
- All instances running same version
- No stale processes from previous deployment
- Configuration consistent

### Error Rate
- Error rate below threshold (default: <1%)
- No spike in error rate since deployment
- Error patterns logged

### Performance
- Latency within SLA (default: p95 < 500ms)
- Throughput meets expectations
- No performance degradation

## Health Check Schema

```json
{
  "timestamp": "2026-08-25T10:30:00Z",
  "environment": "staging",
  "deployed_version": "0.2.0",
  "checks": {
    "service_status": {
      "status": "healthy" | "degraded" | "failed",
      "services": {
        "api": "running",
        "worker": "running",
        "cache": "running"
      }
    },
    "version_consistency": {
      "status": "healthy" | "degraded",
      "instances": [
        { "host": "api-1", "version": "0.2.0", "status": "ok" },
        { "host": "api-2", "version": "0.2.0", "status": "ok" }
      ]
    },
    "error_rate": {
      "status": "healthy" | "degraded",
      "current": "0.2%",
      "threshold": "1%",
      "trend": "stable"
    },
    "performance": {
      "status": "healthy" | "degraded",
      "p95_latency": "350ms",
      "sla": "500ms",
      "throughput": "1000 req/s"
    }
  },
  "overall_status": "healthy" | "degraded" | "failed",
  "recommendations": []
}
```

## Incident Detection & Escalation

### Thresholds

| Metric | Threshold | Severity | Action |
|--------|-----------|----------|--------|
| Error rate spike | >5% | High | Escalate immediately |
| Service down | Yes | High | Page on-call |
| Latency spike | p95 >2000ms | Medium | Alert, wait 5min |
| Disk usage | >90% | Medium | Alert, investigate |
| Memory leak | Steady climb | Low | Log, investigate |

### Escalation Routing

```
Incident (Low) → log to agent-nelly
Incident (Medium) → log + alert team
Incident (High) → page on-call immediately
```

### Incident Schema

```json
{
  "incident_id": "incident-2026-08-25-001",
  "timestamp": "2026-08-25T10:30:00Z",
  "environment": "prod",
  "severity": "high" | "medium" | "low",
  "title": "Error rate spike detected in payment service",
  "description": "Error rate jumped from 0.2% to 8% in staging deployment 0.2.0",
  "affected_services": ["payment"],
  "root_cause": "Unknown (investigate)",
  "deployment_version": "0.2.0",
  "prior_incidents": [
    {
      "incident_id": "incident-2026-08-20-003",
      "title": "Payment service timeout",
      "resolution": "Increased database connection pool",
      "lesson": "Check database capacity before payment service deployment"
    }
  ],
  "recommended_action": "Rollback to 0.1.0 or debug error cause"
}
```

## Cross-Session Pattern Surfacing

Query agent-nelly for prior incidents with similar characteristics:

```python
def surface_incident_patterns(incident: Dict) -> List[Dict]:
    """Find similar prior incidents in cross-session history."""
    
    # Query agent-nelly for incidents with:
    # - Same service
    # - Similar error pattern
    # - Same severity
    
    patterns = agent_nelly.query(
        type="incident",
        service=incident["affected_services"][0],
        severity=incident["severity"]
    )
    
    # Return prior resolutions, lessons learned
    return patterns
```

This allows new incidents to surface:
- "This error happened 3 times before — here's how we fixed it"
- "Similar issue last month was caused by database capacity"
- "Previous rollback to 0.1.0 also failed — check rollback procedure"

## Monitoring Realtime Mode

With `--realtime` flag, stream health checks every 10 seconds:

```
$ claude deploy monitor --realtime

[10:30:00] Health check: healthy (service_status✓ version✓ error_rate✓ performance✓)
[10:30:10] Health check: healthy
[10:30:20] Health check: degraded (error_rate: 2.5% > 1% threshold)
[10:30:30] ⚠️  Error rate spike detected — escalating to team
[10:30:40] Alert sent to team Slack channel
[10:31:00] Searching incident history for similar issues...
[10:31:05] Found: incident-2026-08-20-003 "Payment service timeout" - increased DB pool
[10:31:10] Recommendation: Increase database connection pool or rollback to 0.1.0
```

## Integration

- **Agent-UX:** breadcrumb_only events (health_check, incident_detected)
- **Agent-Nelly:** persists incidents as new_fact, surfaces patterns, stores lessons learned
- **Agent-Cache-Plugin:** ephemeral tracking of current health status (not authoritative)

## Testing

See `tests/e2e/monitoring.test.js` for:
- Healthy deployment (all checks pass)
- Degraded service (one check fails, warning issued)
- Failed deployment (multiple checks fail, rollback recommended)
- Incident escalation (severity triggers appropriate routing)
- Pattern surfacing (similar prior incident found and surfaced)
