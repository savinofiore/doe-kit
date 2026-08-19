---
name: execute
description: Phase 2 of the DOE process — run an APPROVED directive NN test-first (baseline → RED → fix → green gate → cleanup). Refuses to run on a DRAFT or missing directive. Use when the user runs /execute NN or asks to implement an approved directive.
---

# Execute — run an approved directive (PHASE 2: RED → fix → gate → cleanup)

DOE system, execution. Takes a directive `NN` that is already written and APPROVED and drives
it to a green gate with the test-first flow. It does not re-invent the spec: the spec is the
directive. The code adapts to the tests, never the other way round.

Invocation: `/execute NN` (e.g. `/execute 05`). "directive 5" → `05_*.md`.

## Preflight (in order, stop at the first failure)

1. **Argument NN.** Missing → ask which directive to run (list the non-template files in
   `.doe/directives/`). Do not proceed without a number.
2. **Existence.** Read `.doe/directives/NN_*.md`. Not there → refuse: *"Directive NN does not
   exist. Create it with `/directive`."*
3. **Approval.** Look for `STATE: APPROVED` in the directive. If it is `DRAFT` (or absent) →
   stop: *"Directive NN is DRAFT. Review it, set `STATE: APPROVED` by hand, then run
   `/execute NN` again."* (Without APPROVED the directive-guard blocks the protected roots
   anyway.)
4. **Human confirmation.** Summarise the directive (type, objective, files, Test Contract) and
   ask explicitly yes/no:
   > *"You have reviewed and approved directive NN. Confirm — shall I execute? (yes/no)"*
   Proceed only on **yes**. On no → stop.

## Execution by type (the flow comes from the directive's template)

Recognise the type from the `## Type` field (or from the `NN_review_*` file name).

### BUG / REVIEW (test-first, red→green)

1. **Baseline** — `.doe/execution/run.sh <path>` to pin the starting state.
2. **RED** — materialise the Test Contract / regression tests from the directive into the test
   tree. Run them → they must be **RED** for the **right reason** (the real violation, not a
   setup error). Confirm the red before touching production code.
3. **FIX** — change ONLY production code, one finding/bug at a time. **Never** modify a test
   to make it pass.
4. **GREEN** — `.doe/execution/run.sh` → iterate until green (static analysis + whole suite).

### FEATURE (test-first, red→green)

1. **Baseline** — `.doe/execution/run.sh` → must be **green** (healthy starting state).
2. **Tests** — read `Impact on existing tests` in the directive:
   - **Empty (backward compatible):** materialise ONLY the NEW Test Contract tests. Existing
     tests stay green for the whole execution (that is the proof of backward compatibility).
   - **Non-empty (breaking):** besides the new tests, modify/delete **ONLY** the tests listed
     in the table, rewriting them to the NEW expected behaviour.
3. **RED** — `.doe/execution/run.sh` → the new plus rewritten tests fail (the old code does
   not produce the new behaviour yet). Keystone: a rewritten test that is already green here
   means the feature is a no-op or the test is fake → stop and check. Untouched tests stay
   green.
4. **Implement** — write/modify production code following the directive's spec.
5. **GREEN** — `.doe/execution/run.sh` → iterate until green.

> **Declared-tests constraint:** you may touch ONLY the tests listed in `Impact on existing
> tests`. If during execution you need to change a test that is not in the table → **STOP**:
> either the code is wrong (fix the code), or the directive is incomplete (back to
> `/directive`). Never change a test to chase green.

## Red-test rule (the keystone)

A red test means the **code** is wrong, never the test. A test is modified ONLY when the
directive explicitly declared it obsolete for the planned changes.

## Project constraints

The generated code respects the conventions declared in the project's `CLAUDE.md` and in the
stack skills. The directive does not restate them; it assumes them.

## Cleanup (L3)

Green gate + directive checklist complete → the directive has served its purpose: **delete**
`.doe/directives/NN_*.md`. The tests stay in the test tree as permanent regression. With the
directive gone there is no `STATE: APPROVED` left → the directive-guard re-arms.

Report back to the user what went from RED to GREEN and which files were touched.
