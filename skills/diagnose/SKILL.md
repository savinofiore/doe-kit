---
name: diagnose
description: Diagnostic-first debugging. Generates three competing hypotheses, adds only the minimal logging that discriminates between them, and forbids any code fix until the root cause is confirmed by log evidence. Use for bug reports where the error could plausibly come from several layers (400s, broken flows, crashes, unexpected behaviour).
---

# Diagnose — evidence before fix

## RULES (STRICT)

- **NO FIX** until the root cause is confirmed by log evidence.
- Forbidden: `Edit`/`Write` on application code (anything that is not logging) before
  confirmation.
- Allowed: adding print/log statements at the candidate points.
- Forbidden: declaring a hypothesis confirmed without evidence in the logs the user provides.

## Workflow

### Step 1 — Hypotheses

Generate exactly 3 competing hypotheses, ordered by likelihood, with the rationale.

For each hypothesis state:

- The layer involved (UI / state / interceptor / auth / backend / schema / routing).
- The signal expected in the logs if it were TRUE.
- The signal expected if it were FALSE.

Output: a markdown table.

### Step 2 — Instrumentation plan

For each hypothesis, propose the minimal logging that uniquely confirms or refutes it.

Required output:

```
| Hypothesis | Log point (file:line) | Log content | Expected output if TRUE |
```

### Step 3 — Apply logging only

Apply ONLY the logs. No other change to application code.

Ask the user to:

1. Run the repro.
2. Paste the complete logs (not truncated).

### Step 4 — Analyse the logs

Read the logs. Discard the refuted hypotheses.

- One confirmed → Step 5.
- None confirmed → generate 3 new, deeper hypotheses (back to Step 1, with `HYPOTHESES.md`
  updated so the same ones are not retested).

### Step 5 — Propose the fix

Only after confirmation:

- Propose a fix that addresses the **cause**, not the symptom.
- Explain explicitly why the fix resolves the confirmed cause.
- Wait for approval before applying.

> In a DOE project the fix goes through `/directive` (bug flow) — the confirmed cause becomes
> the "Current vs expected" section and the log evidence becomes the regression test.

### Step 6 — Cleanup

After the fix is applied and validated:

1. Remove the diagnostic logging added in Step 3.
2. Run the project's static analysis.
3. If `HYPOTHESES.md` exists in the repo, update it with the hypotheses tested and their
   outcome, so the same ground is not covered twice.

## Critical layers (fill in per project)

Keep a per-project list of the layers to consider for every bug, with their specific traps.
Some that recur:

- **Auth interceptor** — stale token, silent 401 refresh, expiry handled in the wrong place.
- **HTTP client** — base options, timeouts, default headers.
- **State layer** — stale state, missing disposal, direct mutation of a state collection.
- **Routing guards** — blocked navigation, redirect to login, push vs replace mismatch.
- **Enum parsing** — a new value from the backend can fail silently.
- **Known red herrings** — layers that *look* guilty and almost never are. Write them down as
  they are discovered; they are what turns a 20-minute debug into a 3-hour one.

## Expected final output

A `HYPOTHESES.md` (or a session-report section) with:

- The hypotheses generated.
- The logs added and removed.
- The user logs collected (truncated if long, but with the key lines).
- The confirmed hypothesis and its evidence.
- The fix applied, with `file:line`.
- Clean static analysis output.
