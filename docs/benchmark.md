# Benchmark — does the process pay for its tokens?

The claim under test, as it is usually stated:

> **Spending more tokens produces better test-driven code.**

That sentence cannot be falsified as written, and a benchmark that cannot fail is marketing.
This document turns it into something that can lose.

---

## 0. The thesis, restated so it can be false

Tokens are not a *treatment*. You cannot assign an agent "more tokens" the way you assign a
patient a dose — token count is an **outcome** of the process you ran, jointly caused by the
prompt, the task, and how many times the loop went red. DOE spends more tokens *and* imposes a
structure; the naive experiment cannot tell you which one did the work.

So the claim splits into three hypotheses, each with its own verdict:

| | Hypothesis | Falsified if |
|---|---|---|
| **H1** | *Dose–response.* Within a fixed process, quality rises with the token budget. | Quality is flat (or non-monotone) across budget levels, CI on the slope crosses 0 |
| **H2** | *Structure, not spend.* At a **matched** token budget, DOE beats unstructured prompting. | The DOE − baseline delta at matched budget has a CI containing 0 |
| **H3** | *Saturation.* The marginal quality per extra 10k tokens falls to ~0 past some budget. | Quality keeps climbing linearly across the whole range tested |

**H2 is the interesting one.** If H1 holds and H2 fails, the honest headline is *"tokens buy
quality; DOE is one way to spend them, not a better one"* — which is a real, publishable, and
much less flattering result. Design the experiment so it is allowed to say that.

**Primary endpoint (declare it before running, exactly one):** *resolve rate on the hidden
acceptance suite, pass@1.* Everything else is secondary and gets a multiplicity correction.

---

## 1. Four traps that make this measurement succeed no matter what

**① The agent grades its own homework.** If "quality" means *the tests the agent wrote are
green*, you are measuring the agent's willingness to write easy tests. Every arm scores ~100%.
→ Each task ships a **hidden acceptance suite** the agent never sees, applied after the run.
It is the only source of the primary metric.

**② Difficulty is confounded with spend.** Hard tasks consume more tokens *and* fail more
often. Pooled across tasks, the naive correlation between tokens and quality can come out
**negative** while the true within-task effect is positive — Simpson's paradox, and it will
happen to you.
→ Every task is run under **every arm** (paired/within-task design), and every comparison is a
*paired* delta. Task identity never enters the numerator.

**③ Coverage is not test quality.** A test that calls the function and asserts nothing gives
100% line coverage. An agent optimising for a coverage gate learns this in one turn.
→ Test quality is measured by **mutation score**: perturb the implementation, re-run *the
agent's own tests*, count how many mutants die. Assert-free tests score 0.

**④ Nondeterminism eats small effects.** One run per cell measures the sampler, not the
system.
→ *n* ≥ 5 seeds per (task × arm) cell, fixed temperature, pinned model id, and everything
recorded.

---

## 2. Design — two factors, four arms

Factor **P** = process (unstructured / DOE). Factor **B** = token budget (low / matched /
high). Fully crossing them is wasteful; these four cells answer the three hypotheses:

| arm | process | budget | what it is for |
|---|---|---|---|
| **A0** `baseline` | one prompt, no kit, no gate | whatever it takes | the floor, and the industry default |
| **A1** `baseline-rich` | same prompt + "write tests first, then self-review twice" | free-running, high | H1 within the unstructured process — spend without structure |
| **A2** `doe` | full kit: `/directive` → approve → `/execute` → gate | whatever it takes | the product |
| **A3** `baseline-matched` | A1's loop, **capped at A2's spend on that task** | matched, per task | **H2** — the control that can kill the thesis |

**Token matching (A3) is the crux.** Do it per task, not on average:

1. Run A2 on task *t*, seed *s*. Record total tokens `T(t,s)` (input + output + thinking + all
   sub-agent turns — count everything you would pay for).
2. Run A3 on task *t* with budget `T(t,s) ± 10%`: let the self-refinement loop keep iterating
   until it is within the band, then stop it. Runs that finish under 90% of the band are
   *padded* with another review iteration; runs that blow past 110% are **truncated and
   recorded as truncated** (report the truncation rate — a high one is itself a finding).
3. Compare A2 vs A3 pairwise on the same task and seed.

Anything else — matching on the average, or eyeballing "roughly similar" — reintroduces
difficulty as a confounder through the back door.

**The human in the loop must not leak.** DOE requires a human to flip `STATE: DRAFT` →
`APPROVED`. In the benchmark that is an **oracle approver** with a written, fixed policy
(approve iff the directive names the same files and behaviours as the task statement; at most
one revision request; never reveal hidden-test content). Log every approval decision. A human
who "helps" the DOE arm during approval is the single easiest way to fake this result. The
human touchpoint is also a **cost** — report it in the cost column as *N approvals*, never
folded into tokens.

**Unit of analysis:** the (task, arm, seed) run. **Cluster:** the task. Bootstrap resamples
tasks, not runs — 20 tasks × 5 seeds is 20 independent units, not 100.

---

## 3. The task corpus

Twenty tasks is the minimum that gives usable CIs on a medium effect; below twelve, stop and
call it a pilot.

Each task ships:

```
tasks/T07_invoice_rounding/
├── task.json      id, tier, protected roots, stack, the run command
├── prompt.md      the request, exactly as a developer would type it
├── fixture/       a real repo state: source, an existing green suite, config
├── hidden/        the acceptance suite — never copied into the agent's workdir
└── verify.sh      applies hidden/, runs it, exits non-zero on failure
```

Requirements, each of which exists because ignoring it invalidates a published benchmark:

- **Three difficulty tiers** (T1 local function · T2 cross-module with an existing suite to not
  break · T3 ambiguous request with a genuine spec decision inside). Tier 3 is where the
  directive is supposed to earn its keep; without it you are measuring autocomplete.
- **No ceiling, no floor.** Pilot every task at A0. Anything that A0 solves 5/5 or 0/5 carries
  no signal — replace it or move it to a tier where it discriminates.
- **Contamination control.** Public-repo tasks may be in the training data. Prefer fixtures
  authored for the benchmark or drawn from private/post-cutoff code, and record each task's
  provenance in `task.json`. Report results split by provenance if you cannot avoid public
  tasks.
- **Hidden tests must test the *stated* behaviour and nothing else.** A hidden test that
  encodes an unstated design preference measures compliance with your taste, not correctness.
  Two people write them; disagreements are spec bugs, fix the prompt.
- **A pre-existing green suite in every fixture**, so "did it break something" is measurable.

---

## 4. Metrics

| # | metric | how | why it is hard to game |
|---|---|---|---|
| **1** | **Resolve rate** *(primary)* | `verify.sh` — hidden suite, pass/fail per run, pass@1 over seeds | The agent never sees these tests |
| 2 | **Mutation score** | AST mutants of the changed source × *the agent's own* tests; killed / viable | Assertion-free and tautological tests score 0 |
| 3 | **Regression breakage** | fixture's pre-existing suite, after the run | Sabotaging old tests to go green shows up here |
| 4 | **Changed-file coverage** | the kit's own `coverage.sh` | Descriptive only — see trap ③ |
| 5 | **Test-first evidence** | did a failing test exist before the implementation? (commit order / execute log) | Distinguishes *test-driven* from *tests-appended* |
| 6 | **Spec drift** | blind rubric, 0–3, on "does this do what was asked" | Blind + shuffled + two independent judges (§5) |
| 7 | **Cost** | total tokens, USD, wall-clock, **and human approvals** | The denominator of the whole exercise |

Metric 2 is the one that actually speaks to *"better **test-driven** code"*. Report it on the
subset of runs that produced any test at all, and report that subset size — an arm that writes
no tests must not win the mutation column by having no data.

Metric 6 needs care: an LLM judge that knows which arm it is scoring will find the DOE output
better because DOE outputs look more organised. Strip all provenance, shuffle the order,
score A-vs-B blind, use a judge model from a different family than the one under test, and
**validate the judge on a 30-run human-labelled subset** — report the agreement (Cohen's κ). If
κ < 0.6, drop metric 6 rather than publish it.

---

## 5. Analysis

Fix all of this *before* the first run and commit it. Analysis chosen after seeing the data is
not analysis.

**Per-arm headline.** For each metric, per arm: mean, and a 95% CI from a **cluster bootstrap
resampling tasks with replacement** (10k resamples). Never report a bare mean.

**H2 test (the important one).** Paired, per task: `d_t = quality(A2, t) − quality(A3, t)`
averaged over seeds. Report `mean(d)` with a bootstrap CI over tasks, plus the paired sign test
(Wilcoxon signed-rank) as a distribution-free backstop. **Verdict: H2 survives iff the CI
excludes 0 in the positive direction.**

**H1 / H3 (dose–response).** Within each process, regress quality on `log(total_tokens)` with a
task fixed effect — a mixed model if you have the machinery, a within-task demeaned OLS if you
do not (the demeaned version is three lines and removes the difficulty confound exactly). Report
the slope with a cluster-bootstrap CI. Then plot the **cost–quality frontier**: tokens on x,
resolve rate on y, one curve per arm, CI ribbons. That single chart is the honest answer to the
original question, and it is the chart that will show H3 — the point where the curve flattens
is the budget past which you are burning money.

**Multiplicity.** One primary endpoint. Secondary metrics get Holm–Bonferroni across the family
and are labelled *exploratory* if the primary did not survive.

**Power, before you start.** With 20 tasks, 5 seeds, and the run-to-run variance you measured
in the pilot, compute the minimum detectable effect. If the MDE is 20 percentage points,
you cannot detect a real 8-point improvement and the experiment is not worth running at that
size — add tasks, not seeds (tasks are the clustering unit; seeds have sharply diminishing
returns).

**Pre-registration.** Write hypotheses, arms, metrics, exclusion rules and the analysis into
`bench/PREREGISTRATION.md`, commit it, and cite the commit hash in the results. Any deviation
goes in a "deviations from pre-registration" section. This costs an hour and is the difference
between a benchmark and a screenshot.

---

## 6. What each outcome actually licenses you to say

| result | the honest headline |
|---|---|
| H2 holds (A2 > A3 at matched budget) | "The structure buys quality — the tokens alone do not." **This is the claim worth having.** |
| H2 null, H1 holds | "Quality tracks spend; DOE is a way to spend, not a better one." Then argue DOE on *predictability* and *reviewability*, and stop claiming quality. |
| H2 holds only on tier 3 | "The directive pays where the request is ambiguous." Narrower, more credible, and probably the true shape of the effect. |
| Both null | The process costs and does not pay on this corpus. Say so — and check the corpus for ceiling effects before believing it. |
| A2 wins on mutation score but not on resolve rate | "Better tests, same correctness." Legitimate and interesting: it predicts a lower future regression rate, which is a *different* experiment. |

Publishing the second and fourth rows when you get them is the only thing that makes the first
row believable when you get *that*.

---

## 7. Threats to validity — state them in the results, not in the appendix

- **Contamination.** Public fixtures may be memorised. Mitigated by provenance tagging, never
  eliminated.
- **Model drift.** A hosted model changes under a fixed name. Pin the full model id, record the
  date of every run, and re-run A0 as a **temporal control** on the final day; a moved baseline
  invalidates cross-time comparisons.
- **Harness advantage.** DOE gives the agent extra tooling (`run.sh`, a coverage gate). If the
  baseline arm cannot run the tests at all, you are measuring tool access, not process. Give
  **every** arm the same test-running ability; the difference must be the *protocol*, not the
  toolbox.
- **Kit leakage.** `.doe/` present in a baseline fixture leaks the methodology through the
  templates. Baseline workdirs must be clean, and the guard must be absent, not merely disabled.
- **Truncation bias in A3.** Report the truncation rate. If most A3 runs hit the cap mid-thought,
  the matched comparison is unfair to the baseline and the H2 result is not yet earned.
- **Metric–gate circularity.** Do not use the kit's own coverage gate as a *quality metric* for
  the arm that was optimised against it. It is reported, not scored.
- **Generalisation.** Two stacks, twenty tasks, one model family. Say that sentence in the
  abstract.

---

## 8. Reporting

A result row that does not contain **(effect, 95% CI, n tasks, n seeds, model id, date, commit)**
is not a result. Publish `bench/results/*.jsonl` raw, including failed and truncated runs — the
runs you drop are the ones a reader most needs to see.

Suggested headline table:

| arm | resolve@1 | mutation score | regressions | tokens (median) | approvals | USD |
|---|---|---|---|---|---|---|
| A0 baseline | 0.44 [0.31, 0.57] | 0.29 [0.18, 0.41] | 0.12 | 18k | 0 | — |
| A1 baseline-rich | … | … | … | … | 0 | — |
| A2 doe | … | … | … | … | 1.2 | — |
| A3 baseline-matched | … | … | … | … | 0 | — |

*(numbers above are a formatting example, not results)*

And two charts: the cost–quality frontier, and the paired A2−A3 delta per task (a caterpillar
plot shows instantly whether one task is carrying the whole effect — which happens more often
than anyone admits).

---

## 9. Running it

```bash
bench/run.py --arms A0,A1,A2,A3 --tasks all --seeds 5 --out bench/results/
bench/score.py bench/results/                # hidden suite + mutation + regressions
bench/analyze.py bench/results/ --report bench/results/REPORT.md
bench/selftest.sh                            # proves the scorer detects bad tests
```

`bench/selftest.sh` is the equivalent of `guard_selftest.py`: a scorer that silently stops
discriminating between a real test suite and an assertion-free one would produce a beautiful,
wrong benchmark. It feeds the scorer a known-good and a known-worthless suite and fails if
their mutation scores are not far apart.

See [`bench/README.md`](../bench/README.md) for the harness, the task format, and how to add a
task.
