---
name: review-fix
description: Applies the findings of a prior /review on two tracks — DOE directives implemented test-first through the gate (logic findings), and direct edits for non-testable findings. Requires explicit user approval of which items to fix. Never combines review and fix in one pass.
---

# Review Fix — apply what the review found

## Prerequisite

`/review` must have run in the same conversation (or the user must supply a review report
explicitly). The review produces two outputs this skill consumes:

- **Block A** — DOE directives `.doe/directives/NN_review_<tier>.md` (logic findings).
- **Block B** — non-testable findings in the report (direct fixes).

With no review to work from:

1. Refuse to run.
2. Tell the user to run `/review` first.
3. Produce no edits.

## Two tracks

- **Track A — DOE directives (Block A).** For each selected `NN_review_*.md`, run the DOE BUG
  flow test-first and the `.doe/execution/run.sh` gate. This is the only path for logic fixes:
  no code without a directive and without a green gate.
- **Track B — direct fixes (Block B).** Non-testable findings (styling, cosmetic, responsive,
  i18n): applied with `Edit`, outside the gate, with static analysis as the only check.

## Workflow

### Step 1 — Confirm scope

Ask which items to apply, stating which track each belongs to. Examples:

- `"all the Critical ones"` (can touch both tracks)
- `"directive 05"` (Track A only)
- `"the style fixes"` (Track B only)
- `"everything"` (needs explicit confirmation — it is usually scope creep)

Do NOT proceed without a concrete answer.

### Step 2 — Track A: implement the DOE directives (BUG flow, test-first)

For each confirmed `NN_review_<tier>.md`, in finding order:

1. **Baseline** — `.doe/execution/run.sh <path>` to pin the starting state.
2. **Red tests** — write the Test Contract regression tests (one per finding) → gate → **RED**,
   each for the right reason. Show they are red before touching production code.
3. **Fix** — change ONLY production code (never the tests) until the tests pass.
4. **Gate** — `.doe/execution/run.sh` → iterate to **GREEN** (analysis + whole suite, no
   regression).
5. **L3 cleanup** — green gate + checklist complete → **delete** the directive file from
   `.doe/directives/`.

> **Red-test rule (the keystone):** a red test means the code is wrong, never the test. Do not
> modify a test to make it pass.

### Step 3 — Track B: direct fixes (preview + apply)

For each confirmed non-testable finding, before applying:

- Show the file path and the lines involved.
- Show the proposed diff (before/after).

Wait for the user's OK when the diff is non-trivial or touches more than one file. Then apply
one change at a time with `Edit`.

If a `PostToolUse` hook runs static analysis after each edit and reports new errors:

- Stop immediately.
- Show the error.
- Ask whether to fix or roll back.

### Step 4 — Final verification

After both tracks:

```bash
.doe/execution/run.sh   # full gate (analysis + suite) — covers Track A
<static analysis>       # redundant but explicit for Track B
```

Expected: green gate and a clean analysis (or only pre-existing issues).

### Step 5 — Final report

One unified table with a track column:

```
| # | Track (DOE / direct) | Directive / File | Item (from review) | Status (applied / gate-green / skipped / deferred) | Notes |
```

Plus:

- Applied vs requested counters, per track.
- Directives deleted (L3) with their gate outcome.
- Final output of `.doe/execution/run.sh` and of the static analysis.

## RULES (STRICT)

- **Do not apply** fixes the user did not explicitly approve.
- **Do not introduce** changes absent from the review (no scope creep — if you spot another
  problem, note it at the end of the report but do NOT apply it).
- **Track A is test-first:** never change logic code without a red test first, and never
  without a green gate. Never adapt a test to make it pass.
- **Do not combine** with a fresh review. If the user asks for "review + fix", split it:
  `/review` first, then `/review-fix`.
- If static analysis or the gate introduces new errors, stop and ask. Do not auto-correct
  aggressively.
- Delete a directive (L3) **only** after a green gate and a completed checklist.

## The failure pattern this prevents

Usage reports showed recurring cases where, during a review-only pass, the assistant started
implementing unrequested fixes, forcing the user to interrupt and ask for a rollback. Formally
splitting `/review` (analysis) from `/review-fix` (application) makes that pattern impossible.
