# Stack — python

Gate and conventions for a Python project: `ruff` for lint, `mypy` for types, `pytest` for
the suite. Nothing here assumes a web framework; a library, a CLI and a service all use the
same two scripts.

## Gate

```bash
.doe/execution/run.sh                    # mypy + ruff + pytest
.doe/execution/run.sh tests/core         # narrow to a path
.doe/execution/run.sh --name "discount"  # filter by test name (pytest -k)
.doe/execution/run.sh --quick            # skip mypy + ruff, keep the suite
.doe/execution/coverage.sh               # the full gate, the one CI runs
```

A directive is done **if and only if `run.sh` exits 0**. Not when the agent says so, not
when the diff looks right.

`--quick` exists for the red→green loop only. The step it skips is a step the full gate
still runs, so nothing merges unchecked.

If a tool is missing the gate goes **red**, it does not skip the step. A gate that quietly
drops the check it cannot run reports green on unchecked code.

## Test scope

The gate measures deterministic, offline unit tests. That means no network, no real
database, no wall clock, no filesystem outside `tmp_path`. Anything needing a live
dependency belongs in an integration suite outside the gate — a flaky gate gets re-run
until it is green, which is the same as not having one.

`SKIP_PATTERNS` in `coverage.sh` lists what is out of perimeter — migrations, `__main__.py`,
`conftest.py` by default. Every exclusion is printed with its reason on every run. Add to it
only when a file genuinely cannot be reached by a unit test, and say why in the pattern.

## The coverage gate

`coverage.sh` applies the threshold (default 80%) to each source file **changed against the
base ref**, not to the repo total. A codebase at 20% global coverage can adopt this today:
the rule is not "go back and test everything", it is "new work arrives covered".

A changed file absent from the coverage report is red, not skipped — never imported by a
test is the failure the gate exists to catch.

```bash
DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh   # stricter threshold
DOE_BASE_REF=develop .doe/execution/coverage.sh  # different base branch
DOE_SRC_DIR=mypkg    .doe/execution/coverage.sh  # package not under src/
```

## Architecture constraints the generated code must respect

- **Business logic outside the entry points.** Logic living inside a Click command, a
  FastAPI route or a Django view is unreachable by the gate. Put it in a module the test
  can import and call directly, and keep the entry point a thin adapter.
- **I/O at the edges.** A function that both computes and writes is two functions. The
  computing one is the one the gate can hold to a threshold.
- **Typed public surface.** `mypy` is part of the gate: a new public function without
  annotations fails it. `Any` at a real boundary is fine when it is deliberate and named.

## Recommended permissions

```json
{
  "permissions": {
    "allow": ["Bash(pytest:*)", "Bash(ruff:*)", "Bash(mypy:*)", "Bash(.doe/execution/run.sh:*)"]
  }
}
```
