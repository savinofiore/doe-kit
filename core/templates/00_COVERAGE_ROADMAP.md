# ROADMAP — closing the coverage gate on `[branch]`

> **Not a directive.** The `00_` prefix keeps it out of the directive-guard: it carries no
> `STATE`, it unlocks nothing, `/execute` never runs it. It is the map that holds a series of
> numbered directives together — one long push to get `coverage.sh` green.
>
> Copy this file to `.doe/directives/00_COVERAGE_ROADMAP.md`, keep it updated as each
> directive closes, and **delete it when the last one closes**. A roadmap nobody updates is
> worse than none: it reads as a plan while describing a repository that no longer exists.

## Why this file exists

`coverage.sh` applies the threshold to the files **in the diff against the base ref**, not to
a fixed list. That has one consequence worth writing down before starting:

> **Green is not inheritable.** Every directive that touches the source root pulls new files
> into the diff and can turn the gate red where it was green. A roadmap that says "directive
> NN closes the coverage gate" is wrong the moment NN+1 exists. The gate is **measured** at
> the start of each directive, never inherited from the last one.

## Baseline — measured [YYYY-MM-DD]

Fill this in by running `.doe/execution/coverage.sh` on a clean tree. Numbers that were
copied from a previous document instead of measured are how a roadmap starts lying.

| metric | initial | after NN | after NN |
|---|---|---|---|
| suite | [N tests], `run.sh` [GREEN/RED] | | |
| coverage on the gate perimeter | [X%] — [hit]/[total] | | |
| global coverage | [X%] | | |
| files in the perimeter with zero coverage | [N] | | |
| files never imported by any test | [N] | | |
| `coverage.sh` | [GREEN / RED on N files] | | |

> If the perimeter KPI and the global number diverge a lot, say why in one line — usually the
> excluded layer (views, widgets, generated code) dominates the global figure. Name which of
> the two is the number being steered, so nobody reports the flattering one.

## Perimeter — what the gate does not measure, and why

Copied from `SKIP_PATTERNS` in `coverage.sh`, with the reason for each. This section exists so
the skip-list is reviewable in prose, not only in a shell array.

| pattern | reason it cannot be unit-tested |
|---|---|
| `[path fragment]` | [why a deterministic offline test cannot reach it] |

Anything on this list that could be tested after a small refactor belongs in the backlog
below instead — as a directive that moves the logic out, not as a permanent exclusion.

## Backlog — one row per planned directive

| # | scope | why it is red today | directive | status |
|---|---|---|---|---|
| 1 | `[file or module]` | [no test / N% / never imported] | `NN_name.md` | open / approved / closed |

Rules for this table:

- **One directive per coherent slice**, not one per file. A directive that touches thirty
  unrelated files cannot be reviewed, and an unreviewed directive is an unapproved one.
- **Ordered by dependency**, not by size. A module whose tests need a fixture that does not
  exist yet comes after the directive that creates it.
- A row moves to `closed` only when `run.sh` **and** `coverage.sh` are green with it merged —
  not when the tests are written.

## Residual red — measured [YYYY-MM-DD]

The output of the last `coverage.sh` run, file by file. Re-measure before writing the next
directive; do not carry this section forward untouched.

| file | coverage | outcome |
|---|---|---|
| `[path]` | [X% (hit/total)] | [closed by NN / open / excluded — reason] |

## Closing

When `coverage.sh` is green and the backlog is empty: delete this file. The gate stays; the
map does not.
