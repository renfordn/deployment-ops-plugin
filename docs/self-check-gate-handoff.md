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
