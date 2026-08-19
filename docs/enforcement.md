# Enforcement — the guard and the gate

DOE has two enforcement points. They protect against different failure modes and neither
replaces the other.

| | directive-guard | gate (`run.sh` / `coverage.sh`) |
|---|---|---|
| Runs | locally, on every write attempt | on demand, and in CI |
| Prevents | writing code without an approved spec | declaring done what does not pass |
| Failure mode it catches | process bypass | false completion |
| Where it lives | `.doe/execution/directive_guard.py` | `.doe/execution/*.sh` |

---

## Local enforcement — the directive-guard

`.doe/execution/directive_guard.py` is a `PreToolUse` hook wired in `.claude/settings.json`.
It closes **two** write paths into the protected roots:

1. **The write tools** — `Edit`/`Write`/`MultiEdit`/`NotebookEdit`: blocked when `file_path`
   is under a protected root.
2. **Bash commands that write** — redirections (`> file`, `>> file`), `tee`, `sed -i`,
   `cp`/`mv`/`rm`/`touch`, `git apply`, interpreter one-liners with a write verb.

Path 2 exists for a concrete case: regenerating database types is
`npx supabase gen types … > src/types/database.ts` — a write into `src/` that goes through no
Edit tool at all. Without the Bash guard, the entire process is bypassed by a redirection.

In both cases the block only fires when `.doe/directives/` holds no non-template directive
with `STATE: APPROVED`. Outside the protected roots (docs, `.doe/`, config, migrations)
nothing is blocked — the directive itself has to be writable while the guard is armed.

### What it deliberately does NOT block

Reads (`cat`, `grep`, `ls`, `find`), the gate, the tests, `git status`/`diff`/`checkout`/
`reset`, and redirections to unprotected paths (`> /tmp/x`, `2>&1`).

This is a design decision, not an oversight. **A guard that blocks `grep` gets disabled within
the hour, and a disabled guard protects nothing.** Every false positive is a withdrawal from
the same account.

The command analysis is heuristic, not a shell parser: it catches the constructs people
actually use. It exists to stop the process being bypassed by *inattention* — anyone who wants
to bypass it on purpose already has `DOE_BYPASS`, which at least is explicit and visible.

### Configuration

`.doe/doe.config.json` at the repo root:

```json
{ "protected_roots": ["src", "tests"] }
```

Fallback order: config file → `DOE_PROTECTED_ROOTS` (comma-separated) → auto-detection
(`lib` + `test` when a `pubspec.yaml` exists, otherwise `src` + `tests`).

### Lifecycle

- **Unlock:** directive written + `STATE: APPROVED` set by hand.
- **Re-arm:** at L3 cleanup the directive is deleted → no APPROVED left → the guard is armed
  again. The safe state is the default state.
- **Emergency escape** (outside the process): `export DOE_BYPASS=1`.

### Diagnostics without going through the agent

```bash
.doe/execution/directive_guard.py --status              # is it blocked? why?
.doe/execution/directive_guard.py --explain '<command>' # how does it read this Bash command?
.doe/execution/guard_selftest.py                        # does the guard still work?
```

---

## The self-test, and why it is not optional

The guard is the only piece of the system that, when it breaks, **turns nothing red**. It just
stops protecting, silently, and nobody notices until it is far too late.

`guard_selftest.py` is its regression suite. It covers both directions of error:

- **FALSE NEGATIVE** — a write gets through: the process can be bypassed unnoticed.
- **FALSE POSITIVE** — legitimate work is blocked: the guard becomes unbearable, someone
  switches it off, and from then on it protects nothing.

The second is the dangerous one, which is why roughly half the cases in the suite are ALLOW
cases: reads, `git status`, `npm test`, redirections to `/tmp`, `2>&1`.

The self-test runs at two levels:

- **Level 1 — detection.** Pure functions, always run, regardless of directive state. This is
  what makes the suite non-vacuous by construction.
- **Level 2 — end-to-end wiring.** Only meaningful while the guard is armed; when an APPROVED
  directive is active this level is skipped **and says so**, instead of exiting 0 in silence.

That distinction was learned the hard way: an earlier version re-implemented the `STATE:`
parsing inside the test, a substring search matched `STATE: APPROVED` inside the instructions
at the top of a DRAFT directive, and the self-test skipped itself and exited green. A false
green in the test that exists to prevent false greens.

---

## CI enforcement

The gate belongs in CI, not only in a local habit. A workflow runs `coverage.sh` (static
analysis + tests + coverage threshold) on every push/PR and fails the build when the gate is
red.

Run `guard_selftest.py` in the same workflow. It costs a second and it is the only thing that
tells you the guard is still guarding.

Example (GitHub Actions):

```yaml
name: DOE gate
on: [push, pull_request]

jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # the coverage gate diffs against the base ref
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: .doe/execution/guard_selftest.py
      - run: .doe/execution/coverage.sh
        env:
          DOE_BASE_REF: ${{ github.base_ref || 'main' }}
```

`fetch-depth: 0` is not optional: the coverage gate compares against the merge-base with the
target branch, and a shallow clone has no base ref to compare with. When the base ref cannot
be resolved the check fails **red for safety** rather than passing quietly — an
unevaluated gate that reports green is worse than no gate.
