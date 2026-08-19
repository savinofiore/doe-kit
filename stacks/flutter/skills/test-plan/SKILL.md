---
name: test-plan
description: Generate a flat manual-test checklist for the current branch by analysing the git diff against the base. Writes an editable markdown file to .test/<branch>.md with tests grouped by feature. Does NOT execute anything — use test-run for that.
---

# Test Plan — the checklist the gate cannot write

Analyses the current branch against the base and produces a **flat checklist of manual tests**
grouped by feature. Each line is one pass/fail test.

This lives deliberately outside the DOE gate. The gate covers deterministic offline unit tests;
navigation, layout and real-device behaviour are not that, and a gate that includes
non-deterministic checks is one people learn to re-run until it goes green.

## Optional inputs

- `output=<path>` — output file (default: `.test/<current-branch>.md`)
- `append` — add to the file instead of overwriting it
- `base=<ref>` — comparison base (default: the project's integration branch)

## Workflow

### Step 1 — Collect metadata

```bash
BRANCH=$(git branch --show-current)
git log <base>.."$BRANCH" --oneline
git diff <base>..."$BRANCH" --stat
```

### Step 2 — Identify impacted features

Filter the user-facing changed files and group them by feature area:

```bash
git diff <base>..."$BRANCH" --name-only | grep -E '^lib/(pages|components|route|animations)/'
git diff <base>..."$BRANCH" --name-only | grep -E 'assets/translations/'
```

Group by the repo's own structure (`lib/pages/<feature>/` → feature). Ignore purely internal
changes (models, utils, repositories with no visible UX impact) — those are the gate's job.

### Step 2.5 — Inspect the real UI before naming it (MANDATORY)

**Never invent the name of a menu entry, tab, button or page.** If a test cites a visible
element, read the code that defines it first:

```bash
grep -rn "BottomNavigationBar\|NavigationBar\|NavigationDestination" lib/pages/home/ lib/components/
grep -rn "TabBar\|AppBar(" lib/pages/<feature>/
```

Open the file and copy the **exact** visible strings. If a label comes from a translation call,
resolve the key in the translation file. If the diff does not touch navigation, **do not
generate navigation tests** — no speculative "regressions".

> Real case this exists to prevent: a run once wrote "Bottom nav: Home, Academy, Courses,
> Profile" while the real UI showed five different entries. A fabricated checklist is worse
> than no checklist, because someone will tick it.

### Step 2.6 — Ask about external preconditions before generating

Ask once, structured:

1. **Login/logout**: "Do you want login/logout tests? If yes, give me test credentials or a
   test-account tag. If not, I will omit them."
2. **User state**: "Has the test account completed onboarding? Does it have in-progress data?"
   (decides whether tests assume a virgin or a populated state)
3. **Flavor**: confirm which build flavor.

If the user skips point 1, **do not generate login/logout tests**. If they want them but give
no credentials, tag them `- [ ] (requires credentials) ...` so `test-run` skips them without
prompting mid-run.

### Step 3 — Generate the checklist

Create `.test/<branch>.md`:

```markdown
# Test Plan - <branch-name>

**Base**: <base> (`<base-sha>`) | **Head**: `<head-sha>` | **Generated**: <YYYY-MM-DD>
**Device**: _to fill in_ | **Flavor**: <flavor>

---

## <Feature A>

- [ ] From the home, tapping "<exact label>" opens the <X> list
- [ ] Tapping a card opens the detail page with title and description
- [ ] Tapping the heart icon top-right toggles its state (filled <-> empty)
- [ ] Back from the detail page returns to the list without a crash
- [ ] A completed item shows the "<exact badge text>" badge on its card

## <Feature B>

- [ ] ...

## Out-of-runtime checks (manual)

> These are NOT executable by `/test-run` (they are not UI interactions). Run them by hand or
> with dedicated scripts. `/test-run` marks anything left here as `🚫 blocked: out-of-runtime`.

- [ ] `.doe/execution/run.sh` exits GREEN
- [ ] Release build completes and excludes debug/tooling symbols

## Notes

- **Device/Simulator**: state it before the run
- **Widget identification**: widgets are identified by visible text. For widgets without text
  (icons, images) the test describes them by position or role ("heart icon top-right", "first
  card in the list").

## Commits included

<output of git log <base>..HEAD --oneline>
```

### Step 4 — Generation rules

For each impacted feature:

1. **Happy path is mandatory**: at least one test for the main scenario.
2. **Edge case when the diff shows one**: an `if`, a gate, a feature flag → one line per branch.
3. **Back navigation**: if the feature adds a page to the navigation stack, add
   `Back from <page> returns to <previous> without a crash`.
4. **Visual check**: one `Layout of <page> matches the design` line — confirmed by screenshot.
5. **Max 10 tests per feature**: beyond that, ask whether to split the feature.

Every test must be:

- **Atomic**: one sentence, one verifiable assertion.
- **Self-contained**: says where it starts from ("from the home", "logged in") when not obvious.
- **Deterministic**: no "sometimes", "usually", "roughly".
- **Identified by visible text**: if the app has no widget keys, every interaction must name the
  element by its visible text, or by position/role when it has none. Never invent a key.

### Step 5 — Write the file and report

```
Test plan written: .test/<branch>.md

Diff vs <base>:
- 8 commits, 15 user-facing files changed
- Features impacted: A, B, Login

Tests generated: 18
- A: 6   B: 5   Login: 4   Cross-cutting (navigation): 3

Next:
1. Review .test/<branch>.md, add or remove tests
2. Start the app in the test flavor
3. `/test-run` to execute the checklist
```

## RULES

- **Analysis and a markdown file only.** No app launch, no UI automation.
- **Never modify application code.** Only `.test/*.md`.
- **Do not duplicate tests**: if another feature already covers a behaviour, reference it.
- If the file exists and `append` was not given, ask before overwriting.
- If the current branch is the base branch itself, or HEAD is detached, refuse with a clear
  message.
