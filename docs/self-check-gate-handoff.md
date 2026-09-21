# Handoff: Self-Check Gate Real Eval-Results (Follow-Up)

## Status

The Plugin/Skill Creator & Validator feature is **complete** (v0.1.9). All 18 `tasks.md` phases
(1a through 10d) are landed and released, and this plugin now passes its own validator:
`validate_plugin.validate('.')` reports `success: true`, with one remaining by-design residual
(the best-practice-doc check's skip notice, pending a real `scripts/refresh_docs.py` run in an
environment with network access).

## What's Left

The self-check gate itself (Phase 8: `compute_skill_git_hash`, `check_self_check_gate`,
`run_self_check_gate`, `populate_self_check_gate_section` in `scripts/validate_plugin.py`, wired
into `bump_version.py --self-check`, `scripts/validate_plugin.py --self-check`, and
`/plugin-validate --self-check`) is fully implemented and tested (14/14 unit tests in
`tests/scripts/test_validate_plugin_self_check_gate.py` and
`tests/skills/test_bump_version_self_check_gate.py`).

It currently and *correctly* blocks for all three of this plugin's own skills
(`release-planner`, `deployment-orchestrator`, `monitoring`), because no real
`skills/release-planner/eval-results/<skill>.json` files exist yet. This was never faked --
the gate's logic is trustworthy; only the real data behind it is missing.

## What "Done" Looks Like

For each of the 3 skills, `skills/release-planner/eval-results/<skill>.json` needs to exist with:

```json
{
  "skill_name": "<skill>",
  "git_hash": "<sha256 from compute_skill_git_hash(repo_root, skill_name)>",
  "summary": {"passed": N, "failed": 0, "total": N, "pass_rate": 1.0}
}
```

`git_hash` and `summary.pass_rate` are the two fields the gate actually reads; other fields
(`skill_name`, `passed`/`failed`/`total`) are for human readability and match
`anthropic-skills:skill-creator`'s own `grading.json`/`benchmark.json` summary shape.

## How To Get There

1. **Author `evals/evals.json`** for each skill -- prompt / expected_output / expectations
   scenarios. See `anthropic-skills:skill-creator`'s own `evals.json` schema (its
   `references/schemas.md`) for the exact shape. This is real authoring work: think through what
   a good eval scenario for "bump a version," "decide go/no-go on a deployment," or "classify and
   route an incident" actually looks like -- not boilerplate.
2. **Run skill-creator's eval mode** against each skill. This executes real model calls per
   scenario: once to run the skill against the prompt, once (via skill-creator's `grader` agent)
   to grade the transcript against the stated expectations.
3. **Compute the git hash** via `scripts.validate_plugin.compute_skill_git_hash(repo_root,
   skill_name)` and write `eval-results/<skill>.json` in the schema above, using the grading run's
   actual pass/fail counts.
4. **Confirm the gate passes**: `python3 skills/release-planner/bump_version.py <version>
   --self-check` should print `✓ Self-check gate passed` for all three skills.

## Cost/Shape Estimate

Roughly `3 skills x (a handful of eval scenarios each) x 2 model calls per scenario (execute +
grade)`. This is a moderate, real amount of model usage and wall-clock time -- not a quick script
run. Expect the first pass to surface real gaps in the skills' own instructions (that's the
eval's job); getting to a genuine 100% pass rate may take iteration on the skills themselves, not
just recording whatever score comes back first.

## Where Things Live

- **Gate logic**: `scripts/validate_plugin.py` -- `compute_skill_git_hash`,
  `check_self_check_gate`, `run_self_check_gate`, `populate_self_check_gate_section`.
- **CLI wiring**: `skills/release-planner/bump_version.py` (`--self-check`),
  `scripts/validate_plugin.py`'s `main()` (`--self-check`), `commands/plugin-validate.md`.
- **Tests**: `tests/scripts/test_validate_plugin_self_check_gate.py`,
  `tests/skills/test_bump_version_self_check_gate.py`.
- **Eval-results storage** (centralized for all 3 skills, by design):
  `skills/release-planner/eval-results/` -- this directory doesn't exist yet; it's created when
  the first real eval-results file is written.

## Recommended First Step

Start with `release-planner` alone as a proof of concept -- it's the simplest of the three
skills -- before committing to all three.

## Update (2026-09-21): PoC In Progress, Handed Off Mid-Execution

An interactive session started the `release-planner` PoC and got partway through before crashing
twice on the execution step. Status:

**Done:**
- `skills/release-planner/evals/evals.json` is authored -- 5 real scenarios, not boilerplate:
  1. `valid-version-bump` -- CHANGELOG has real `## [Unreleased]` content; expects a clean bump.
  2. `missing-unreleased-section` -- no `## [Unreleased]` heading at all; expects the agent to
     refuse and tell the user to add entries first, per the skill's own "When NOT to Use" section
     -- not silently invent entries or bump anyway.
  3. `invalid-semver` -- version `"1.2"` (not X.Y.Z); expects the agent to reject it and ask for a
     corrected version rather than guessing a patch segment.
  4. `plugin-json-write-failure` -- `.claude-plugin/plugin.json` chmod'd to 444 so the CHANGELOG
     write succeeds but the plugin.json write fails mid-operation; expects the agent to surface
     the specific write failure and flag the resulting lockstep mismatch rather than claim success
     or silently fix permissions itself.
  5. `self-check-blocked` -- no `eval-results/` directory yet; expects the agent to actually run
     `--self-check`, report it as blocked, name `release-planner` as a blocking skill, and *not*
     bump the version anyway.

**Not done:** actually executing these 5 scenarios (skill-creator's with-skill executor pattern:
one subagent per scenario, running for real in an isolated sandbox), grading each against its
`expectations` (a separate grader subagent per `agents/grader.md`, so grading stays independent of
the executor's own account of what happened), computing the git hash, and writing
`skills/release-planner/eval-results/release-planner.json`. The self-check gate for
`release-planner` is therefore still correctly BLOCKED (missing eval-results) -- this update did
**not** fake or shortcut that file into existence.

**Why it stalled:** spawning all 5 executor subagents in parallel in one interactive turn (each
doing real multi-step Bash-driven work in its own sandbox) crashed the session twice before any
executor produced output. Prefer running the 5 scenarios sequentially, or in smaller batches, in
whatever session picks this up next -- especially a cloud/background session, which tolerates
longer-running multi-agent work better than an interactive one.

### Sandbox fixture setup (already scripted once, reusable as-is)

```bash
REPO=/path/to/deployment-ops-plugin
WS=<scratch-dir>/release-planner-workspace/iteration-1
for name in valid-version-bump missing-unreleased-section invalid-semver plugin-json-write-failure self-check-blocked; do
  mkdir -p "$WS/$name/sandbox"
  rsync -a --exclude='.git' --exclude='skills/release-planner/evals' --exclude='skills/release-planner/eval-results' "$REPO/" "$WS/$name/sandbox/"
done
# valid-version-bump / invalid-semver / plugin-json-write-failure sandboxes:
#   give CHANGELOG.md a real "## [Unreleased]" entry (it's empty in the real repo right now)
# missing-unreleased-section sandbox:
#   strip the "## [Unreleased]" heading and blank line entirely
# plugin-json-write-failure sandbox:
#   chmod 444 .claude-plugin/plugin.json (only in that one sandbox)
# self-check-blocked sandbox:
#   leave as-is -- no skills/release-planner/eval-results/ directory should exist
```

### Remaining steps, in order

1. Build the 5 sandboxes above (or reuse `skills/release-planner/evals/evals.json` prompts against
   fresh ones).
2. Per scenario: spawn one executor subagent with the scenario's `prompt` from `evals.json`,
   pointed at that scenario's sandboxed `skills/release-planner/SKILL.md`, real Bash tool use only
   (no simulated output). Save a transcript (commands run + real output + the agent's final reply)
   and the resulting CHANGELOG.md/plugin.json state.
3. Per scenario: spawn a *separate* grader subagent with only the transcript, final file state,
   and that scenario's `expectations` list (not the executor's reasoning) -- grade each expectation
   pass/fail with evidence, per `anthropic-skills:skill-creator`'s `agents/grader.md` pattern.
4. If grading surfaces a real gap in `skills/release-planner/SKILL.md`'s own instructions (e.g. the
   skill doesn't actually tell the agent what to do on a write failure), fix the skill first. Don't
   record a passing score that isn't earned.
5. Compute the hash:
   `python3 -c "from scripts import validate_plugin; print(validate_plugin.compute_skill_git_hash('.', 'release-planner'))"`.
6. Write `skills/release-planner/eval-results/release-planner.json`:
   `{"skill_name": "release-planner", "git_hash": "<hash>", "summary": {"passed": N, "failed": 0, "total": N, "pass_rate": 1.0}}`
   using the grading run's actual pass/fail counts (`N` = 5 if every scenario's expectations all
   passed; iterate on the skill and re-grade instead of rounding up).
7. Confirm: `python3 skills/release-planner/bump_version.py <version> --self-check` prints
   `release-planner: OK` (the other two skills, `deployment-orchestrator` and `monitoring`, will
   still correctly block -- that's expected and out of scope for this PoC).
8. `pytest tests/ -q` must stay green.
9. CUPS it for real: update CHANGELOG's `[Unreleased]`, `bump_version.py <version>`, commit, push,
   `claude plugin update deployment-ops-plugin@renfordn-plugins`, clear the stale cached version
   under `~/.claude/plugins/cache/renfordn-plugins/deployment-ops-plugin/<old-version>`.
