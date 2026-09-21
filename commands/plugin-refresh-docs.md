---
description: Refresh this plugin's local snapshot of Anthropic's agent-authoring reference docs, used by the best-practice-doc validator check.
allowed-tools: [Bash]
---

Refresh this plugin's `references/anthropic-docs/` snapshot.

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/refresh_docs.py`.
2. This is a manual, explicit refresh only -- the validator itself never fetches these docs live
   (see `scripts/validate_plugin.py`'s module docstring). Report which docs refreshed
   successfully and which, if any, failed to fetch, per the script's output.
