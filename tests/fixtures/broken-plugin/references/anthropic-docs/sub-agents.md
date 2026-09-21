fetched_at: 2026-01-01T00:00:00+00:00
# Subagents (stubbed excerpt for fixture testing)

This is a minimal, hand-written excerpt of agent-authoring best-practice guidance, trimmed for
deterministic test fixtures. It is not a full snapshot of the live Anthropic documentation; see
`scripts/refresh_docs.py` for the real fetch mechanism.

## Persona and role

Every agent should open with a clear persona and role statement describing who the agent is and
what its scope of responsibility is, before any procedural instructions.

## Description trigger phrasing

An agent's `description` field should follow "Use this agent when..." trigger-phrase
conventions, so the invoking model can reliably decide when to delegate to it based on concrete
example scenarios.

## Tool scoping

Agents should declare only the tools they need to do their job (least privilege). Do not grant
broad or unrelated tool access; an agent's declared tools should map directly to the actions
described in its instructions.

## Examples

Include at least one concrete example showing a representative user request, the reasoning for
delegating to this agent, and a sample invocation, so reviewers can verify the agent's scope
without executing it.
