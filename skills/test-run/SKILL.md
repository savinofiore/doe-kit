---
name: test-run
description: Execute a manual-test checklist from .test/<branch>.md against a already-running Flutter app, driving it through a UI-automation MCP server. Ticks each line (pass/fail/skipped/blocked) in a copy saved under .test/reports/<branch>-<timestamp>/, with screenshots and logs. Never modifies application code.
---

# Test Run — drive the checklist against a real device

Executes the checklist written in `.test/` by driving a simulator or device through a Flutter
UI-automation MCP server (for example `marionette`). For each `- [ ]` line it attempts the
check, marks ✅/❌/⏸/🚫 and writes the result to `.test/reports/<branch>-<timestamp>/`.

The tool names below are those of `marionette`. With a different automation server, map them to
its equivalents — the logic of the skill does not change.

## Prerequisites

1. The app is **already running** in the flavor where the automation server is initialised.
2. `.test/<branch>.md` exists (from `/test-plan` or written by hand).

## Optional inputs

- `file=<path>` — checklist to run (default: `.test/<current-branch>.md`)
- `vm=<uri>` — VM service URI
- `only=A,Login` — run only these sections (case-insensitive match on `## <name>`)
- `stop-on-fail` — stop at the first ❌ (default: continue)
- `all-screenshots` — screenshot every test (default: only failures and end-of-section)

## Workflow

### Step 1 — Preflight

1. `BRANCH=$(git branch --show-current)`
2. Resolve the checklist file. If it does not exist, suggest `/test-plan` and stop.
3. Create the report directory:
   ```bash
   TS=$(date +%Y%m%d-%H%M%S)
   REPORT_DIR=".test/reports/${BRANCH//\//_}-$TS"
   mkdir -p "$REPORT_DIR/screenshots"
   cp "<checklist>" "$REPORT_DIR/checklist.md"
   ```
   The original checklist is never modified — only the copy.

### Step 2 — Classify what is runnable

Every test under `## Out-of-runtime checks (manual)` is marked `🚫 blocked: out-of-runtime`
without analysis: that section is declaratively out of scope.

Then continue with the tests that are actually executable.

### Step 3 — Connect

Connect the automation server to the VM URI. On failure: stop and mark every test
`🚫 blocked: connection failed`, suggesting a check that the app is running in the right
flavor.

### Step 4 — Run the tests

Section by section, for each `- [ ] <test>`:

1. **Interpret the text** and derive the tool-call sequence. When the app has no widget keys,
   identify widgets by visible text or by inspecting the tree:
   - `"Tap 'X' in the bottom nav opens the list"` → `tap(text: 'X')` + an element dump to
     verify the list is present.
   - `"Valid email and password lead to the home"` → dump elements to locate the fields (they
     usually have a recognisable label/placeholder) → `enter_text` → `tap` → verify home
     elements.
   - `"Tapping the heart icon top-right toggles its state"` → dump before, `tap`, dump after,
     compare.
   - If the text is ambiguous (the same label on several buttons): dump and filter by
     page/position. Record in the report how it was resolved.

2. **Execute** the calls in sequence. Per-step timeout: 15s.

3. **Determine the outcome** — four states, not three:
   - ✅ `pass` — every action succeeded and the check confirms the behaviour
   - ❌ `fail` — the action ran but the check is negative
   - ⏸ `skipped` — the user chose not to run it (login without credentials, for instance) — it
     was NOT executed
   - 🚫 `blocked` — impossible to run here (needs a code change, a build, a git operation, an
     unmet system precondition) — it was NOT executed

4. **Screenshots**:
   - On ❌ always: save to `$REPORT_DIR/screenshots/<feature>-<n>-FAIL.png` and cite it. If the
     tool only returns an inline payload, note that in the report and continue.
   - End of each section: `<feature>-end.png`.
   - With `all-screenshots`: also on ✅, as `<feature>-<n>-pass.png`.

5. **Update the line** in the copied file:

   | State | Line format |
   |---|---|
   | ✅ pass | `- [x] ✅ <test>` |
   | ❌ fail | `- [x] ❌ <test> — <reason>` |
   | ⏸ skipped | `- [ ] ⏸ skipped: <reason> — <test>` |
   | 🚫 blocked | `- [ ] 🚫 blocked: <reason> — <test>` |

   > **Important**: `[ ]` (unchecked) for skipped and blocked — the test was not executed, so it
   > must not count as done. This keeps the file readable at a glance and compatible with
   > external counters.

6. **Logs**: capture the app logs during the test and append them to `$REPORT_DIR/run.log`
   under a `### <feature> - <test>` header. **If the log call errors** (a known failure mode of
   some automation-server versions):
   - do not mark the test failed because of it;
   - try the fallback log source (the Dart/Flutter tooling MCP, if the app is registered);
   - if neither is available, write `[logs unavailable: <error>]` in `run.log` and continue;
   - note the degradation ONCE in the final report, under "Issues during the run".

7. **Reset state** between tests: press back until you are at the starting point named by the
   next test. If the starting point is unreachable, mark subsequent tests
   `🚫 blocked: dirty state` and jump to the next independent group (or stop, with
   `stop-on-fail`).

With `stop-on-fail`, on the first ❌ stop and mark the rest `⏸ skipped: stop-on-fail`.

### Step 5 — Disconnect

Always, including on error or interruption.

### Step 6 — Write the report

`$REPORT_DIR/report.md`:

```markdown
# Test Report - <branch>

**Checklist**: .test/<branch>.md
**Run**: <timestamp> (duration <X>m)
**Device**: <value>
**Mode**: stop-on-fail=<bool>, all-screenshots=<bool>

## Summary

| Feature | ✅ Pass | ❌ Fail | ⏸ Skipped | 🚫 Blocked | Total |
|---------|------|------|---------|---------|--------|
| A       | 5 | 1 | 0 | 0 | 6 |
| Login   | 2 | 0 | 2 | 0 | 4 |
| **Total** | **12** | **1** | **2** | **0** | **15** |

> `Skipped` and `Blocked` are separate columns on purpose: skipped = the user's choice,
> blocked = outside the tool's reach. Collapsing them hides why coverage is missing.

## Failures

### A - "The favourite button toggles on tap"
- **Reason**: the heart icon does not respond to the tap; its visual state does not change
- **Screenshot**: screenshots/a-3-FAIL.png (pre-tap) + a-3-FAIL-post.png (unchanged)
- **Suggestion**: check the toggle handler in `<Page>` (line XX); it may not be wired to the
  state layer.

## Full logs

See `run.log`.

## Updated checklist

See `checklist.md`.
```

### Step 7 — Chat summary

Short, not the whole report:

```
Test run complete: .test/reports/<branch>-<ts>/

✅ 14/15 pass (93%)
❌ 1 fail: A "favourite button toggles on tap" → tap has no effect on the visual state

Screenshots: 4 in screenshots/
Full log: run.log

Suggested next step:
- Check the onTap handler → re-run with `/test-run only=A`
```

## Translating test text into tool calls

| Pattern in the text | Tool call |
|---|---|
| "Tap 'X'" / "Select 'X'" | `tap` with `text: "X"` — the **visible** on-screen string |
| "Tap the <Y> icon" / a widget with no text | dump the tree, locate by type/position, then tap the identified element |
| "Enter 'x' in <field>" | dump to locate the field by label/placeholder, then `enter_text` |
| "Scroll up/down" | `swipe` or `scroll_to` |
| "Back" | `press_back_button` |
| "Page <X> opens" / "Shows <X>" | dump + check for the characteristic text/elements |
| "No error" / "No crash" | read the logs and grep for `ERROR`, `Exception`, `OVERFLOW`, `RenderFlex`. If logs are unavailable, judge only the absence of a visible crash and note `logs unavailable` |
| "Badge/icon present" | dump + check |
| "Layout matches the design" | screenshot (visual check — passes unless there is a crash) |

**Ambiguous text** (the same string in several places):

1. Dump to see every occurrence.
2. Filter by context (current page, widget type, position).
3. Note explicitly in the report how the ambiguity was resolved.

**Uninterpretable test**: mark `🚫 blocked: ambiguous test` and add a "Tests to clarify" section
with a suggested rewording.

## Edge cases

- **Widget not found**: the tap by text fails. Mark it failed, screenshot the current tree, and
  note whether the searched text was plausibly wrong (suggest a rewording) or the widget has no
  visible text (suggest describing it by position/role).
- **App crashed** during a test: mark `fail: app crashed`, attempt a hot reload. If it does not
  recover, mark the rest `🚫 blocked: app crashed` and stop with a note.
- **Unexpected dialog/overlay**: try back. If it does not close, fail the current test with a
  screenshot and continue after a state reset.
- **Routing redirect** (session expired): mark `🚫 blocked: session expired` and suggest making
  the login precondition explicit in the test.
- **Animations in flight** at screenshot time: poll briefly (max 3s) until the tree stabilises.

## RULES (STRICT)

- **Never modify application code.** Even an obvious bug goes in the report; applying it is the
  user's call — or `/doe-review-fix`'s, in a separate session.
- **Never start the app.** If it is not running or the automation server will not connect, stop
  with instructions.
- **Never touch the original** `.test/<branch>.md`. Only the copy in `$REPORT_DIR/checklist.md`.
- **Never silently skip a test.** Every line ends with a state in the report.
- **Always disconnect** at the end, including on error.
