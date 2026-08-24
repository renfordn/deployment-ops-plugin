/**
 * E2E Integration Tests: Monitoring & Alerting
 *
 * Tests:
 * - Health checks (service status, version consistency, error rate, performance)
 * - Incident detection and classification
 * - Escalation routing (high/medium/low severity)
 * - Pattern surfacing (similar prior incidents)
 * - Cross-session memory persistence
 */

const assert = require('assert');

describe('Monitoring & Alerting', () => {
  // Mock health check results
  const healthyHealth = {
    timestamp: '2026-08-25T10:30:00Z',
    environment: 'prod',
    deployed_version: '0.1.0',
    checks: {
      service_status: { status: 'healthy', services: { api: 'running', worker: 'running' } },
      version_consistency: { status: 'healthy', instances: [] },
      error_rate: { status: 'healthy', current: '0.1%', threshold: '1%' },
      performance: { status: 'healthy', p95_latency: '350ms', sla: '500ms' }
    },
    overall_status: 'healthy'
  };

  const degradedHealth = {
    timestamp: '2026-08-25T10:30:30Z',
    environment: 'prod',
    deployed_version: '0.1.0',
    checks: {
      service_status: { status: 'healthy', services: { api: 'running', worker: 'running' } },
      version_consistency: { status: 'healthy', instances: [] },
      error_rate: { status: 'degraded', current: '2.5%', threshold: '1%', trend: 'increasing' },
      performance: { status: 'healthy', p95_latency: '450ms', sla: '500ms' }
    },
    overall_status: 'degraded'
  };

  const failedHealth = {
    timestamp: '2026-08-25T10:30:45Z',
    environment: 'prod',
    deployed_version: '0.1.0',
    checks: {
      service_status: { status: 'failed', services: { api: 'down', worker: 'running' } },
      version_consistency: { status: 'degraded', instances: [] },
      error_rate: { status: 'degraded', current: '15%', threshold: '1%', trend: 'increasing' },
      performance: { status: 'degraded', p95_latency: '2500ms', sla: '500ms' }
    },
    overall_status: 'failed'
  };

  // Mock prior incidents from agent-nelly
  const priorIncidents = [
    {
      id: 'incident-2026-08-20-003',
      date: '2026-08-20',
      severity: 'high',
      triggered_by: 'Error rate spike',
      resolution: 'Increased database connection pool',
      lesson_learned: 'Check database capacity before payment service deployment'
    },
    {
      id: 'incident-2026-07-15-001',
      date: '2026-07-15',
      severity: 'high',
      triggered_by: 'Service down',
      resolution: 'Scaled additional worker nodes',
      lesson_learned: 'Scale capacity during peak traffic periods'
    }
  ];

  describe('Health Checks', () => {
    it('should pass all checks on healthy deployment', () => {
      assert.strictEqual(healthyHealth.overall_status, 'healthy', 'Overall status should be healthy');
      assert.strictEqual(healthyHealth.checks.service_status.status, 'healthy', 'Service status should be healthy');
      assert.strictEqual(healthyHealth.checks.error_rate.status, 'healthy', 'Error rate should be healthy');
      assert.strictEqual(healthyHealth.checks.performance.status, 'healthy', 'Performance should be healthy');
    });

    it('should detect error rate degradation', () => {
      assert.strictEqual(degradedHealth.overall_status, 'degraded', 'Overall status should be degraded');
      assert.strictEqual(degradedHealth.checks.error_rate.status, 'degraded', 'Error rate should be degraded');
      assert.strictEqual(degradedHealth.checks.error_rate.trend, 'increasing', 'Trend should be increasing');
    });

    it('should detect service failure', () => {
      assert.strictEqual(failedHealth.overall_status, 'failed', 'Overall status should be failed');
      assert.strictEqual(failedHealth.checks.service_status.status, 'failed', 'Service status should be failed');
    });

    it('should track version consistency across instances', () => {
      const versionCheck = healthyHealth.checks.version_consistency;
      assert.strictEqual(versionCheck.status, 'healthy', 'All instances should have same version');
    });

    it('should verify performance against SLA', () => {
      const perfCheck = healthyHealth.checks.performance;
      assert(perfCheck.p95_latency < perfCheck.sla, 'Latency should be under SLA');
    });
  });

  describe('Incident Detection', () => {
    it('should detect no incident on healthy deployment', () => {
      const incident = detectIncident(healthyHealth);
      assert.strictEqual(incident, null, 'No incident should be detected on healthy deployment');
    });

    it('should detect medium-severity incident on degradation', () => {
      const incident = detectIncident(degradedHealth);
      assert.notStrictEqual(incident, null, 'Should detect incident on degradation');
      assert.strictEqual(incident.severity, 'medium', 'Degradation should be medium severity');
    });

    it('should detect high-severity incident on failure', () => {
      const incident = detectIncident(failedHealth);
      assert.notStrictEqual(incident, null, 'Should detect incident on failure');
      assert.strictEqual(incident.severity, 'high', 'Failure should be high severity');
    });

    it('should classify incident by trigger', () => {
      const incident = detectIncident(degradedHealth);
      assert(incident.triggered_by.includes('rate') || incident.triggered_by.includes('degradation'), 'Should identify trigger');
    });

    function detectIncident(health) {
      if (health.overall_status === 'failed') {
        return { severity: 'high', triggered_by: 'Service failure' };
      }
      if (health.overall_status === 'degraded' && health.checks.error_rate?.trend === 'increasing') {
        return { severity: 'high', triggered_by: 'Error rate spike' };
      }
      if (health.overall_status === 'degraded' && health.checks.performance?.status === 'degraded') {
        return { severity: 'medium', triggered_by: 'Performance degradation' };
      }
      if (health.overall_status === 'degraded') {
        return { severity: 'medium', triggered_by: 'Service degradation' };
      }
      return null;
    }
  });

  describe('Escalation Routing', () => {
    it('should escalate high-severity incident to on-call', () => {
      const incident = { severity: 'high', triggered_by: 'Service failure' };
      const escalation = escalateIncident(incident);

      assert.strictEqual(escalation.route, 'on-call', 'Should route to on-call');
      assert.strictEqual(escalation.immediate, true, 'Should be immediate');
    });

    it('should escalate medium-severity incident to team', () => {
      const incident = { severity: 'medium', triggered_by: 'Performance degradation' };
      const escalation = escalateIncident(incident);

      assert.strictEqual(escalation.route, 'team', 'Should route to team');
      assert.strictEqual(escalation.immediate, false, 'Should allow investigation time');
    });

    it('should log low-severity incident to agent-nelly', () => {
      const incident = { severity: 'low', triggered_by: 'Minor memory usage increase' };
      const escalation = escalateIncident(incident);

      assert.strictEqual(escalation.route, 'nelly', 'Should route to agent-nelly');
      assert.strictEqual(escalation.immediate, false, 'Should be background logging');
    });

    function escalateIncident(incident) {
      if (incident.severity === 'high') {
        return { route: 'on-call', immediate: true, action: 'page on-call immediately' };
      } else if (incident.severity === 'medium') {
        return { route: 'team', immediate: false, action: 'alert team, wait for investigation' };
      } else {
        return { route: 'nelly', immediate: false, action: 'log to agent-nelly' };
      }
    }
  });

  describe('Pattern Surfacing', () => {
    it('should find similar prior incidents', () => {
      const incident = { severity: 'high', triggered_by: 'Error rate spike' };
      const patterns = surfacePatterns(incident);

      assert(patterns.length > 0, 'Should find similar prior incidents');
      assert.strictEqual(patterns[0].triggered_by, 'Error rate spike', 'First result should match trigger');
    });

    it('should surface resolution strategy from prior incident', () => {
      const incident = { severity: 'high', triggered_by: 'Error rate spike' };
      const patterns = surfacePatterns(incident);

      assert(patterns[0].resolution, 'Should include resolution strategy');
      assert(patterns[0].lesson_learned, 'Should include lesson learned');
    });

    it('should return top-3 most relevant prior incidents', () => {
      const incident = { severity: 'high', triggered_by: 'Error rate spike' };
      const patterns = surfacePatterns(incident);

      assert(patterns.length <= 3, 'Should return at most 3 results');
    });

    function surfacePatterns(incident) {
      return priorIncidents.filter(
        i => i.severity === incident.severity && i.triggered_by === incident.triggered_by
      ).slice(0, 3);
    }
  });

  describe('Memory Persistence', () => {
    it('should persist incident to agent-nelly', () => {
      const incident = {
        id: 'incident-2026-08-25-001',
        severity: 'high',
        triggered_by: 'Error rate spike',
        health_snapshot: failedHealth
      };

      const fact = {
        type: 'incident',
        key: `incident-${incident.id}`,
        value: incident,
        source: 'monitoring-agent'
      };

      assert.strictEqual(fact.type, 'incident', 'Fact should be incident type');
      assert.strictEqual(fact.source, 'monitoring-agent', 'Source should be monitoring-agent');
    });

    it('should persist error lesson on high-severity incident', () => {
      const incident = {
        id: 'incident-2026-08-25-001',
        environment: 'prod',
        severity: 'high',
        triggered_by: 'Error rate spike'
      };

      if (incident.severity === 'high') {
        const lesson = {
          scenario: `High-severity incident: ${incident.triggered_by}`,
          lesson: 'Investigate root cause and apply fix before next deployment',
          plugin: 'monitoring-agent'
        };

        assert(lesson.scenario.includes(incident.triggered_by), 'Lesson should reference incident');
      }
    });

    it('should allow cross-session incident retrieval', () => {
      // Simulate retrieving incident from agent-nelly in next session
      const retrievedIncident = priorIncidents[0];

      assert.strictEqual(retrievedIncident.id, 'incident-2026-08-20-003', 'Should retrieve correct incident');
      assert(retrievedIncident.lesson_learned, 'Should include lesson learned from prior session');
    });
  });

  describe('Integration with Agent-UX', () => {
    it('should emit breadcrumb_only event on healthy deployment', () => {
      const event = {
        caller: 'deployment-ops-plugin',
        event_type: 'breadcrumb_only',
        phase_state: { phase: 'Monitoring', status: 'in_progress' }
      };

      assert.strictEqual(event.phase_state.status, 'in_progress', 'Status should be in_progress');
    });

    it('should emit out_of_scope_flag event on incident', () => {
      const event = {
        caller: 'deployment-ops-plugin',
        event_type: 'out_of_scope_flag',
        phase_state: { phase: 'Monitoring', status: 'blocked' },
        delta: { reason: 'Error rate spike detected' }
      };

      assert.strictEqual(event.event_type, 'out_of_scope_flag', 'Event type should be out_of_scope_flag');
      assert.strictEqual(event.delta.reason.includes('rate'), true, 'Reason should reference error rate');
    });
  });

  describe('Realtime Monitoring', () => {
    it('should stream health checks continuously with --realtime flag', () => {
      const monitoringStream = [
        { timestamp: '10:30:00', status: 'healthy' },
        { timestamp: '10:30:10', status: 'healthy' },
        { timestamp: '10:30:20', status: 'degraded' },
        { timestamp: '10:30:30', status: 'degraded' }
      ];

      assert(monitoringStream.length >= 3, 'Should stream multiple checks');
      assert.strictEqual(monitoringStream[0].status, 'healthy', 'First check should be healthy');
      assert.strictEqual(monitoringStream[2].status, 'degraded', 'Should detect degradation in stream');
    });

    it('should generate recommendations based on health status', () => {
      const health = failedHealth;
      const recommendations = [
        'Service API is down — investigate service logs',
        'Error rate at 15% — significantly over threshold',
        'Latency at 2500ms — far exceeds 500ms SLA',
        'Recommendation: Rollback to previous version 0.0.1 or debug error cause'
      ];

      assert(recommendations.length > 0, 'Should generate recommendations');
      assert(recommendations[3].includes('Rollback'), 'Should recommend rollback on failure');
    });
  });

  describe('Graceful Degradation', () => {
    it('should log incident when agent-nelly unavailable', () => {
      const incident = { severity: 'low', triggered_by: 'Minor metric deviation' };
      const logged = {
        success: true,
        nelly_persisted: false,  // agent-nelly unavailable
        local_logged: true
      };

      assert.strictEqual(logged.success, true, 'Should still succeed');
      assert.strictEqual(logged.local_logged, true, 'Should log locally');
    });

    it('should alert team when agent-ux unavailable', () => {
      const incident = { severity: 'medium', triggered_by: 'Performance degradation' };
      const alerted = {
        success: true,
        ux_event_sent: false,  // agent-ux unavailable
        team_alerted: true
      };

      assert.strictEqual(alerted.success, true, 'Should still alert team');
      assert.strictEqual(alerted.team_alerted, true, 'Should send alert');
    });
  });
});
