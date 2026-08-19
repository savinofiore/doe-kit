# Stacks

A stack adapter is small on purpose. The method, the templates, the guard and the skills are
stack-agnostic; a stack only has to answer two questions:

1. **What is the gate?** → `execution/run.sh`, exit 0 or non-zero.
2. **What counts as covered?** → `execution/coverage.sh`.

| Stack | Gate | Protected roots |
|---|---|---|
| [`web-ts`](web-ts/) | `tsc --noEmit` + `eslint` + `vitest run` | `src/`, `tests/` |
| [`flutter`](flutter/) | `flutter analyze` + `flutter test` | `lib/`, `test/` |
| [`shared`](shared/) | — (convention skills only, installed with every stack) | — |

## Adding a stack

```
stacks/<name>/
├── README.md            must contain a "## Gate" section — the installer copies it into .doe/README.md
├── execution/
│   ├── run.sh           fast gate: static analysis + lint + unit suite
│   └── coverage.sh      full gate: + per-file coverage threshold on changed files
└── skills/              optional: stack-specific convention skills
```

Then add the protected roots to the `case` in `install.sh`, and to the auto-detection in
`core/execution/directive_guard.py` if the stack has an unambiguous marker file.

### What `run.sh` must guarantee

- **Exit 0 if and only if everything passes.** The gate is the only judge of "done"; an exit
  code that lies is worse than no gate.
- **Deterministic and offline.** No network, no real database, no device, no wall-clock
  dependence. A flaky gate gets re-run until it is green, which is the same as not having one.
- **Fast enough to run in the red→green loop.** If the full gate is slow, give it a
  `--quick`-style flag that skips the slowest non-essential step (lint, usually), and keep the
  full run for CI.
- **Narrowable by path**, so the RED step of a directive can be checked in seconds.

### What `coverage.sh` must guarantee

- Coverage measured **per changed file** against the merge-base with the base ref, not
  globally. This is what makes the gate adoptable on a repo with low coverage today.
- Every exclusion **logged with its reason**. Silent skips make a green gate meaningless.
- **Red when it cannot evaluate** — a missing base ref or a missing coverage report must fail,
  never pass quietly.

## Language-agnostic sketch

Any language works if it can answer the two questions. A Python stack, for instance:

```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"

FAILED=()
step() { local l="$1"; shift; if "$@"; then echo "✓ $l"; else echo "✗ $l"; FAILED+=("$l"); fi; }

step "typecheck" mypy src
step "lint"      ruff check .
step "test"      pytest -q "$@"

[[ ${#FAILED[@]} -eq 0 ]] && { echo "GATE GREEN"; exit 0; }
echo "GATE RED — failed: ${FAILED[*]}"; exit 1
```

That is the whole contract.
