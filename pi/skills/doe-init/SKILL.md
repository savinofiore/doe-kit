---
name: doe-init
description: Set up DOE in the current project — creates .doe/ with the directive templates, the gate scripts for the chosen stack, and the config the guard reads. Run once per project, after installing the doe-kit plugin. Use when the user says "set up DOE", "doe init", or the guard reports it is dormant.
---

> **Pi:** invoke this skill with `/skill:doe-init`.


# Init — opt this project into DOE

Creates the project side of DOE. The plugin provides the skills; this scaffolds what has to
live in the repository, because it is project-specific and belongs in version control.

Invocation: `/doe-kit:init <stack>` — e.g. `/doe-kit:init flutter`. With no argument, ask.

## Why this step exists at all

The guard is **dormant in any project without a `.doe/` directory**. That is deliberate: the
plugin is enabled globally, and a guard that armed itself everywhere would make every unrelated
repository read-only the moment someone installed it.

So `.doe/` is the opt-in. Creating it arms a configured guard for this project and nothing else.

On Codex, use the project-local installer first because Codex plugins package skills but not
plugin-scoped hooks:

```bash
curl -fsSL https://raw.githubusercontent.com/savinofiore/doe-kit/main/install.sh | bash -s -- --stack <stack>
```

It creates `.doe/`, installs `.codex/skills/`, and merges the guard into `.codex/hooks.json`.

## Step 1 — Determine the stack

The stacks are not a list held in this skill. Each one describes itself in
`stacks/<name>/stack.json`, and that descriptor is the only place a stack is defined — so
this list is always the real one, however many have been added since:

```bash
python3 - "$CLAUDE_PLUGIN_ROOT"/stacks/*/stack.json <<'EOF'
import json, sys
for path in sys.argv[1:]:
    d = json.load(open(path))
    print(f"{d['name']:<10} {d['label']:<38} "
          f"markers: {', '.join(d['markers']):<26} roots: {', '.join(d['protected_roots'])}")
EOF
```

Match the repository against the `markers` of each descriptor, then **ask the user to
confirm**. If nothing matches, see "Unsupported stack" below.

Never guess silently. The stack decides the protected roots, and getting those wrong either
leaves the code unguarded or blocks the wrong directory.

## Step 2 — Copy the kit's project files

For Claude Code, everything comes from the plugin directory, `${CLAUDE_PLUGIN_ROOT}`:

```bash
mkdir -p .doe/directives .doe/execution

cp "$CLAUDE_PLUGIN_ROOT"/core/execution/directive_guard.py .doe/execution/
cp "$CLAUDE_PLUGIN_ROOT"/core/execution/guard_selftest.py  .doe/execution/
cp "$CLAUDE_PLUGIN_ROOT"/stacks/<stack>/execution/*        .doe/execution/
cp "$CLAUDE_PLUGIN_ROOT"/core/templates/00_*.md            .doe/directives/
chmod +x .doe/execution/*
```

The guard is copied into the project as well as living in the plugin. That is on purpose: the
plugin's copy runs as the hook, and the project's copy is what `--status`, `--explain` and the
self-test use — and what keeps working for a teammate who has not installed the plugin but
wires the hook through `.claude/settings.json` instead.

Then the method doc, so the process is readable inside the repo:

```bash
cp "$CLAUDE_PLUGIN_ROOT"/docs/methodology.md .doe/README.md
```

## Step 3 — Write the config

`.doe/doe.config.json` — the protected roots. Copy them out of the descriptor rather than
typing them, so this file and the stack can never disagree:

```bash
python3 - "$CLAUDE_PLUGIN_ROOT/stacks/<stack>/stack.json" <<'EOF'
import json, sys
roots = json.load(open(sys.argv[1]))["protected_roots"]
with open(".doe/doe.config.json", "w") as f:
    json.dump({"protected_roots": roots}, f, indent=2)
    f.write("\n")
print("protected_roots:", roots)
EOF
```

These must be the directories holding production code and tests. Never include `.doe/`
itself: the directive has to stay writable while the guard is armed.

When the descriptor says `"conventions": true`, the stack also ships a conventions template
that its skills read instead of hardcoding a design system — copy it:

```bash
cp "$CLAUDE_PLUGIN_ROOT"/stacks/<stack>/conventions.example.json .doe/conventions.example.json
```

Do **not** create `.doe/conventions.json` yourself. The skills that need it refuse to run
without it, and a config full of another project's token names produces fixes that compile
and are wrong. Tell the user to copy and fill it.

## Step 4 — Check the gate

Read `.doe/execution/run.sh` with the user and adjust the commands to this project (test
runner, lint, typecheck, test directory). Then run it.

**It must be green on a clean tree before anything is armed.** A gate that is red for unrelated
reasons is a gate people learn to ignore, and after that the whole system is decoration.

If it is red, stop here and fix that first. Do not proceed to step 5.

## Step 5 — Verify the guard

```bash
.doe/execution/directive_guard.py --status     # GUARD: ARMED
.doe/execution/guard_selftest.py               # no false positives, no false negatives
```

`DORMANT` at this point means `.doe/` was not created where the project root is — check the
working directory.

## Step 6 — Tell the project about the process

Append to `AGENTS.md` for Codex or `CLAUDE.md` for Claude Code (create it if absent):

```markdown
## Process — DOE (mandatory)

No code change without an approved directive. See `.doe/README.md`.

- Change requested → `/doe-kit:directive` (interview → `.doe/directives/NN_name.md`, STATE: DRAFT, zero code)
- Human approval → `STATE: APPROVED` set by hand
- `/doe-kit:execute NN` → RED → fix → green gate → delete the directive
- A red test means the code is wrong, never the test.
```

## Step 7 — Report

Tell the user, concretely:

- what was created;
- the protected roots now in force;
- whether the gate is green;
- what is still on them: adjust `run.sh` if needed, fill `conventions.json` when the stack
  ships one, turn on
  CI (`docs/enforcement.md` has the workflow), and commit `.doe/` — it belongs in the repo, it
  is the process, not a local preference.

Then the first real instruction:

> *"Ask me to change something under `<roots>`. The write will be refused and the directive
> interview will start. That refusal is the system working."*

## Unsupported stack

If no descriptor matches, do not fake it. Say what is missing — a `stack.json`, a `run.sh`
and a `coverage.sh` for that toolchain — and offer to write them, using
`${CLAUDE_PLUGIN_ROOT}/stacks/README.md` as the contract:

- exit 0 if and only if everything passes;
- deterministic and offline;
- narrowable by path;
- coverage measured per changed file, every exclusion logged.

Everything else in the kit is stack-agnostic and works as soon as those two scripts exist.

## RULES

- **Never overwrite** an existing `.doe/` file without asking. A project mid-directive would
  lose it.
- **Never pre-fill** `conventions.json`.
- **Never arm the guard on a red gate.**
- **Never add `.doe/` to `.gitignore`.** The process is shared or it is nothing; only
  `.test/reports/` and coverage output stay local.
