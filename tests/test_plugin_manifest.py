"""
Phase 1b (tasks.md): plugin.json `agents` array registers all vendored agents.

Phase 1a vendored agents/plugin-validator.md, agents/skill-reviewer.md, and
agents/agent-creator.md. This confirms the manifest's `agents` array lists
them alongside the pre-existing deployment-agent and monitoring-agent.
"""

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")

EXPECTED_AGENTS = {
    "deployment-agent",
    "monitoring-agent",
    "plugin-validator",
    "skill-reviewer",
    "agent-creator",
}


def test_manifest_agents_array_lists_all_vendored_agents():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert set(manifest.get("agents", [])) == EXPECTED_AGENTS, (
        f"expected manifest agents array to list {sorted(EXPECTED_AGENTS)}, "
        f"got {manifest.get('agents')}"
    )
