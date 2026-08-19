---
name: directive
description: Phase 1 of the DOE process — interview the user and compile a directive (spec + Test Contract) into .doe/directives/NN_name.md with STATE: DRAFT, writing ZERO code and ZERO tests. Use whenever a code change is requested and no APPROVED directive exists, or when the directive-guard blocks a write.
---

# Directive — compile the directive (PHASE 1: spec only, ZERO code)

DOE system, **forced directive-first**. This skill compiles ONLY the directive. It writes no
code, no tests, implements nothing. It ends with the directive at `STATE: DRAFT`, ready for
human review. Execution is a separate phase: `/execute NN`.

> The directive-guard (PreToolUse hook) blocks every `Edit`/`Write` on the protected roots
> until an `STATE: APPROVED` directive exists. This skill only works inside `.doe/`.

## Rule of engagement (always)

A request to change code with no directive → **do not write code**. Say the directive is
required and start the interview below. No exceptions, not even for a one-line change.

## Interview (produces the directive)

1. **Opening** — ALWAYS ask first: **feature** or **bug**? It determines the flow and the
   template. (`NN_review_<tier>.md` directives come from `/review`, template
   `00_REVIEW_TEMPLATE.md`.)
2. **Context analysis** — analyse ALL production files involved, find ALL tests involved, and
   **run the baseline** (`.doe/execution/run.sh <path>`) BEFORE writing the directive. Pin the
   starting state (feature: green; bug: note what passes and what fails).
3. **Write the directive** by copying the right template (`00_FEATURE_TEMPLATE.md`,
   `00_BUG_TEMPLATE.md` or `00_REVIEW_TEMPLATE.md`) to `.doe/directives/NN_name.md`
   (progressive number, never colliding with an existing directive). Fill EVERY section:
   Objective · Current vs expected · Files involved · Tests involved ·
   **Impact on existing tests** (see below) · **Test Contract** (the test code as SPEC, not
   yet materialised in the test tree) · planned fix/changes. Leave `STATE: DRAFT`.

## Impact on existing tests (how to compile it)

Principle: **the test suite is the map of the use cases**. An untested use case is a use case
that does not exist — nobody added it. Enumerating the use cases = enumerating the tests.

Fill the `Impact on existing tests` table like this — **default EMPTY**:

1. From the "Current vs expected" row: what actually changes. If additive/backward
   compatible → the table stays empty (existing tests stay green, you only add new tests in
   the Test Contract).
2. Only when **breaking**: from "Files involved", find the tests covering them — mirror path
   plus `grep -rl "<Symbol>" <tests>/`.
3. For each test read the assertions → **keep** (out of the table) / **modify** (the old
   assertion is now wrong) / **delete** (the feature is gone). Every `modify`/`delete` row
   MUST map to a row in "Current vs expected". Never invent obsolescence to dodge a fix.

## Test Contract (mandatory in the directive)

Defines the tests BEFORE the code — it is the acceptance contract. Write it inside the
directive as code blocks (spec). Only **deterministic, offline unit tests**; the test tree
mirrors the source tree. Cover the edge cases (null / missing keys, empty list, mapped
transport error, unknown enum value). Do NOT create the test files yet: `/execute` does that.

## STOP — end of phase 1

After writing the directive:

1. Summarise for the user: number, type, objective, files/tests involved, what the Test
   Contract will say.
2. **Stop.** Do not implement. Final output:
   > *"Directive NN is ready at `STATE: DRAFT`. Review it; if it is good, set
   > `STATE: APPROVED` by hand, then run `/execute NN`."*

Never move to the execution phase on your own: the approval (`DRAFT → APPROVED`) is the
user's manual act, and it is what unlocks the directive-guard.
