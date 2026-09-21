---
name: bad-style-agent
description: Checks monitoring dashboards for anomalies and reports on them.
model: sonnet
color: yellow
tools: ["Read"]
---

Check the monitoring dashboards for the configured services. Look at error rates, latency
percentiles, and saturation metrics over the last hour. If any metric is outside its normal
range, write a short report describing what looks off and which service it affects. If nothing
looks unusual, say so.

Steps:
1. Pull the current metrics for each monitored service.
2. Compare each metric against its historical baseline.
3. Note any metric that deviates meaningfully from baseline.
4. Write up the findings in a short report.

This fixture agent's `description` deliberately skips the imperative "Use this agent when..."
trigger-phrase convention (and the body skips an explicit expert-persona statement) documented in
this plugin's vendored `agents/agent-creator.md` and `agents/skill-reviewer.md` -- the
"best-practice-doc deviation" defect exercised by Phase 6c's best-practice-doc conformance loop.
It otherwise reads as a plausible, well-formed agent so this one deviation is the only thing
under test.
