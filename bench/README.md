# `bench/` — the harness

The protocol lives in [`../docs/benchmark.md`](../docs/benchmark.md). This is what runs it.

Everything here is Python 3 standard library and bash, like the rest of the kit. Nothing reads
the agent's own account of what it did: every number comes from running something.

```
bench/
├── run.py            orchestrates arm × task × seed into fresh working copies
├── score.py          scores finished runs — hidden suite, regressions, mutation
├── mutation.py       the mutation scorer (the anti-gaming metric for test quality)
├── analyze.py        cluster bootstrap, paired H2 test, dose–response, frontier SVG
├── selftest.sh       proves the scorer still discriminates. Run it before every campaign
├── PREREGISTRATION.md   fill in and commit BEFORE the first run
├── arms/             one JSON per arm + the protocol prompt each arm receives
├── tasks/            one directory per task (fixture, prompt, hidden suite, verify.sh)
└── results/          run output — gitignored until you deliberately publish a campaign
```

## The three commands

```bash
export BENCH_MODEL_ID='<the exact model id, pinned>'
export BENCH_AGENT_CMD='claude -p "$(cat {prompt_file})" --output-format json --permission-mode acceptEdits'

bench/selftest.sh                                                  # first, always
bench/run.py --arms A0_baseline,A1_baseline_rich,A2_doe --seeds 5  # A2 before A3
bench/run.py --arms A3_baseline_matched --seeds 5                  # matched to A2's spend
bench/score.py bench/results/
bench/analyze.py bench/results/ --report bench/results/REPORT.md
```

`--dry-run` prints every command that would be issued and invokes nothing. Use it whenever you
touch an arm.

**Order matters.** `A3_baseline_matched` caps each run at what `A2_doe` actually spent *on that
task and seed*, so A2 must have run first. Without a reference run, A3 skips the cell loudly
rather than silently falling back to an average — matching on the average reintroduces task
difficulty as a confounder, which is the mistake the arm exists to avoid.

## The agent command

`--agent-cmd` (or `$BENCH_AGENT_CMD`) is a template, so the harness does not privilege one CLI.
Placeholders: `{prompt_file}`, `{workdir}`, `{seed}`, `{token_budget}`.

Token accounting is read out of the agent's JSON output by walking it for the usual keys
(`input_tokens`, `output_tokens`, cache reads, `total_cost_usd`). If your CLI names them
something else, teach `find_usage()` about it — a missing token count is recorded as **missing**,
never as zero, because a zero would drag the whole cost axis toward the origin and flatter every
arm that failed to report.

## Adding a task

```
tasks/T0N_short_name/
├── task.json      id · tier · stack · provenance · commands · mutation + regression config
├── prompt.md      the request, exactly as a developer would type it
├── fixture/       a real repo state: source, a GREEN pre-existing suite, config
├── hidden/        the acceptance suite. Never copied into the agent's workdir
└── verify.sh      copies hidden/ in, runs it, exits non-zero on failure, cleans up
```

Before the task counts:

1. **The fixture suite is green.** Run it.
2. **A reference solution passes `verify.sh`, and a plausible wrong one fails it.** If you
   cannot write the wrong one, the hidden suite is not discriminating and the task will score
   every arm the same.
3. **Hidden tests only test behaviour stated in `prompt.md`.** A hidden test encoding an
   unstated preference measures compliance with your taste, not correctness.
4. **Pilot it at `A0_baseline`.** 5/5 or 0/5 means no signal — retune or drop it.
5. **Record provenance** in `task.json`. Public-repo fixtures may be memorised, and that has
   to appear in the write-up.

The shipped task, `T01_volume_discounts`, is deliberately small and discriminates on three
things a one-shot run usually gets wrong: inclusive tier boundaries, half-away-from-zero
rounding (Python's `round()` is banker's rounding), and per-line rather than per-order tiering.

**It is also stdlib Python, which the kit has no installer for**, so `A2_doe`'s setup step is
skipped and recorded as skipped in `meta.json`. It exercises the harness end to end; it does
not exercise the guard. Real campaign tasks should use the `web-ts` or `flutter` stacks so the
kit is genuinely installed and the guard genuinely armed.

## Why `selftest.sh` exists

The scorer shares the guard's failure mode: when it breaks, nothing turns red — it just stops
discriminating, and you publish a beautiful, wrong benchmark. So it is tested in both
directions, on a correct run and on a plausibly wrong one:

| it must catch | how |
|---|---|
| an assertion-free suite scoring like a real one | mutation score, asserting vs smoke-test suite |
| a wrong implementation passing acceptance | reference vs a rounding-and-guard bug |
| a dropped behaviour hiding behind edited tests | the fixture suite is **restored from the task**, never read from the workdir |
| a pre-existing test quietly edited | content hashes against the fixture |

Run it before every campaign, and after touching anything in here.
