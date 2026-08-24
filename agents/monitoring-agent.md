# Monitoring Agent

Real-time health monitoring, incident detection, escalation routing, and cross-session pattern surfacing.

## Responsibilities

1. **Continuous Health Monitoring**
   - Periodic health checks (every 10-30 seconds)
   - Detect service degradation or failures
   - Compare against thresholds and SLAs

2. **Incident Detection**
   - Recognize error spikes, performance degradation, service outages
   - Classify by severity (high/medium/low)
   - Surface related prior incidents from agent-nelly

3. **Escalation Routing**
   - High severity → page on-call immediately
   - Medium severity → alert team, wait for investigation
   - Low severity → log to agent-nelly for later analysis

4. **Pattern Surfacing**
   - Query agent-nelly for similar prior incidents
   - Surface resolution strategies and lessons learned
   - Build incident memory across sessions

## Entry Points

### Monitor Command
```
claude deploy monitor [--realtime] [--interval 10s]
```

Parameters:
- `--realtime`: Stream health checks continuously
- `--interval`: Check frequency (default: 10s realtime, 5m background)

### Incident Command
```
claude deploy incident <name> [--severity high|medium|low]
```

## Implementation

### Health Check Orchestration

```python
def monitor_health(env: str, version: str, realtime: bool = False) -> Generator[Dict, None, None]:
    """
    Continuously monitor deployment health.
    
    Yields health check results every interval.
    """
    
    interval = 10 if realtime else 300  # 10s realtime, 5min background
    
    while True:
        health = {
            "timestamp": datetime.now().isoformat(),
            "environment": env,
            "deployed_version": version,
            "checks": {}
        }
        
        # Run all health checks
        health["checks"]["service_status"] = check_service_status(env)
        health["checks"]["version_consistency"] = check_version_consistency(env, version)
        health["checks"]["error_rate"] = check_error_rate(env)
        health["checks"]["performance"] = check_performance(env)
        
        # Determine overall status
        statuses = [check["status"] for check in health["checks"].values()]
        if "failed" in statuses:
            health["overall_status"] = "failed"
        elif "degraded" in statuses:
            health["overall_status"] = "degraded"
        else:
            health["overall_status"] = "healthy"
        
        # Generate recommendations
        health["recommendations"] = generate_recommendations(health)
        
        yield health
        
        if not realtime:
            break
        
        time.sleep(interval)
```

### Individual Check Implementations

**Service Status:**
```python
def check_service_status(env: str) -> Dict:
    """Verify all services are running and responsive."""
    services = get_services_for_env(env)
    check_results = {}
    
    for service in services:
        try:
            response = requests.get(f"http://{service}:8080/health", timeout=5)
            check_results[service] = "running" if response.status_code == 200 else "unhealthy"
        except Exception as e:
            check_results[service] = "failed"
    
    return {
        "status": "healthy" if all(v == "running" for v in check_results.values()) else "degraded",
        "services": check_results
    }
```

**Version Consistency:**
```python
def check_version_consistency(env: str, expected_version: str) -> Dict:
    """Verify all instances running same version."""
    instances = get_instances_for_env(env)
    version_map = {}
    
    for instance in instances:
        try:
            version = get_instance_version(instance)
            version_map[instance["host"]] = {
                "version": version,
                "status": "ok" if version == expected_version else "mismatch"
            }
        except Exception:
            version_map[instance["host"]] = {"status": "unreachable"}
    
    mismatches = sum(1 for v in version_map.values() if v.get("status") == "mismatch")
    status = "degraded" if mismatches > 0 else "healthy"
    
    return {
        "status": status,
        "instances": [{"host": k, **v} for k, v in version_map.items()]
    }
```

**Error Rate:**
```python
def check_error_rate(env: str, threshold: float = 0.01) -> Dict:
    """Check error rate against threshold."""
    current_rate = get_error_rate(env)
    prior_rate = get_prior_error_rate(env, minutes=5)
    
    trend = "increasing" if current_rate > prior_rate else "stable"
    
    return {
        "status": "degraded" if current_rate > threshold else "healthy",
        "current": f"{current_rate:.1%}",
        "threshold": f"{threshold:.1%}",
        "trend": trend
    }
```

**Performance:**
```python
def check_performance(env: str, sla_p95: float = 0.5) -> Dict:
    """Check latency against SLA."""
    latency = get_p95_latency(env)
    throughput = get_throughput(env)
    
    return {
        "status": "degraded" if latency > sla_p95 else "healthy",
        "p95_latency": f"{latency*1000:.0f}ms",
        "sla": f"{sla_p95*1000:.0f}ms",
        "throughput": f"{throughput:.0f} req/s"
    }
```

### Incident Detection

```python
def detect_incident(health: Dict) -> Optional[Dict]:
    """Detect if health check indicates an incident."""
    
    # Check for failures or significant degradation
    if health["overall_status"] == "failed":
        return {
            "severity": "high",
            "triggered_by": "Service failure"
        }
    
    # Check for error rate spike
    error_check = health["checks"]["error_rate"]
    if error_check["status"] == "degraded" and error_check["trend"] == "increasing":
        return {
            "severity": "high",
            "triggered_by": "Error rate spike"
        }
    
    # Check for performance degradation
    perf_check = health["checks"]["performance"]
    if perf_check["status"] == "degraded":
        return {
            "severity": "medium",
            "triggered_by": "Performance SLA breach"
        }
    
    # Check for version inconsistency
    version_check = health["checks"]["version_consistency"]
    if version_check["status"] == "degraded":
        return {
            "severity": "medium",
            "triggered_by": "Version inconsistency"
        }
    
    return None
```

### Escalation Routing

```python
def escalate_incident(incident: Dict, env: str, version: str) -> None:
    """Route incident to appropriate handler based on severity."""
    
    if incident["severity"] == "high":
        page_oncall(env, incident)
        emit_event("phase_blocked", f"Deployment {version}", incident["triggered_by"])
    
    elif incident["severity"] == "medium":
        alert_team(env, incident)
        emit_event("phase_blocked", f"Deployment {version}", incident["triggered_by"])
    
    else:  # low
        log_incident(incident)
        emit_event("breadcrumb_only", f"Deployment {version}", "degraded")
```

### Pattern Surfacing

```python
def surface_incident_patterns(incident: Dict, env: str) -> List[Dict]:
    """Find and surface similar prior incidents from agent-nelly."""
    
    # Query for similar incidents
    similar = agent_nelly.query(
        type="incident",
        environment=env,
        severity=incident["severity"],
        triggered_by=incident["triggered_by"]
    )
    
    patterns = []
    for prior in similar[:3]:  # Top 3 similar incidents
        patterns.append({
            "incident_id": prior["id"],
            "date": prior["date"],
            "resolution": prior["resolution"],
            "lesson": prior["lesson_learned"]
        })
    
    return patterns
```

### Memory Persistence

```python
def persist_incident_to_memory(incident: Dict, health: Dict) -> None:
    """Persist incident details to agent-nelly for cross-session context."""
    
    facts = [{
        "type": "incident",
        "key": f"incident-{incident['id']}",
        "value": {
            "severity": incident["severity"],
            "triggered_by": incident["triggered_by"],
            "health_snapshot": health
        },
        "source": "monitoring-agent"
    }]
    
    agent_nelly.persist_facts(facts)
    
    # If high-severity incident, also persist lesson learned
    if incident["severity"] == "high":
        agent_nelly.persist_error_lesson(
            scenario=f"High-severity incident in {incident['environment']}: {incident['triggered_by']}",
            lesson="Investigate root cause and apply fix before next deployment"
        )
```

## Usage Example

### Realtime Monitoring

```bash
$ claude deploy monitor --realtime

[2026-08-25 10:30:00] Starting health monitoring for prod (version 0.2.0)
[2026-08-25 10:30:00] Health: healthy ✓ (service_status✓ version✓ error_rate✓ performance✓)
[2026-08-25 10:30:10] Health: healthy ✓
[2026-08-25 10:30:20] Health: degraded ⚠ (error_rate: 2.5% > 1% SLA)
[2026-08-25 10:30:30] 🚨 Incident detected: Error rate spike (HIGH severity)
[2026-08-25 10:30:35] Searching incident history...
[2026-08-25 10:30:36] Found: incident-2026-08-20-003
                       - Title: Payment service timeout
                       - Resolution: Increased database connection pool
                       - Lesson: Check database capacity before deployment
[2026-08-25 10:30:40] Escalating to on-call
[2026-08-25 10:30:45] Alert sent to Slack: #incidents
[2026-08-25 10:31:00] Health: degraded ⚠ (error_rate: 8% > 1% SLA)
[2026-08-25 10:31:15] Recommendation: Rollback to 0.1.0 or debug error cause
[2026-08-25 10:31:20] Incident details persisted to agent-nelly
```

### Incident Reporting

```bash
$ claude deploy incident "Payment timeout in prod" --severity high

🚨 High-severity incident reported: Payment timeout in prod
[Searching history...]
Found 2 similar prior incidents:
  1. incident-2026-08-20-003 (Payment service timeout)
     - Resolution: Increased database connection pool
  2. incident-2026-07-15-001 (API latency spike)
     - Resolution: Scaled additional worker nodes

[Escalating to on-call team]
Alert sent to on-call @ Slack
Incident details persisted for cross-session context
```

## Testing

High-risk slice — test-first approach recommended.

See `tests/e2e/monitoring.test.js` for:
1. Healthy deployment (all checks pass, no incident)
2. Service down (service_status fails, high-severity incident)
3. Error rate spike (error_rate fails, high-severity incident with prior pattern)
4. Performance degradation (performance check fails, medium-severity incident)
5. Version inconsistency (version_consistency fails, medium-severity incident)
6. Pattern surfacing (similar prior incident retrieved and displayed)
7. Escalation routing (severity routes to correct handler)
8. Memory persistence (incident persisted to agent-nelly, retrievable next session)

Fixtures:
- Healthy health check results
- Failed service check
- Error rate spike scenarios
- Performance SLA breaches
- Version mismatch scenarios
- Incident history with similar patterns
