# DOE — Directive · Oriented · Execution

A three-level system for deterministic, verifiable code generation.

The principle: **a directive is not "done" because someone says so, but because a green test
proves it.** The test runner is the only judge of correctness.

```
┌──────────────┐   generates ┌──────────────┐   gate    ┌──────────────┐
│ L1 DIRECTIVE │ ──────────► │ L2 EXECUTION │ ────────► │ L3 VERIFY    │
│  spec + test │             │  test runner │           │ pass→cleanup │
│   contract   │ ◄────────── │  (red→green) │           │              │
└──────────────┘    fix      └──────────────┘           └──────────────┘
```

---

## Why it exists

An agent that writes code is fast and confident. Neither property is correctness. Left alone
it will:

- implement something adjacent to what you asked for, and call it done;
- declare a task complete on the strength of its own summary;
- when a test goes red, edit the test.

DOE removes all three by construction. The spec is written before the code and reviewed by a
human. The tests are written before the code and are the acceptance contract. And "done" is
not a claim — it is an exit code.

## The mandatory process (two phases and a human gate)

**No code change without a directive.** This is not a written rule that an agent can talk
itself out of: the **directive-guard** (a `PreToolUse` hook) mechanically blocks every write
into the protected roots until a directive with `STATE: APPROVED` exists. Trying to change
code without one is refused, and the interview starts instead.

The cycle is split into two commands with a human approval in the middle:

```
/directive  → interview + writes .doe/directives/NN_name.md (STATE: DRAFT)   [ZERO code]
     ↓  the human reviews and sets STATE: APPROVED by hand   ← unlocks the guard
/execute NN → yes/no confirmation → RED → fix → green gate → cleanup (delete NN)
```

### Phase 1 — `/directive` (compiles, does not execute)

1. **Opening** — always the first question: **feature or bug?** It determines the flow and the
   template.
2. **Context analysis** — analyse every file involved, find every test involved, and **run the
   baseline** before writing the directive.
3. **Write the directive** (Objective · Current vs expected · Files · Tests · Test Contract)
   with `STATE: DRAFT`, then **stop**. No code, no materialised tests.

### The approval gate (manual)

The human re-reads the directive and changes `STATE: DRAFT` → `STATE: APPROVED` **by hand**.
That is the only way to unlock the guard: from that point the protected roots are writable.

This gate is the entire point. It is where you catch a misunderstood requirement while it
still costs one paragraph to fix, instead of after 400 lines of confident code.

### Phase 2 — `/execute NN` (runs the approved directive)

Asks for a yes/no confirmation, then applies the flow for the directive's type.

---

## The three flows

### FEATURE

Principle: **the test suite is the map of the use cases. An untested use case is a use case
that does not exist.** Planning a feature means enumerating its use cases — which means
enumerating its tests — in the directive, before the code.

1. **Baseline**: existing tests → green (healthy starting state).
2. **Write and discuss the directive**, including `Impact on existing tests` (default EMPTY).
3. Two cases:
   - **Backward compatible** (impact empty): add only the NEW tests → RED; the existing ones
     stay green, which is the proof of backward compatibility.
   - **Breaking** (impact filled): rewrite ONLY the listed tests to the new expectation → RED.
4. **Implement** the change.
5. **Re-run** → everything green.

> Step 3 (RED) is the test-first keystone. A rewritten test that is already green *before* you
> implement means the feature is a no-op or the test is fake. "Green first" only applies to
> the baseline in step 1.

### BUG

1. **Reproduce the bug**: write a test scenario that exposes it (red), without touching the code.
2. **Confirm** the test is red for the right reason — the real defect, not a broken setup.
3. **Change the code** until it goes green — without modifying the test.

### REVIEW

Reviews go through DOE too. `/review` classifies the findings and materialises **one directive
per tier** (`NN_review_<tier>.md`) holding only the **logic-testable** findings; each gets its
own regression test. `/review-fix` implements it with the BUG flow (red tests → fix → green
gate → cleanup).

**Non-testable** findings (styling, cosmetic, responsive, i18n) never enter a directive: they
stay in the report as direct fixes, outside the gate. A gate that pretends to verify a colour
token is a gate nobody believes.

---

## The red-test rule (the keystone)

A red test means the **code** is wrong, never the test. Do not modify a test to make it pass.

A test may be modified ONLY when it is listed in the `Impact on existing tests` table of an
**APPROVED** directive, and every row maps to a behaviour change declared in "Current vs
expected". During `/execute` you cannot touch a test outside that table: if you need to →
STOP, either the code is wrong or the directive is incomplete → back to `/directive`.

Marking a test "obsolete" on the fly to dodge a fix is cheating, and it is the single failure
mode this whole system exists to prevent.

---

## L1 — Directive (`.doe/directives/NN_name.md`)

A numbered declarative spec. Copy `00_FEATURE_TEMPLATE.md`, `00_BUG_TEMPLATE.md` or
`00_REVIEW_TEMPLATE.md` depending on the kind of change, rename it with a progressive number
(`05_quiz_lives.md`, `06_review_critical.md`) and fill it in.

**Mandatory:** the **Test Contract** section. It defines the tests before the code — they are
the acceptance contract. Without a Test Contract the directive is not executable.

Reference by number: "directive 5" → `05_*.md`.

## L2 — Execution (`.doe/execution/`)

Running the test suite is the **deterministic gate**. Generated code is correct **if and only
if** the gate is green.

```bash
.doe/execution/run.sh                 # full gate: static analysis + whole suite
.doe/execution/run.sh <path>          # narrow during development
.doe/execution/run.sh --name "Quiz"   # filter by test name
```

TDD workflow (test-first, red→green):

1. Write the Test Contract tests → run → **RED** (they fail: the code does not exist).
2. Write the production code.
3. Re-run → iterate until **GREEN**.
4. No test adapts to the code: the code adapts to the tests.

## L3 — Verification and cleanup

Green gate + completed checklist → the directive has served its purpose: **delete it** from
`.doe/directives/`. Directives are ephemeral; the tests stay in the test tree as permanent
regression.

Deleting the directive also re-arms the guard — there is no `STATE: APPROVED` left, so the
protected roots go read-only again until the next directive. The system returns to its safe
state by default, not by discipline.

---

## Test scope (the rules)

- **Unit tests only.** No component/widget/E2E tests inside the gate: gate tests must be
  deterministic, offline, device-free. Network, timing and real databases are
  non-deterministic → out of the gate.
- **What gets tested:**
  - **Models / schemas** → parsing, mapping, copy semantics, edge cases (null, missing keys,
    wrong types).
  - **State logic** → transitions driven through the state container with fakes injected.
  - **Repositories** → transport client mocked, response and error mapping.
  - **Utils** → pure functions.
- **The test tree mirrors the source tree** — always, so "which test covers this file" is a
  path transformation, not a search.
- **Business logic never lives in a component or a hook.** It lives in a framework-free layer
  and gets imported. This is not an aesthetic preference: it is what makes the gate possible
  at all. A gate you cannot run offline is a gate that never runs.

The last point is the one that pays for itself. Every project that adopts DOE ends up with a
cleaner architecture than it started with, because the alternative is a gate that cannot see
anything.
