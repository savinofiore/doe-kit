# The coverage gate

`run.sh` is the fast gate for the red→green loop. `coverage.sh` is the full gate that runs in
CI: it adds a coverage threshold (default **80%**) on **every changed file**, measured against
a base ref.

A changed logic file with no test is red.

```bash
.doe/execution/coverage.sh                       # 80% threshold vs the default base
DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh   # custom threshold
DOE_BASE_REF=develop .doe/execution/coverage.sh  # custom diff base
```

## Why per-file, not global

Global coverage is a number that goes up when someone tests something easy. It says nothing
about the change in front of you.

The gate measures **what this directive touched**. That has two consequences worth stating:

- A repo at 15% global coverage can adopt the gate today. It does not demand a retroactive
  test-writing project — it demands that new work arrives covered.
- Coverage cannot be gamed by adding tests somewhere cheap. The only way to make the gate
  green is to test the file you changed.

The diff is taken against the **merge-base** with the base ref, not against its tip. Otherwise
an advance on `main` would drag other people's files into your directive's diff.

## Deleted files

A deleted file shows up in `git diff --name-only` but has no lcov record. It used to land in
the "no coverage" branch and **failed the gate on every dead-code removal** — a gate that
punishes cleanup teaches people not to clean up.

Deleted files now leave the calculation by construction: they have no lines to cover.

- committed deletion → `git diff --diff-filter=d`;
- absent from the working tree → logged as `⊘ skip (absent from the working tree)`.

## The skip-list

A file enters the skip-list because it is **not testable with deterministic offline unit
tests**, never because excluding it is convenient.

Excluded files are **logged** with `⊘ skip (reason)`, and the report closes with
`N measured, M excluded`. This matters more than it sounds:

> An invisible skip-list turns the gate into theatre.

If you cannot see what was excluded, a green gate stops meaning anything, and the list grows
quietly until it covers everything that was ever inconvenient.

Typical entries (adapt them to your stack):

| pattern | reason |
|---|---|
| the widget/component layer | extract the logic into a testable layer and test it there; the view itself, no |
| design tokens | no branch to cover |
| animations / transitions | need a rendered tree |
| native channels, platform plugins | do not exist off-device |
| abstract interfaces and typedefs | no body to execute |
| routing builders holding a context | need a rendered tree |
| static-const-only files | zero executable lines, so no lcov record is possible even when imported by tested code |

Two rules keep it honest:

1. **Single-file exclusions use the full path**, not the directory prefix. Excluding one file
   inside `src/api/` must not silently dismantle the whole measured folder.
2. **The skip-list must not swallow gate-eligible code.** Repositories, models, state,
   utilities stay measured, and under threshold they still go red. Every addition needs a
   written justification, otherwise the gate stops biting where it matters.

## The keep-list — the exception to the exception

Pure logic living inside an excluded folder **stays measured**. The keep-list wins over the
skip-list and can only make the gate **stricter**, never more permissive.

A file qualifies when it has no dependency on the view layer, on a rendering context, or on a
platform plugin — a markdown parser sitting in a components folder, an enum with a mapping, a
set of exception classes.

The report says how many: `of which N inside excluded folders but measured via keep-list`.

## The KPI to actually look at

On a mature app the global lcov total is dominated by the view layer that sits outside the
perimeter — often 15,000–20,000 lines of it. That number is not the one that measures the
gate's work, and reading it as a failure is how teams talk themselves out of the whole
exercise.

The gate prints both, and labels which is which:

```
▶ non-widget KPI (gate perimeter): 4290/8274 = 51.8%
  global lcov: 4388/29144 = 15.1% (includes the view layer outside the perimeter: not the number to watch)
```

The perimeter KPI is the honest one. The global one is printed so nobody has to wonder whether
it was hidden.
