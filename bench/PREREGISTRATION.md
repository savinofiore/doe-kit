# Pre-registration

Fill this in and **commit it before the first run**. Cite the commit hash in the results.
Analysis chosen after seeing the data is not analysis, and an hour spent here is the whole
difference between a benchmark and a screenshot.

| field | value |
|---|---|
| Registered on | *YYYY-MM-DD* |
| Registered by | |
| Kit commit | |
| Model id (pinned, exact) | |
| Temperature / sampling | |
| Agent CLI + version | |

## Hypotheses

- **H1 (dose–response).** Within a fixed process, resolve rate rises with the token budget.
- **H2 (structure, not spend).** At a token budget matched per task and seed, `A2_doe` beats
  `A3_baseline_matched`.
- **H3 (saturation).** Marginal resolve rate per doubling of budget approaches 0 above some
  budget.

## Primary endpoint

**Exactly one:** resolve rate on the hidden acceptance suite, pass@1, averaged within task
before averaging across tasks.

## Secondary endpoints (exploratory unless the primary survives)

Mutation score · regression breakage · pre-existing tests edited · changed-file coverage ·
spec-drift rubric · tokens · USD · wall-clock · human approvals. Holm–Bonferroni across the
family.

## Design

| | |
|---|---|
| Arms | `A0_baseline` · `A1_baseline_rich` · `A2_doe` · `A3_baseline_matched` |
| Tasks | *n =* , tiers 1/2/3 = / / |
| Seeds per cell | *n =* |
| Unit of analysis | the task |
| Budget matching | per (task, seed), band ±10% of `A2_doe`'s recorded spend |
| Approval policy | oracle approver: approve iff the directive names the same files and behaviours as the task statement; at most one revision request; hidden-test content never revealed. Every decision logged. |

## Analysis, fixed in advance

- Per-arm means with 95% percentile bootstrap CIs, 10k resamples, **clustered on task**.
- H2: paired per-task delta `A2 − A3`, bootstrap CI over tasks + Wilcoxon signed-rank.
  **Survives iff the CI excludes 0 in the positive direction.**
- H1/H3: within-task demeaned OLS of resolve rate on `log(tokens)`, cluster-bootstrap CI,
  reported per doubling of budget. Frontier plot for the saturation point.

## Exclusion rules, fixed in advance

A run is excluded only if the harness failed (agent CLI crash, network failure, timeout with no
output). **Runs where the agent produced bad code are never excluded** — that is the
measurement. Every exclusion is listed in the report with its reason.

## Minimum detectable effect

From the pilot's run-to-run variance, at the planned task and seed counts, the MDE on the
primary endpoint is: *____ percentage points.* If a plausible real effect is smaller than this,
add **tasks** (the clustering unit), not seeds.

## Stopping rule

All planned cells are run before any comparison is looked at. No peeking, no early stop, no
adding tasks after seeing results.

## Deviations

Every departure from the above goes here, dated, with the reason — including the ones that
make the result look worse.
