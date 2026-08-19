# Stack: flutter (Dart · flutter test)

Target: Flutter apps with `flutter analyze` and `flutter test`.

Protected roots: **`lib/`** and **`test/`**.

## Gate

```bash
.doe/execution/run.sh                 # analyze + whole unit suite
.doe/execution/run.sh test/models     # narrow to a path
.doe/execution/run.sh --name "Quiz"   # filter by test name

.doe/execution/coverage.sh            # full gate: + coverage threshold on changed files
DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh
DOE_BASE_REF=main .doe/execution/coverage.sh
```

Every argument to `run.sh` is forwarded to `flutter test`.

## Test scope

- **Unit tests only.** A `testWidgets` drags in the framework bootstrap and as many sources of
  non-determinism (timers, frames, assets, plugins).
- **Widget tests are excluded mechanically, not by convention.** `run.sh` enforces it:
  - `test/widget/` is the **only** folder where a `testWidgets(` may live, and it stays out of
    the target when the gate runs without arguments;
  - a `testWidgets(` **outside** that folder fails the gate with an explicit message, before
    `flutter analyze` even runs.

  The match is on the `testWidgets(` invocation, not the bare word, so a mention in a comment
  does not turn the gate red by accident.
- **What gets tested:**
  - **Models** → `fromJson`, `copyWith`, enum parsing, edge cases (null, missing keys).
  - **State logic** → notifiers driven through a container with overrides.
  - **Repositories** → HTTP client mocked, response and error mapping.
  - **Utils** → pure functions.
- **Mocking:** `mocktail` (no codegen, so no `build_runner` in the loop).
- **`test/` mirrors `lib/`** (`lib/models/user/emoji.dart` → `test/models/user/emoji_test.dart`).

## The coverage gate on a Flutter app

The view layer dominates the line count — on a mature app, 15,000–20,000 lines of it. The
global lcov number is therefore meaningless as a target, and `coverage.sh` prints the KPI on
the gate perimeter separately, labelling which is which.

Before you run it, edit the two lists at the top of `coverage.sh`:

- `SKIP_PATTERNS` — layers outside the unit perimeter (pages, components, themes, animations,
  native channels, platform plugins). Every entry carries a written reason and gets **logged**
  when it fires. An invisible skip-list turns the gate into theatre.
- `KEEP_PATTERNS` — pure logic that happens to live inside an excluded folder (a markdown
  parser, an enum with a mapping, plain exception classes). The keep-list wins over the
  skip-list and can only make the gate stricter.

Details and the rules for both lists: [../../docs/coverage-gate.md](../../docs/coverage-gate.md).

## Architecture constraints the generated code must respect

- **Business logic never lives in a widget.** Extract it into models, notifiers, repositories
  and utils — the layers a unit test can reach. A gate that cannot run offline is a gate that
  never runs.
- **Repository pattern for data access**: no HTTP calls from pages or notifiers.
- **Dependencies injected through the container**, so tests can override them.
- **Models carry their own `fromJson` / `toJson` / `copyWith`.**
- **No hardcoded colours, text styles, sizes or radii** — design tokens only.
- **No user-visible hardcoded strings** — the localisation call, with the keys present in the
  translation files.

## Stack skills

Five skills ship with this stack. Each one states where it sits in the DOE loop, because a
skill that writes to `lib/` outside an approved directive is a skill the guard will refuse —
and that refusal is the point.

| Skill | Runs | Writes code? |
|---|---|---|
| `riverpod-architect` | **before** `/directive` — designs the state, produces the use-case list that becomes the Test Contract | no |
| `scaffold-feature` | **inside** `/execute NN` — tests first, then model → repository → state → provider → view | yes, under an APPROVED directive |
| `fix-style` | **Track B** of `/review-fix` — the non-testable findings | yes, outside the gate |
| `test-plan` | any time — reads the branch diff, writes a manual checklist | no (only `.test/`) |
| `test-run` | after `test-plan` — drives a running app through the checklist | no |

The pipeline they form:

```
riverpod-architect → /directive → [approve] → /execute (scaffold-feature) → /review → /review-fix (fix-style)
                                                        ↑ tests first, RED before GREEN
```

## Conventions file (required by three of them)

`scaffold-feature`, `fix-style` and `riverpod-architect` read `.doe/conventions.json` — your
token classes, paths, naming rules, state patterns and i18n setup. The installer drops
`conventions.example.json` next to it; copy and fill it.

```bash
cp .doe/conventions.example.json .doe/conventions.json
```

**They refuse to run without it, on purpose.** A style skill that guesses your design system
produces fixes that compile and are wrong — which is strictly worse than no fix, because it
looks done. The example file carries one real project's values as illustration; none of them
are a standard, and any section you delete simply turns that rule off.

## Beyond the gate: manual QA

Unit tests cannot see navigation, layout or a real device. Two skills cover that ground without
pretending to be part of the gate:

- **`test-plan`** — reads the branch diff and generates a flat, checkable list of manual tests
  grouped by feature, into `.test/<branch>.md`.
- **`test-run`** — drives a running app through that checklist via a UI-automation MCP server
  and writes a ticked report.

They are deliberately outside `run.sh`: they are not deterministic, and a gate that includes
non-deterministic checks is a gate people learn to re-run until it is green.

## Recommended permissions

```json
{
  "permissions": {
    "allow": [
      "Bash(.doe/execution/run.sh:*)",
      "Bash(.doe/execution/coverage.sh:*)",
      "Bash(.doe/execution/directive_guard.py:*)",
      "Bash(flutter analyze:*)",
      "Bash(flutter test:*)",
      "Bash(dart fix:*)",
      "Bash(dart format:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)"
    ]
  }
}
```
