---
name: port-commits
description: Port commits between branches with an enumerate-then-verify pattern. A pre-flight file enumeration plus a post-flight coverage check make silently skipped files impossible. Use when porting changes from an outdated or diverged branch.
---

# Port Commits — enumerate, then verify

## Expected input

- `SOURCE_BRANCH` (or an explicit list of commit SHAs)
- `TARGET_BRANCH` (default: current branch)
- Optional: an explicit list of files to exclude

## Workflow

### Step 1 — Enumerate

List EVERY file touched by the source commits:

```bash
git show --name-only --format="" <COMMIT1> <COMMIT2> ... | sort -u
```

or, for a range:

```bash
git diff --name-only <SOURCE_BASE>..<SOURCE_HEAD> | sort -u
```

Produce a markdown table:

```
| # | File | Source commit(s) | Status on target (exists / missing / different) |
```

Show the table and ask for confirmation before proceeding.

### Step 2 — Plan

For each file, decide the action:

- **`port-as-is`** — copy the content from the source.
- **`adapt`** — the source is outdated; it needs adapting to current conventions (new imports,
  renamed APIs, new patterns).
- **`skip-with-reason`** — not applicable on the target (already refactored differently,
  intentionally deleted).

Output: the Step 1 table plus an `Action` column and `Reason (if skip)`.

Show the full plan and wait for explicit confirmation before Step 3.

### Step 3 — Execute

Apply commit by commit, atomically. For each source commit:

1. Apply the files (`Edit`/`Write` per the planned action).
2. Run the project's static analysis.
3. If it fails:
   - Do NOT move to the next commit.
   - Roll back the partial changes (`git restore <files>`).
   - Report and ask for instructions.
4. Atomic commit, referencing the ticket (when present) and the source commit:

   ```
   <TICKET> <description> (port of <SHORT_SHA>)
   ```

### Step 4 — Coverage check

Verify every source file was handled:

```bash
git diff --name-only <SOURCE_BASE>..<SOURCE_HEAD> | sort -u > /tmp/source_files.txt
git diff --name-only <TARGET_START_SHA>..HEAD | sort -u > /tmp/target_files.txt
comm -23 /tmp/source_files.txt /tmp/target_files.txt
```

Files in the `comm -23` output are **source files with no counterpart on target**.

For each one:

- Was it `skip-with-reason`? → fine, ignore.
- Otherwise → THE PORT IS INCOMPLETE, back to Step 3.

Do not continue until `comm -23` returns only files marked `skip-with-reason`.

### Step 5 — Final report

Mandatory closing table:

```
| # | Source file | Action taken | Target commit SHA | Analysis status |
```

Plus:

- Total source file count.
- Ported / adapted / skipped counts.
- Final static analysis output (clean, or filtered to pre-existing issues only).

## RULES (STRICT)

- **Never** declare the port complete without the Step 4 coverage check.
- **Never** skip a file without a written reason in the table.
- **Never** merge several source commits into one target commit (atomicity).
- Clean static analysis on every commit is a closing condition.
- If the user interrupts, leave the tree in a consistent state (no dangling partial changes).

## The failure pattern this prevents

A port once silently skipped 9 files and needed a second pass after the user noticed. This
skill exists to make that impossible: the Step 1 enumeration and the Step 4 coverage check are
the two gates that prevent silent skipping.
