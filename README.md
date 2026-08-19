# DOE Kit — Directive · Oriented · Execution

**Directive-first, test-driven development for coding agents.**
An agent may not touch your code until a spec is written and a human has approved it — and
"done" is an exit code, not a claim.

```
/directive  → interview + spec + Test Contract  (STATE: DRAFT)   [ZERO code]
     ↓  you review and set STATE: APPROVED by hand  ← this unlocks the guard
/execute NN → RED → fix → green gate → the directive is deleted
```

The rule is not written in a prompt and hoped for. A `PreToolUse` hook **mechanically blocks**
every write into your source and test directories until an approved directive exists.

---

## The three problems it fixes

| Problem | What DOE does |
|---|---|
| The agent implements something adjacent to what you asked | The spec is written and human-approved *before* any code |
| "Done!" — based on the agent's own summary | Done = `run.sh` exits 0. The test runner is the only judge |
| A red test tempts the agent to edit the test | The red-test rule, enforced by process and by the directive's test-impact table |

The second one is the expensive one. An agent's confidence is uncorrelated with its
correctness, and the only cheap way to tell them apart is a gate it cannot argue with.

---

## Quick start

```bash
git clone https://github.com/<you>/doe-kit.git /tmp/doe-kit
/tmp/doe-kit/install.sh --stack web-ts /path/to/your/project

cd /path/to/your/project
.doe/execution/directive_guard.py --status   # GUARD: ARMED
.doe/execution/guard_selftest.py             # no false positives, no false negatives
.doe/execution/run.sh                        # your gate — must be green before you start
```

Then just ask your agent to change something. It will be refused, and it will start the
interview instead.

Needs `python3` on `PATH` (standard library only) and `git`. In Claude Code the hook goes live
immediately — the settings file watcher picks it up, no restart — and you can confirm it with
`/hooks`. The skills install project-scoped under `.claude/skills/`, invoked as `/directive`,
`/execute NN`, `/doe-review`, or loaded automatically when your request matches their
description. Full walkthrough: [docs/adoption.md](docs/adoption.md).

Stacks: **`web-ts`** (TypeScript · Vitest · tsc · eslint) · **`flutter`** (Dart · flutter test
· analyze). Adding one is a `run.sh` and a `coverage.sh` — see
[stacks/README.md](stacks/README.md).

The Flutter stack also ships the feature pipeline — design the state, spec it, scaffold it
tests-first, review it, fix what no test can see:

```
riverpod-architect → /directive → [approve] → /execute (scaffold-feature) → /doe-review → /doe-review-fix (fix-style)
```

Those three skills read your token names from `.doe/conventions.json` and **refuse to run
without it**: a style skill that guesses your design system produces fixes that compile and are
wrong, which is worse than no fix because it looks done.

---

## What is in the box

```
core/
├── skills/          directive · execute · review · review-fix · diagnose · delta-check · port-commits
├── templates/       00_FEATURE · 00_BUG · 00_REVIEW directive templates
└── execution/       directive_guard.py · guard_selftest.py     (stack-agnostic)

stacks/
├── web-ts/          run.sh · coverage.sh · coverage-check.mjs + frontend/backend standards
├── flutter/         run.sh · coverage.sh + riverpod-architect · scaffold-feature · fix-style
│                    · test-plan · test-run, driven by .doe/conventions.json
└── shared/          ui-standards · i18n-translator (+ a validator that fails CI)

docs/
├── methodology.md   the three levels, the three flows, the red-test rule
├── workflow.md      a day with DOE: one feature, one bug, one review
├── enforcement.md   the guard, the self-test, CI
├── coverage-gate.md per-file coverage, skip-list, keep-list, the KPI to watch
└── adoption.md      installing it in an existing project, and rolling it out
```

---

## The parts worth stealing even if you skip the rest

**The test-impact table.** Every directive declares which existing tests it is allowed to
change, and each row must map to a declared behaviour change. During execution the agent may
touch *only* those tests. This is what makes "never edit a test to make it pass" mechanical
instead of aspirational.

**Findings classified by testability, not just severity.** `/doe-review` splits findings into
logic-testable (→ a directive with a regression test) and non-testable (→ a direct fix in the
report). A gate that pretends to verify a colour token is a gate nobody believes.

**A logged skip-list.** The coverage gate excludes the view layer — and prints every exclusion
with its reason. An invisible skip-list turns the gate into theatre.

**A self-test for the guard.** The guard is the only component that, when it breaks, turns
nothing red: it just stops protecting. Its regression suite tests both directions — writes
that should be blocked, *and* legitimate work that must never be. A guard that blocks `grep`
gets disabled within the hour, and a disabled guard protects nothing.

**Per-file coverage on changed files only.** A repo at 15% global coverage can adopt this
today. It does not demand a retroactive testing project — it demands that new work arrives
covered.

---

## Honest limits

- **The round-trip is real.** Every change goes through a written spec. For a throwaway
  prototype that is a bad trade.
- **The gate only sees what a unit test can reach.** If your business logic lives inside
  components and route handlers, you will need to move it out first — see
  [adoption.md](docs/adoption.md). This is a feature disguised as a prerequisite.
- **The Bash guard is a heuristic, not a shell parser.** It stops the process being bypassed
  by inattention. Anyone determined to bypass it already has `DOE_BYPASS=1`, which at least is
  explicit.

---

## Origin

Distilled from production use across Flutter apps, Next.js sites and Node backends — including
the bugs that shaped each rule. The comments in `directive_guard.py` about heredoc bodies and
about the self-test that skipped itself are not hypotheticals; they are incident reports.

## License

MIT — see [LICENSE](LICENSE).
