---
name: delta-check
description: Read-only pre-commit/pre-PR check on the branch delta (git diff base...HEAD) — lists touched files, flags convention violations on the changed lines only, and confirms static analysis is clean. Reports, never fixes. Use before committing or opening a PR.
---

# Delta Check — what the branch actually changed

A focused check on the **delta** of the branch (only what changed vs the base), not on the
whole codebase. Meant as a gate before a commit or a PR.

## When to use it

- "Check my branch before I commit"
- "Verify the diff vs develop"
- "What did I touch, and are there violations?"
- Pre-PR self-review.

**NOT for:**

- Applying fixes → the stack's auto-fix skill (lint) or style-fix skill (conventions).
- A full review with a PR comment → the `review` skill.

## Flow

### Step 1 — Determine the delta files

```bash
git rev-parse --abbrev-ref HEAD          # current branch
git diff <base>...HEAD --name-only       # files touched vs base
git diff <base>...HEAD --stat            # size of the change
```

Consider only those files. Read the changed lines with:

```bash
git diff <base>...HEAD -- <file>
```

### Step 2 — Check the project conventions on the changed lines

On the diff only, not on the whole file. Look for the violations your project actually cares
about — keep this list in sync with the project's `CLAUDE.md`:

- Hardcoded colours / sizes / text styles / radii → the design tokens.
- Hardcoded user-visible strings → the translation call.
- Direct mutation of a state collection → the immutable pattern.
- New dependency not registered where the project requires it.
- Missing route/path constant.

Targeted greps, limited to the delta files, are usually enough:

```bash
git diff <base>...HEAD -- '*.<ext>' | grep -nE '<pattern1>|<pattern2>'
```

### Step 3 — Clean analysis

Run the project's static analysis on the delta files. Confirm zero errors/warnings introduced
by the branch.

### Step 4 — Report

```
Branch: feature/XXXX-...
Files touched: N

✓ static analysis clean
Convention violations (on the diff):
  <src>/pages/x/x_page:88    hardcoded colour → design token
  <src>/state/x_state:40      direct mutation of state.items → immutable copy

Suggested: <auto-fix skill> for lint, <style-fix skill> for conventions.
```

## Rules

- **Read-only**: this skill never modifies code, it analyses and reports.
- Limit every check to the `<base>...HEAD` diff; ignore untouched pre-existing code.
- Every violation must carry `file:line` and the concrete correction.
- Do not report formatting nits — the formatter owns those.
