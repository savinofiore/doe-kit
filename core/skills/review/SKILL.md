---
name: review
description: Analysis-only branch/PR review. Classifies findings by severity AND by testability, materialises one DOE directive per tier for the logic findings, and reports the non-testable ones as direct fixes. Never edits code. Use for "review this branch", "review my diff", "PR review".
---

# Review — analysis only, never fixes

## RULES (STRICT)

- **NO code fixes.** Do NOT edit/patch/fix production code or tests. Do NOT run
  `git commit` / `git restore` / `git checkout`. Read, grep and analyse only.
- **DOE exception:** writing directive files in `.doe/directives/NN_review_<tier>.md` is
  allowed and is part of the flow (they are L1 specs, not code). The "no edit" ban covers the
  protected roots, not DOE artifacts.
- **Scope** = exactly what the user asked for. Frontend-only means frontend-only.
- **Output** = a two-block markdown report (logic findings → DOE directives; non-testable
  findings → direct fixes) plus the materialised directives. Every issue must carry a concrete
  fix (a line of code or a precise instruction), but the fix is NOT applied.
- **Close the report with:** "Run `/review-fix`: it will implement the directives through the
  DOE gate and apply the direct fixes. Or tell me which items to apply."

If the user wants the fixes applied, they will ask explicitly via `/review-fix` in a later
message. Never combine review and fix in one pass.

## DOE coherence (the keystone)

The project forbids code changes without a DOE directive. The review respects that: **logic**
findings are materialised as DOE directives that `/review-fix` will implement through the
test-first gate. **Non-testable** findings stay as direct fixes tracked in the report.

### Classifying findings (logic-testable vs non-testable)

For each finding, decide whether a **deterministic offline unit test** could cover it (the DOE
gate rule):

- **Logic-testable → DOE directive.** Bugs in:
  - **Models** — parse/serialize/copy, enum parsing, null and missing keys.
  - **State** — direct mutation of a state collection, aliasing without a defensive copy,
    immutability, state-machine logic.
  - **Repositories / services** — response and error mapping, transport exception handling.
- **Non-testable → direct fix.** Anything that needs a widget/DOM/context, or is cosmetic:
  hardcoded design tokens, missing translation call, responsive behaviour, naming, layout.
  These do NOT enter a directive.

When in doubt: if you cannot write an offline unit test that turns red for that finding, it is
non-testable → direct fix.

## Workflow

### Step 1 — Identify changed files

```bash
git diff <base>...HEAD --name-only
git diff <base>...HEAD --stat
```

### Step 2 — Analyse the full diff

```bash
git diff <base>...HEAD
```

Read the diff and analyse every change against the checklist below.

### Step 3 — Run the project's static analysis on the changed files

Filter to the errors/warnings introduced by this branch; ignore pre-existing ones.

### Step 4 — Classify the problems found

Sort by decreasing weight (Critical, Major, Minor, Cosmetic). For each finding also assign its
nature: **logic-testable** or **non-testable** (see above).

### Step 5 — Materialise the DOE directives (one per tier, logic findings only)

For every tier (Critical/Major/Minor) that holds at least one **logic-testable** finding:

1. Compute the progressive number from the files already in `.doe/directives/` (excluding
   `00_*_TEMPLATE.md`).
2. Create `.doe/directives/NN_review_<tier>.md` from `00_REVIEW_TEMPLATE.md` and fill it:
   - the "Findings in this tier" table with `file:line` + problem + suggestion for every logic
     finding;
   - the Test Contract with **one regression test per finding** (test path mirroring the
     source path);
   - Files involved and the Fix section, from the suggestions.
3. Do NOT write code or tests: the directive is spec only. `/review-fix` writes the real tests.

Cosmetic findings and every non-testable finding generate no directive.

### Step 6 — Show the report

Present the two-block report (see "Report format"), list the directives created, and ask for
confirmation before doing anything else.

### Step 7 — Post to GitHub (only if asked)

1. Find the PR: `gh pr list --head $(git branch --show-current) --json number -q '.[0].number'`
2. If not found, ask for the PR number.
3. Post with `gh pr comment <number> --body "<review>"`.

Never post without explicit user confirmation.

## Review checklist

### Architecture

- Layer separation respected (UI / state / repository).
- Repository pattern for data access (no direct API calls from UI or state).
- Dependencies injected, not imported inside the layer that must stay testable.
- Models carry their own parse/serialize/copy contract.

### State

- No direct mutation of state collections.
- New collections on every state transition; defensive copies where aliasing is possible.
- Reads and writes of state used in the right lifecycle position.
- Temporary state disposed.

### OOP practice

- Single responsibility.
- Early return, nesting no deeper than 2–3 levels.
- Max 3 arguments per function; short, readable functions.
- No side effects, no business logic in the UI layer.
- Naming conventions respected.

### Styling and theming

- No hardcoded colours, text styles, sizes, radii, aspect ratios → the project's design tokens.

### Responsive

- Breakpoint helpers used where the layout demands it.

### Localisation

- No user-visible hardcoded strings → the project's translation call, with the keys present in
  the translation files.

## Bug classification

| Weight | Level | Tag | Definition |
|---|---|---|---|
| **10** | Critical | `[P10 Critical]` | Crash, data loss, total block |
| **7** | Major | `[P7 Major]` | Feature broken or unusable |
| **4** | Minor | `[P4 Minor]` | Works, but with defects or badly handled edge cases |
| **1** | Cosmetic | `[P1 Cosmetic]` | Copy, colours, alignment — nothing functional |

Format for each finding:

```
**[P7 Major]** `file_path:line` - description of the problem
Suggestion: how to fix it, with a code example
```

## Report format

Two blocks: the logic findings (→ DOE directives) and the non-testable ones (→ direct fixes).
Every finding keeps its tier tag so severity survives the split.

```markdown
## Changes analysed
- File list with +/- stats, grouped by kind (UI, Logic, Models, Other)

## Block A — Logic findings → DOE directives
Implemented by `/review-fix` through the test-first gate (red→green).

| Directive | Tier | Finding (`file:line`) | Problem | Suggestion |
| --- | --- | --- | --- | --- |
| `NN_review_critical.md` | P10 | `<src>/...:NN` | ... | ... |

Directives created: [list of files in `.doe/directives/`]

## Block B — Non-testable findings → direct fixes
Applied by `/review-fix` with `Edit` (outside the gate, static analysis only).

### Critical (P10)
### Major (P7)
### Minor (P4)
### Cosmetic (P1)

## Static analysis
- New errors/warnings introduced by the branch (if any)

## Verdict
- PASS: no critical problem, branch is merge-ready
- FAIL: problems to solve before merge (list the required actions)
```

## Rules

- Direct, professional tone. No emoji.
- No AI filler ("great job", "I noticed that", "make sure to").
- Every problem carries a concrete suggestion with `file:line`.
- Analyse ONLY the branch diff, not pre-existing code.
- Never publish to GitHub without explicit confirmation.
