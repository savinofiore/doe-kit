# A day with DOE

A concrete walkthrough of one feature, one bug, and one review. Nothing here is aspirational —
it is what the loop actually feels like once the guard is armed.

---

## Feature: "add a favourite toggle to the course card"

**You:** *"Add a favourite toggle to the course card."*

**Agent:** tries to edit a file under a protected root. The guard denies the write and returns
the process instructions. The agent switches to the interview:

> *"Feature or bug?"*

**You:** feature.

The agent then does the work that usually never happens: it reads every file involved, finds
every test that touches them, and runs the baseline gate. Green. It writes
`.doe/directives/07_course_favourite.md`:

- **Objective** — one paragraph.
- **Current vs expected** — a two-row table.
- **Files involved** — the model, the repository, the state, the card.
- **Impact on existing tests** — *empty*, because the change is additive. That empty table is
  a claim: the existing tests must stay green for the whole execution.
- **Test Contract** — five tests as code: toggling on, toggling off, the optimistic update
  rolling back on a transport error, parsing a payload where the flag is missing, and the
  repository mapping a 409.

Then it stops. `STATE: DRAFT`.

**You** read it. Two of the five tests describe behaviour you did not intend — the optimistic
rollback is not what the product wants. You edit the directive, drop that test, and change one
line in "Current vs expected".

This is the moment the whole system exists for. Fixing it here costs a paragraph. Fixing it
after implementation costs an afternoon, and you would have had to read 400 lines of confident
code to notice.

You set `STATE: APPROVED`.

**You:** `/execute 07`

The agent summarises the directive and asks for confirmation. You say yes.

1. Baseline → green.
2. It writes the four Test Contract tests → runs the gate → **RED**. Four failures, each for
   the right reason.
3. It writes the production code.
4. Gate → green.
5. It deletes `07_course_favourite.md`. The tests stay. The guard re-arms.

---

## Bug: "the badge shows the wrong count after deleting"

**You:** *"After deleting an item the badge count is off by one."*

**Agent:** *"Feature or bug?"* → bug. It runs the baseline first — worth doing, because
sometimes the baseline is already red and the bug is not where anyone thought.

The directive is short:

- **Current (bug) vs expected** — the observed count vs the correct one.
- **Regression test** — one test, as code: arrange a state with three items, remove one, assert
  the badge reads two.
- **Cause confirmation** — the state removal mutates the list in place, so the notifier never
  sees a new reference and never rebuilds.
- **Fix** — before/after on four lines.

You approve. `/execute 09`:

1. The regression test goes in → **RED**. The agent shows you the failure and confirms it fails
   for the stated cause, not because the test setup is wrong.
2. It changes the production code — and only the production code.
3. Green.

The test that was written to reproduce the bug stays in the suite forever. That is the part
that compounds: every bug you fix leaves behind the test that would have caught it.

---

## Review: a branch before merge

**You:** `/review`

The agent reads the diff against the base, runs static analysis, and classifies every finding
twice: by **severity** (P10/P7/P4/P1) and by **testability**.

That second axis is the one that makes the review useful:

- A state object mutated in place → **logic-testable** → goes into
  `.doe/directives/11_review_major.md` with a regression test.
- A hardcoded colour → **non-testable** → stays in the report as a direct fix. No test could
  turn red for it, and pretending otherwise builds a gate nobody believes.

The review edits nothing. It ends with: *"Run `/review-fix`…"*.

**You:** `/review-fix` — "the Critical ones and the style fixes".

Two tracks run:

- **Track A** — the Critical directive goes through the BUG flow: red tests, fix, green gate,
  directive deleted.
- **Track B** — the style fixes are applied with `Edit`, previewed one at a time, outside the
  gate.

The final report has a track column, so it is obvious which fixes are backed by a test and
which are backed by a human reading a diff.

---

## What the loop buys you

| Without DOE | With DOE |
|---|---|
| "Done!" — based on the agent's own summary | Done = exit code 0 |
| Requirements clarified after implementation | Requirements clarified in a paragraph, before |
| A red test tempts an edit to the test | A red test is a code bug, mechanically |
| Fixed bugs stay fixed by luck | Fixed bugs stay fixed by regression |
| Review findings become vague to-dos | Findings become directives with tests, or explicit direct fixes |

The cost is real and worth naming: every change now goes through a written spec, and the
smallest change costs one round-trip. For a throwaway prototype that is a bad trade. For code
that has to survive contact with other people, it is the cheapest trade in the list.
