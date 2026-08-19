# Adopting DOE in an existing project

Installing the kit takes a minute. Making it stick takes one honest decision about your
architecture. Both are below.

## 1. Install

```bash
git clone https://github.com/<you>/doe-kit.git /tmp/doe-kit
/tmp/doe-kit/install.sh --stack web-ts /path/to/your/project
```

Stacks available: `web-ts` (TypeScript + Vitest), `flutter` (Dart + flutter test).

The installer copies:

```
your-project/
├── .doe/
│   ├── README.md              # the method, in the repo, where the agent will read it
│   ├── doe.config.json        # protected roots
│   ├── directives/            # 00_*_TEMPLATE.md  (+ your NN_*.md over time)
│   └── execution/             # directive_guard.py, guard_selftest.py, run.sh, coverage.sh
└── .claude/
    ├── settings.json          # the PreToolUse hook (merged, never overwritten blindly)
    └── skills/                # directive, execute, review, review-fix, …
```

Nothing under your source roots is touched.

## 2. Set the protected roots

`.doe/doe.config.json`:

```json
{ "protected_roots": ["src", "tests"] }
```

These are the directories the guard makes read-only until a directive is approved. Pick the
ones that hold production code and tests — not config, not docs, not migrations. The directive
itself must stay writable while the guard is armed, which is why `.doe/` is never protected.

## 3. Wire the hook

The installer merges this into `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.doe/execution/directive_guard.py\""
          }
        ]
      }
    ]
  }
}
```

Verify it:

```bash
.doe/execution/directive_guard.py --status      # should say: GUARD: ARMED
.doe/execution/guard_selftest.py                # should say: no false positives, no false negatives
```

## 4. Make the gate real

`run.sh` ships with sensible defaults for the stack, but it has to match your project:

- the typecheck/analysis command,
- the lint command,
- the test command and the test directory,
- for `coverage.sh`: the base ref (`main` vs `develop`) and the skip/keep lists.

Run it once on a clean tree. **If it is not green before you start, fix that first** — a gate
that is red for unrelated reasons is a gate people learn to ignore.

## 5. The honest decision

DOE's gate only sees code that a deterministic offline unit test can reach. If your business
logic lives inside components, hooks, widgets or route handlers, the gate will see almost
nothing, and you will be tempted to widen the skip-list until it is green and meaningless.

The fix is the same in every stack: **business logic goes in a framework-free layer and gets
imported.** The view layer stays thin.

```
src/core/          ← models, services, repositories, utils   → measured, gated
src/app/           ← routes, pages                            → thin, exempt
src/components/    ← view                                     → thin, exempt
```

You do not have to migrate everything on day one. New work goes in the core layer; old code
moves when you touch it. The coverage gate only measures *changed* files, so this works
incrementally by construction.

## 6. Add it to CLAUDE.md

The guard blocks the write, but the agent works better when it knows why. Add this to your
project's `CLAUDE.md`:

```markdown
## Process — DOE (mandatory)

No code change without an approved directive. See `.doe/README.md`.

- Change requested → `/directive` (interview → `.doe/directives/NN_name.md`, STATE: DRAFT, zero code)
- Human approval → `STATE: APPROVED` set by hand
- `/execute NN` → RED → fix → green gate → delete the directive
- A red test means the code is wrong, never the test.
```

## 7. Turn on CI

See [enforcement.md](enforcement.md) for a ready-made GitHub Actions workflow. Two rules:

- `fetch-depth: 0`, otherwise the coverage gate has no base ref and fails red for safety.
- Run `guard_selftest.py` in the same job. It is the only thing that tells you the guard is
  still guarding.

---

## Rollout that works

1. **Week 1 — gate only.** Install `run.sh`, get it green, wire CI. No guard yet. This alone
   catches the "done!" problem.
2. **Week 2 — coverage gate.** Turn on `coverage.sh` with the threshold at 80% on changed
   files. Expect to argue with the skip-list once; log every exclusion.
3. **Week 3 — the guard.** Arm it. The first day is annoying, and then it is not: the
   interview is faster than the rework it replaces.

Adopting the guard first, before the gate is trustworthy, is how the whole thing gets
uninstalled by Friday.

## When not to use this

- Throwaway prototypes and spikes. The round-trip cost is real and buys nothing there.
- Code with no test story at all (pure glue, generated clients). Gate what has logic; leave the
  rest out and say so in the skip-list.
- Solo exploratory work where you *want* the agent running ahead of you. Use `DOE_BYPASS=1`,
  and know that you turned it off.
