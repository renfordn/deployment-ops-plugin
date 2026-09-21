"""
Phase 1b (tasks.md): plugin.json `agents` array registers all vendored agents.

Phase 1a vendored agents/plugin-validator.md, agents/skill-reviewer.md, and
agents/agent-creator.md. This confirms the manifest's `agents` array lists
them alongside the pre-existing deployment-agent and monitoring-agent.

Entries are path-shaped (`./agents/<name>.md`), not bare names -- confirmed
empirically against `claude plugin validate` (a bare name like
"deployment-agent" doesn't resolve; see this plugin's own remediation pass,
which also fixed the equivalent `skills` array and `author` field so this
plugin now passes its own validator).
"""

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")

EXPECTED_AGENT_NAMES = {
    "deployment-agent",
    "monitoring-agent",
    "plugin-validator",
    "skill-reviewer",
    "agent-creator",
}


def test_manifest_agents_array_lists_all_vendored_agents():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    agents = manifest.get("agents", [])
    actual_names = {os.path.splitext(os.path.basename(entry))[0] for entry in agents}
    assert actual_names == EXPECTED_AGENT_NAMES, (
        f"expected manifest agents array to list {sorted(EXPECTED_AGENT_NAMES)}, "
        f"got {agents}"
    )

    for entry in agents:
        relative = entry[2:] if entry.startswith("./") else entry
        assert os.path.isfile(os.path.join(REPO_ROOT, relative)), (
            f"plugin.json lists agent `{entry}`, which doesn't resolve to a real file"
        )
