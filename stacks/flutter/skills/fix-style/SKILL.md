---
name: fix-style
description: Detect and fix design-token and naming violations in Flutter code — hardcoded colours, text styles, dimensions, border radii, missing imports, naming conventions. Reads the project's token names from .doe/conventions.json instead of assuming a design system. Use for the non-testable half of a review, or to clean a feature before a PR.
allowed-tools: Read, Edit, Glob, Grep, Bash
---

# Fix Style — the violations no unit test can see

Detects and fixes convention violations in the widget layer: hardcoded colours, text styles,
dimensions, radii, missing imports, naming.

## Where this sits in DOE

These violations are **non-testable by design**. No deterministic offline unit test turns red
because a colour is hardcoded — the widget layer is outside the gate perimeter on purpose (see
`.doe/README.md` § Test scope).

So this skill is **Track B**: direct fixes, outside the gate, with `flutter analyze` as the
only check. It is what `/doe-review-fix` calls for the findings `/doe-review` classified as
non-testable.

Two consequences worth being explicit about:

- The directive-guard blocks writes to `lib/` unless a directive is APPROVED. Running this
  skill outside `/doe-review-fix` means either an approved directive is already active, or you set
  `DOE_BYPASS=1` and know it.
- Never route a style fix through a directive to "make it official". A Test Contract that
  cannot produce a red test is theatre, and it teaches everyone that the gate is negotiable.

## Configuration (mandatory)

Read `.doe/conventions.json` first. It declares this project's token classes, accessor names,
sizing extensions, imports and naming rules. Template: `conventions.example.json` in the stack.

**If the file is missing, stop.** Ask the user to create it. Do not guess token names from the
codebase and do not fall back to another project's conventions — a wrong "fix" that compiles is
worse than no fix, because it looks done.

Every rule below is driven by that config. If a section is absent from the config, the
corresponding rule is **off**: report nothing for it.

## Violation categories

### 1. Hardcoded colours

Violations: `Colors.<name>`, `Color(0x…)`, `Color.fromARGB(…)`, `Color.fromRGBO(…)`.

Fix: the accessor from `tokens.colors`, chosen by **role**, not by hue. The role comes from the
context of the usage — a colour on a card background maps to `cardBackground`, whatever its hex
value was.

```bash
grep -rn "Colors\." lib/ --include="*.dart" | grep -vF -f <(allowed-list)
grep -rn "Color(0x\|Color\.from" lib/ --include="*.dart"
```

Never invent a role that is not in `tokens.colors.roles`. If none fits, report it and ask —
that is usually a missing token, not a missing fix.

### 2. Hardcoded text styles

Violations: a bare `TextStyle(...)` where a token exists.

Fix: `tokens.textStyles.bySize` maps a font size to a token member. A `.copyWith()` on top of a
token is **allowed** and must not be flagged.

```bash
grep -rn "TextStyle(" lib/ --include="*.dart" | grep -v "<textStyles.class>" | grep -v ".copyWith"
```

### 3. Dimensions without the sizing extension

Only when `tokens.sizing.library` is set. Violations: numeric literals for width, height, font
size, padding, margin without the configured extension.

Fix: append `tokens.sizing.width` / `.height` / `.fontSize`.

**Never flag** anything in `tokens.sizing.allowed` (typically `double.infinity`, `MediaQuery`
sizes, and zero). Zero especially: `height: 0` scaled is still zero, and flagging it is noise
that trains people to ignore the report.

### 4. Hardcoded border radii

Violations: `BorderRadius.circular(N)` / `Radius.circular(N)` where `N` is in
`tokens.radii.byValue`.

Fix: the mapped constant. A value **not** in the map is a finding of a different kind: report
it as "off-scale radius" and ask whether it should become a token, rather than rounding it to
the nearest one. Silently snapping values is how a design system drifts.

### 5. Naming conventions

Driven by `naming`:

- components missing `componentPrefix`
- pages missing `pageSuffix`
- pages missing the static path constant, when `pageRequiresStaticPath` is true

```bash
grep -rn "class [A-Z]" lib/components/ | grep -v "class <prefix>"
grep -rn "class [A-Z].*extends ConsumerWidget" lib/pages/ | grep -v "<suffix> "
```

A rename touches every call site. Never rename in the same pass as a style fix: report it,
fix it in its own change, with `flutter analyze` between the two.

### 6. Missing imports

After any fix, add the `import` declared next to each token group in the config, plus the
sizing library import when an extension was added. A fix that does not compile is not a fix.

## Execution

1. **Read the config.** Missing → stop and ask.
2. **Scan** the target scope only — a file, a feature folder, or the branch diff. Never scan all
   of `lib/` unless asked: a 400-line report gets closed, not read.
3. **Report before fixing** (see format below), grouped by category with `file:line`.
4. **Apply** one file at a time with `Edit`, adding imports as you go.
5. **Verify** with `flutter analyze` (or the Dart MCP `analyze_files` when available, for
   structured output). New errors → stop, show them, ask whether to fix or roll back.
6. **Format** the touched files.
7. **Re-scan** to confirm.

## Report format

```markdown
# Style violations — lib/pages/<feature>/

**Files scanned:** 4   **Violations:** 12

## Hardcoded colours (5)
- `<feature>_page.dart:45`  `Colors.blue` → `KColors.getInteractivePrimaryColor(context)`  [role: buttonBackground]
- `<feature>_card.dart:67`  `Color(0xFF1E2A38)` → `KColors.getBackgroundCardColor(context)`  [role: cardBackground]

## Dimensions without ScreenUtil (4)
- `<feature>_page.dart:78`  `width: 16` → `width: 16.w`

## Off-scale radii (1) — needs a decision
- `<feature>_card.dart:22`  `BorderRadius.circular(10)` — 10 is not in the radius scale
  (4/8/12/16/24/100). Round to `small` (8) or `medium` (12), or add a token?

## Naming (1) — separate change
- `components/badge.dart:8`  `class Badge` → `class KBadge` (touches 6 call sites)

## Missing imports (1)
- `<feature>_card.dart`  add `package:myapp/themes/k_colors.dart`
```

## RULES

- **Config first.** No `.doe/conventions.json` → no fixes.
- **Map by role, not by value.** The old hex is evidence of intent, not the answer.
- **Never invent a token.** An unmappable value is a finding, not a fix.
- **Never rename in a style pass.** Renames are their own change.
- **Never suppress an analyzer warning** with an ignore comment to make the scan pass.
- **Ignore** generated files (`*.g.dart`, `*.freezed.dart`) and tests.
- Report `N fixed, M left for a decision` — a report that claims 100% while hiding the
  ambiguous cases is the same failure as an invisible skip-list in the coverage gate.
