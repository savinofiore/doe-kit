# REVIEW directive: [Tier] — [Branch]

> Copy this file to `NN_review_<tier>.md` (progressive number) when the findings come from a
> `/review`. **One directive per tier** (Critical/Major/Minor): it groups every **logic**
> finding of the same weight.
> Only **logic, testable** findings land here. Non-testable findings (styling, copy,
> responsive, a11y) do NOT go into a directive: they stay in the report as direct fixes.
> Every finding gets **its own** regression test, written BEFORE the fix: it must be RED and
> reproduce the violation. The directive is "done" only when `.doe/execution/run.sh` exits
> GREEN without any test having been modified to make it pass.

STATE: DRAFT

> **Approval gate.** `STATE: DRAFT` = being written/discussed: the directive-guard BLOCKS
> every change to the protected roots. After re-reading and discussing the directive, change
> it by hand to `STATE: APPROVED`: only then can `/execute NN` write the red tests and the
> fixes. At L3 cleanup the directive is deleted.

## Type

**review** — tier **[Critical | Major | Minor]**. Origin: `/review` on branch `[branch-name]`.

## Objective

Fix the [tier] logic findings surfaced by the review, each covered by a red→green regression
test.

## Findings in this tier (from the review report)

| # | `file:line` | Problem | Suggestion |
|---|-------------|---------|------------|
| 1 | `<src>/path/file:NN` | [violation] | [proposed fix] |
| 2 | `<src>/path/other:NN` | [violation] | [proposed fix] |

## Files involved

- [Every production file named by the findings above]

## Tests involved

- [Existing tests touching this area]
- **Baseline:** run `.doe/execution/run.sh <path>` BEFORE any change to pin the starting state.

## Impact on existing tests (default: NONE)

A review fixes violations without changing intended behaviour → normally **EMPTY**: you only
add one regression test per finding (Test Contract below). Fill the table ONLY when a fix
changes behaviour covered by an existing test (rare); the rules are identical to the FEATURE
template (each row maps to a finding, `/execute` touches only the listed tests).

| test `file:group` | action | reason → which finding/behaviour |
|---|---|---|
| _(empty: a review adds regressions, it does not modify tests)_ | | |

## Test Contract (MANDATORY — one regression test per finding, written BEFORE the fixes)

**Unit tests only**, deterministic, offline. Each test reproduces one finding and must be RED
for the **right reason** (the real violation, not a broken setup) before the fix.

### Finding #1 — `<tests>/<area>/<name>_test.<ext>`

```
[arrange: the state that triggers the violation
 act: the action that manifests it
 assert: the CORRECT expected behaviour → RED today]
```

### Finding #2 — `<tests>/<area>/<name>_state_test.<ext>` (when it is state logic)

```
[State test with the dependency injected as a fake or mock.]
```

**Typical edge cases behind review findings:** direct mutation of a state collection (missing
copy / new list), aliasing without a defensive copy, parsing on null or missing keys, unknown
enum value, transport error mapped incorrectly.

## Fix (the code — NOT the tests)

### MODIFY: `<src>/path/file` (finding #1)

**Before → After:**

```
// before (violation)

// after (fix)
```

> **Red-test rule (the keystone):** you change the **code**, never the tests. Every
> regression test stays untouched; it goes from RED to GREEN thanks to the fix alone.

## Execution plan (L2 — REVIEW flow, identical to BUG)

1. Run the baseline → pin the starting state.
2. Write ALL the tier's regression tests → `.doe/execution/run.sh <path>` → **RED** (each for
   the right reason).
3. Change the production code (not the tests), one finding at a time.
4. `.doe/execution/run.sh` → iterate until **GREEN**.

## Verification (L3)

1. [ ] Every regression test was RED before the fix and is GREEN now — none modified.
2. [ ] Every finding in the tier is covered (the table above fully addressed).
3. [ ] `.doe/execution/run.sh` exits GREEN (static analysis + whole suite) — no regression elsewhere.
4. [ ] Directive complete → **delete this file** from `.doe/directives/`.

## Notes

- Non-testable findings of the same tier stay in the report as direct fixes (`/review-fix` Track B).
- [Dependencies on other review directives, warnings]
