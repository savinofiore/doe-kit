# BUG directive: [Name]

> Copy this file to `NN_name.md` (progressive number) when the change is a **bug fix**.
> For a **feature** use `00_FEATURE_TEMPLATE.md` instead.
> The **regression test** is MANDATORY and is written BEFORE the fix: it must be RED and it
> must reproduce the bug. The directive is "done" only when `.doe/execution/run.sh` exits
> GREEN *without the test having been modified to make it pass*.

STATE: DRAFT

> **Approval gate.** `STATE: DRAFT` = being written/discussed: the directive-guard BLOCKS
> every change to the protected roots. After re-reading and discussing the directive, change
> it by hand to `STATE: APPROVED`: only then can `/execute NN` write the red test and the fix.
> At L3 cleanup the directive is deleted.

## Type

**bug** — existing behaviour is wrong and must be corrected.

## Objective

[Description of the bug: what goes wrong, how it shows up, steps to reproduce]

## Current (wrong) vs expected behaviour

| | |
|---|---|
| **Current (bug)** | [wrong behaviour observed] |
| **Expected** | [correct behaviour] |

## Files involved

- [Every suspect production file — analysed before writing the directive]

## Tests involved

- [Existing tests that touch this area]
- **Baseline:** run `.doe/execution/run.sh <path>` BEFORE any change to pin the starting state.

## Regression test (MANDATORY — written BEFORE the fix, must be RED)

A test scenario that reproduces the bug. **Unit test only**, deterministic, offline. Run it
BEFORE touching the code: it must fail (**RED**), and it must fail **for the right reason**
(the real defect, not a broken test setup).

### `<tests>/<area>/<name>_test.<ext>`

```
[Test code:
 - arrange: the state that triggers the bug
 - act: the action that manifests it
 - assert: the CORRECT expected behaviour → RED today]
```

## Cause confirmation (why the test is red)

[Explain why the test fails — the root of the bug in the production code. Confirm the red
comes from the bug and not from a defect in the test.]

## Fix (the code — NOT the test)

### MODIFY: `<src>/path/file`

**Before → After:**

```
// before (bug)

// after (fix)
```

> **Red-test rule (the keystone):** you change the **code**, never the test. The regression
> test stays untouched; it must go from RED to GREEN thanks to the fix alone. A test is
> modified ONLY when this directive declared it obsolete for the planned changes.

## Execution plan (L2 — BUG flow)

1. Run the baseline → pin the starting state.
2. Write the regression test → `.doe/execution/run.sh <path>` → **RED** (for the right reason).
3. Change the production code (not the test).
4. `.doe/execution/run.sh` → iterate until **GREEN**.

## Verification (L3)

1. [ ] The regression test was RED before the fix and is GREEN now — without being modified.
2. [ ] `.doe/execution/run.sh` exits GREEN (static analysis + whole suite) — no regression elsewhere.
3. [ ] Directive complete → **delete this file** from `.doe/directives/`.

## Notes

- [Dependencies on other directives, warnings, known red herrings]
