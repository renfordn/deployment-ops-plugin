---
description: Scaffold a new agent file for a Claude Code plugin from a name and description, using agent-creator's Create mode.
argument-hint: "[agent-name] [agent-description]"
allowed-tools: [Bash]
---

Scaffold a new agent named `$0` for the plugin the user is currently working on, with `$1` as
its description.

1. Determine the target plugin's `agents/` directory (the plugin in the current working
   directory, or ask the user if it's ambiguous).
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/create_agent.py <target-agents-dir> "$0" "$1"`,
   which implements `agents/agent-creator.md`'s Create mode
   (`create_agent(agents_dir, name, description) -> CreateResult`), including its
   name-collision refusal.
3. If the script reports an error (e.g. an agent with that name already exists), relay it to the
   user rather than overwriting anything.
4. On success, tell the user the new agent file's path and suggest running `/plugin-validate` on
   the plugin to confirm the new agent passes all checks.
