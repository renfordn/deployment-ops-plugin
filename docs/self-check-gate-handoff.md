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

## Update (2026-09-21): release-planner PoC Complete

A follow-up cloud session ran all 5 remaining steps sequentially (one executor subagent, then one
grader subagent, per scenario -- avoiding the earlier session's parallel-executor crash) and closed
this out for `release-planner`:

- All 5 sandboxes were rebuilt fresh from the recipe above and executed for real, one at a time.
- **Real gap found and fixed in the fixture itself, not the skill**: the `plugin-json-write-failure`
  sandbox's `chmod 444 .claude-plugin/plugin.json` did not actually block the write, because this
  sandbox executes as `root`, and root bypasses standard Unix permission bits. The first executor
  run correctly discovered and reported this (the bump silently "succeeded"). The fixture was
  corrected to `chattr +i` (filesystem immutable attribute), which reproduces a genuine
  `PermissionError` even for root, and the scenario was rebuilt and re-executed against the
  corrected fixture, this time reproducing and correctly handling the real write failure.
- All 5 scenarios' full expectation sets passed on grading, with each grader independently
  re-verifying file contents in the sandbox rather than trusting the transcript: 26/26 total
  expectations across the 5 scenarios, pass_rate 1.0 in every scenario. No score was rounded up --
  the one real gap found (above) was fixed and re-run, not glossed over.
- `skills/release-planner/eval-results/release-planner.json` written with the computed
  skill-content hash (a SHA-256 over `git ls-files`-tracked bytes, not a `git`-verifiable object
  despite the function's `compute_skill_git_hash` name) and
  `{"passed": 5, "failed": 0, "total": 5, "pass_rate": 1.0}`.
- `python3 skills/release-planner/bump_version.py 0.1.12 --self-check` now prints
  `release-planner: OK`; `deployment-orchestrator` and `monitoring` still correctly report
  `BLOCKED (missing)` -- expected, out of scope for this PoC.
- `pytest tests/ -q`: 81 passed.
- Released as v0.1.12.

**Still outstanding** (same shape as this PoC, now with a working recipe and a corrected
write-failure fixture pattern to reuse): real `evals/evals.json` + eval-results for
`deployment-orchestrator` and `monitoring`.

## Update (2026-09-21): All Three Skills Complete -- Self-Check Gate Fully Passing

A follow-up session finished `deployment-orchestrator` and `monitoring`, closing out this handoff
for all three of the plugin's skills.

Neither skill has a real backing script the way `release-planner` has `bump_version.py` --
`claude deploy <environment>` and `claude deploy monitor`/`claude deploy incident` are documented
decision-logic specifications (go/no-go schema + rollback guard for deployment-orchestrator;
health-check schema + incident severity/escalation thresholds + cross-session pattern surfacing
for monitoring), not executable CLIs, and there's no real infrastructure in this sandbox to
deploy to or monitor. So the eval design differs from `release-planner`'s file-mutation scenarios:
each of the 10 new scenarios (5 per skill, in `skills/deployment-orchestrator/evals/evals.json`
and `skills/monitoring/evals/evals.json`) supplies the raw pre-flight/health-check/metric facts
directly in the prompt, and the executor's job is to correctly apply the skill's documented
schema/thresholds to those given facts -- not to run real commands. This is still "real" work in
the sense that matters for the gate: the executor must actually read the current SKILL.md and
reason correctly over it, and the grader independently re-checks every quoted schema/threshold
claim against the real file rather than trusting the transcript.

Both executors ran all 5 of their scenarios sequentially in one subagent call each (not one
subagent per scenario) since there was no heavy Bash work to isolate -- this was faster and lower
crash-risk than the parallel-executor pattern that failed for `release-planner`, while a separate
grader subagent still graded independently per skill.

Results:
- `deployment-orchestrator`: 5/5 scenarios, 26/26 expectations passed (valid go-decision,
  missing-permissions block, artifact-missing block, health-failure-triggers-rollback,
  rollback-blocked-manual-intervention).
- `monitoring`: 5/5 scenarios, 24/24 expectations passed (healthy report, error-rate-spike
  High-severity incident, latency-spike Medium-severity incident, version-inconsistency detection,
  similar-past-incident cross-session surfacing).
- `skills/release-planner/eval-results/deployment-orchestrator.json` and `.../monitoring.json`
  written with computed skill-content hashes and `{"passed": 5, "failed": 0, "total": 5,
  "pass_rate": 1.0}` each.
- `python3 skills/release-planner/bump_version.py 0.1.13 --self-check` now reports all three
  skills OK: `✓ Self-check gate passed: all skills fresh and at 100% pass rate`.
- `pytest tests/ -q`: 81 passed.
- Released as v0.1.13.

Two non-blocking eval-design notes the graders surfaced (recorded in the relevant scenarios'
`grading.json` `eval_feedback`, not failures): the error-spike scenario's expectations don't check
that `affected_services` is traceable to a service actually named in the prompt (the executor
filled in `["api"]` with no given basis); and the version-inconsistency scenario's expectations
don't verify the executor's correct restraint in *not* fabricating an incident severity for a case
the Incident Detection table has no row for. Worth tightening in a future iteration, not blocking.

## Update (2026-09-21): Gate Hardened Against Fabrication -- Grading Evidence Now Required

A code review of the merged PR (renfordn/deployment-ops-plugin#1) surfaced a real structural gap:
the self-check gate as landed only checked a self-reported `summary.pass_rate` against a content
hash -- it never re-executed any eval scenario, so a hand-edited `eval-results/<skill>.json` with
a matching hash and `pass_rate: 1.0` satisfied the gate regardless of whether any eval was ever
actually run or graded. A second finding: the gate never checked that `summary.total` was
positive, so a degenerate `{"passed": 0, "failed": 0, "total": 0, "pass_rate": 1.0}` record also
passed. A third and fourth finding: this doc's own prose overclaimed -- it said `grading.json`
evidence existed for each scenario (it lived only in an ephemeral scratch workspace, never
committed) and described the content hash as a "real computed git hash" (it is a SHA-256 over
`git ls-files`-tracked bytes, not a `git`-verifiable object).

Fixed in `scripts/validate_plugin.py`:
- `_self_check_one_skill` now rejects `summary.total <= 0` (reason `vacuous`).
- A new `_verify_grading_evidence` check requires a committed
  `skills/release-planner/eval-results/<skill>.grading.json` evidence file: one real grader-agent
  record per scenario defined in that skill's `evals/evals.json`, cross-validated by scenario name
  (every scenario in `evals.json` must be evidenced and vice versa) and required to show a full
  pass per scenario, with the evidenced scenario count required to match `summary.total`. Missing,
  malformed, or inconsistent evidence blocks the gate (`missing-evidence` /
  `evidence-parse-error` / `evidence-mismatch`).
- The three `eval-results/*.grading.json` evidence files were built from this session's actual
  grader-subagent output (consolidated from the scratch workspace where it was originally
  written) and committed for real, so the doc's earlier claim is now true rather than aspirational.
- Doc/`SKILL.md` wording fixed to describe the hash accurately as a skill-content hash, not a git
  object hash.

This still isn't a cryptographic attestation that a real model call happened -- it's a local
file-consistency check, and a sufficiently motivated adversary could still hand-author a
plausible-looking evidence file. What it does close is the trivial one-line forgery this review
demonstrated (editing a single summary object), and it gives a human auditor a concrete,
scenario-by-scenario artifact to spot-check against the real eval prompts. A stronger future
version would have the gate (or CI) actually re-run the skill-creator eval mode live rather than
trust any committed record, self-reported or evidenced.

**Nothing left outstanding from this handoff.** All three skills have real eval-results and the
self-check gate passes cleanly for the whole plugin.

## Update (2026-09-22): Monitoring Eval Gaps Closed

The two non-blocking eval-design gaps the 2026-09-21 update's graders surfaced for `monitoring`
are now closed:

- `error-rate-spike-incident`'s prompt now explicitly attributes the error-rate spike to the
  `api` service (worker/cache stay at baseline), and a new expectation requires
  `affected_services` to name `api` specifically and exclude worker/cache -- previously the
  prompt gave no service at all, so an executor filling in `["api"]` passed the old expectation
  with no basis for that value.
- `version-inconsistency-detection` gained an expectation requiring the agent *not* fabricate an
  Incident object (with a severity) for the version-mismatch condition itself, since SKILL.md's
  Incident Detection thresholds table has no row for version inconsistency -- only a degraded
  health-check finding is warranted.

Re-ran the executor + independent grader pair for all 5 `monitoring` scenarios against the
updated `evals.json` and the real `SKILL.md`: 5/5 scenarios, 26/26 expectations passed.
`skills/release-planner/eval-results/monitoring.json` and `.../monitoring.grading.json` rewritten
with the new content hash and full grading evidence.
`python3 skills/release-planner/bump_version.py <version> --self-check` reports all three skills
`OK` (spot-checked via `validate_plugin._self_check_one_skill` directly, without triggering an
actual version bump). `pytest tests/ -q`: 96 passed (94 prior + 2 new regression tests for the
`validate_plugin.py` historical-qualifier fix below).

Also fixed, in the same session: `scripts/validate_plugin.py`'s Dangling References check
previously still flagged a component named with an explicit historical qualifier immediately
before it (e.g. "the former `artifact-scaffolder` skill") -- PR #3 had documented this as a known
limitation. A new `_SIBLING_HISTORICAL_QUALIFIERS` check now suppresses references preceded
by a qualifier word (former, old, legacy, removed, deprecated, historical, previous, prior,
retired, renamed, defunct, obsolete, sunset, discontinued), while still flagging an unqualified
reference to the same nonexistent name.
