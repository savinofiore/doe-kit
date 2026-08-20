# Adopting DOE in an existing project

Installing the kit takes a minute. Making it stick takes one honest decision about your
architecture. Both are below.

## 0. Prerequisites

- **Claude Code or Codex** (or any agent that reads project skills and supports `PreToolUse` hooks).
- **python3** on `PATH` — the guard and its self-test are Python, and the hook invokes
  `python3` directly. No packages, standard library only.
- **git** — the coverage gate diffs against a base ref.
- Your stack's toolchain (`node`/`npm`, or `flutter`/`dart`).

## 1. Install

Two paths. They install the same method; they differ in where the files live and how updates
reach you.

### One command (project-local)

```bash
cd /path/to/your/project
curl -fsSL https://raw.githubusercontent.com/savinofiore/doe-kit/main/install.sh | bash -s -- --stack web-ts
```

The script detects it is being piped, clones itself to a temp dir, installs, and cleans up. To
audit it before running — a reasonable habit for anything piped into a shell — drop the pipe:

```bash
curl -fsSL https://raw.githubusercontent.com/savinofiore/doe-kit/main/install.sh -o /tmp/doe.sh
less /tmp/doe.sh && bash /tmp/doe.sh --stack web-ts
```

It copies:

```
your-project/
├── .doe/
│   ├── README.md              # the method, in the repo, where the agent will read it
│   ├── doe.config.json        # protected roots
│   ├── directives/            # 00_*_TEMPLATE.md  (+ your NN_*.md over time)
│   └── execution/             # directive_guard.py, guard_selftest.py, run.sh, coverage.sh
├── .claude/
│   ├── settings.json          # the Claude Code PreToolUse hook (merged)
│   └── skills/                # directive, execute, doe-review, doe-review-fix, …
└── .codex/
    ├── hooks.json             # the Codex PreToolUse hook (merged)
    └── skills/                # the same DOE skills for Codex
```

Nothing under your source roots is touched, and re-running it never clobbers an existing file
without `--force`.

### As a Claude Code plugin

```
/plugin marketplace add savinofiore/doe-kit
/plugin install doe-kit@doe-kit
/doe-kit:init web-ts
```

The plugin carries the skills and the guard hook; `/doe-kit:init` scaffolds the project side
(`.doe/`). Skills are namespaced — `/doe-kit:directive`, `/doe-kit:execute 05` — which removes
the whole class of name collisions, including with bundled aliases.

Update with `/plugin marketplace update`. A private marketplace repo works too, as long as the
people installing it have git access.

**Why the guard is safe to enable globally:** a project with no `.doe/` directory is not a DOE
project, and the guard is **dormant** there — it blocks nothing. Running `/doe-kit:init` is the
opt-in; deleting `.doe/` is the opt-out. Without that rule, installing the plugin would make
every unrelated repository on your machine read-only.

### As a Codex plugin

```bash
codex plugin marketplace add https://github.com/savinofiore/doe-kit.git
codex plugin add doe-kit@doe-kit
```

Start a new task after installation. The Codex plugin provides the DOE skills; Codex does not
load plugin-scoped hooks, so use `install.sh` once per project to wire the same guard into
`.codex/hooks.json`. The guard is still dormant until `.doe/` exists.

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

For Codex it also merges this into `.codex/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "apply_patch|exec_command",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \".doe/execution/directive_guard.py\""
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

### What Claude Code and Codex do with this

**Hooks load without a restart.** Claude Code watches the settings files, so the guard is live
as soon as `install.sh` writes it. Type `/hooks` to see it listed under `PreToolUse` — that
menu is read-only, so edit `.claude/settings.json` to change anything.

Codex reads project hooks from `.codex/hooks.json`. Start a new task after changing its hook or
skill configuration. Its guard matches `apply_patch` and `exec_command`, including protected
paths inside an `apply_patch` payload and shell commands supplied as `cmd`.

**Skills are project-scoped.** They land in `.claude/skills/<name>/SKILL.md`, so they exist in
this repo and nowhere else. Two ways they run:

- you type `/directive`, `/execute 05`, `/doe-review` — explicit invocation;
- Claude loads one on its own when your request matches its `description`. That is why every
  skill here has a description written as trigger conditions rather than a summary.

The skill bodies cost nothing until they load, so having a dozen-plus of them installed does not
tax the context window.

**Names are chosen to avoid collisions.** Precedence in Claude Code is enterprise → personal →
project, and a skill at any level overrides a *bundled* skill of the same name **but never a
bundled alias**. `/review` is the bundled alias for `/code-review`, so a project skill called
`review` would be shadowed when typed — silently. Hence `doe-review` and `doe-review-fix`. If
you rename them in your own copy, check the name against the bundled list first, and prefer a
prefix.

**A personal skill wins over a project one.** If you keep something in `~/.claude/skills/` with
a name this kit also uses, yours wins and the DOE one never runs. Rename one of the two.

### First run

Ask the agent to change something under a protected root. Expected: the write is denied, the
guard's message comes back, and the interview starts. If the agent edits the file instead, the
hook is not wired — check `/hooks` and the `--status` output above.

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

## 6. Add it to AGENTS.md or CLAUDE.md

The guard blocks the write, but the agent works better when it knows why. Add this to your
project's `AGENTS.md` (or `CLAUDE.md`):

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
