---
description: Validate a Claude Code plugin for release readiness -- structural correctness, agent-context checks, dangling references, and security/sanitization, or (with --self-check) this plugin's own skill-eval gate.
argument-hint: "[plugin-path] [--self-check]"
allowed-tools: [Bash]
---

Run this plugin's release-readiness validator against the target plugin.

1. If no plugin path was given in `$ARGUMENTS`, ask the user which plugin directory to validate.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py $ARGUMENTS` and capture its JSON
   report and exit code.
   - Without `--self-check`, this runs the full validator (`validate_plugin.validate`): the
     Structural, Per-Skill Quality, Per-Agent Plugin-Context Findings, Dangling References, and
     Security/Sanitization sections.
   - With `--self-check`, this instead runs this plugin's own self-check gate
     (`validate_plugin.run_self_check_gate`) against its three built-in skills
     (release-planner, deployment-orchestrator, monitoring) and reports the "Self-Check Gate"
     section instead.
3. Present the JSON report to the user as a readable summary, grouped by section and severity
   (critical/major/minor), with each finding's file and message. Lead with a one-line verdict
   (ready to release / not ready) based on the script's exit code -- a non-zero exit means the
   plugin is not ready to release, and the summary should say why.
