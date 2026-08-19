# FEATURE directive: [Name]

> Copy this file to `NN_name.md` (progressive number) when the change is a **feature**.
> For a **bug** use `00_BUG_TEMPLATE.md` instead.
> The **Test Contract** section is MANDATORY: it defines the tests BEFORE the code (test-first).
> The directive is "done" only when `.doe/execution/run.sh` exits GREEN.

STATE: DRAFT

> **Approval gate.** `STATE: DRAFT` = being written/discussed: the directive-guard BLOCKS
> every change to the protected roots. After re-reading and discussing the directive, change
> it by hand to `STATE: APPROVED`: only then can `/execute NN` write code and tests.
> At L3 cleanup the directive is deleted.

## Type

**feature** — new functionality, or a change to existing behaviour.

## Objective

[What the feature must do — explicit, 1-2 sentences]

## Current vs expected behaviour

| | |
|---|---|
| **Current** | [how it behaves today] |
| **Expected** | [how it must behave afterwards] |

## Files involved

- [Every production file touched — analysed before writing the directive]

## Tests involved

- [Every existing test that touches this area]
- **Baseline:** run `.doe/execution/run.sh <path>` BEFORE any change → they must be GREEN.

## Impact on existing tests (default: NONE)

Most features are **backward compatible** → this table stays **EMPTY**: the existing tests
stay green throughout (that is the proof of backward compatibility) and you only add NEW
tests in the Test Contract.

Fill the table ONLY when the feature changes **existing behaviour** (breaking). How to fill
it (phase 1):

1. From the "Current vs expected" row: what actually changes.
2. From "Files involved": which production files.
3. Find the tests covering them — mirror path (`<src>/x/y` → `<tests>/x/y_test`) plus
   `grep -rl "<Symbol>" <tests>/`.
4. For each test, read its assertions: still true → **keep** (out of the table); they encode
   the old behaviour that is now wrong → **modify**; they cover a removed feature → **delete**.

| test `file:group` | action | reason → which behaviour changes (maps to "Current vs expected") |
|---|---|---|
| _(empty when backward compatible)_ | | |

- **modify** = rewrite the assertions to the NEW expected behaviour. In `/execute` the
  rewritten test must run **RED** against the old code, then green with the fix. (If it is
  green BEFORE implementing, the feature is a no-op or the test is fake.)
- **delete** = the behaviour/feature is removed.

> **Constraints.** Every `modify`/`delete` row MUST map to a row in "Current vs expected":
> a test changed without a declared behaviour change means you are adapting the test to the
> code. `/execute` may touch ONLY the tests listed here; if it needs another one → STOP,
> back to `/directive`.

## Test Contract (MANDATORY — written BEFORE the code)

List the tests that define success. **Unit tests only**, deterministic, offline. The test
tree mirrors the source tree. Write them here as real code blocks — they are the spec, not
yet materialised as files.

### `<tests>/<area>/<name>_test.<ext>`

```
[Test code as spec: arrange / act / assert on the expected behaviour.]
```

### `<tests>/<area>/<name>_state_test.<ext>` (when there is state logic)

```
[State/service test with the dependency injected as a fake or mock.]
```

**Edge cases to cover:** null / missing keys in the payload, empty list, mapped transport
error, unknown enum value, boundary numbers.

## Files to change

### DELETE: `<src>/path/file` (optional)

[Why]

### MODIFY: `<src>/path/existing`

**Remove / Add / Keep:**

```
// ...
```

### CREATE: `<src>/path/new_file`

```
// Full example
```

## Models / data structures (optional)

```
[Model with its parse/serialize/copy contract, following the project's conventions.]
```

## Data layer (optional)

```
[Repository / service and where it gets registered or wired.]
```

## Routing / navigation (optional)

[Which route file changes, and whether state lives in the router stack or in an overlay.]

## UI/UX (optional)

ASCII layout + components. Constraints: the project's design tokens, never hardcoded values.

## Execution plan (L2 — FEATURE flow)

1. Run the existing tests → **GREEN** (baseline, healthy starting state).
2. Materialise the Test Contract tests. If `Impact on existing tests` is NOT empty
   (breaking): modify/delete ONLY the listed tests, rewriting them to the NEW expectation.
3. `.doe/execution/run.sh <path>` → **RED**: the new tests plus the rewritten ones fail (the
   old code does not produce the new behaviour yet). Untouched tests stay green.
4. Install new dependencies, if any.
5. Write/modify the production code.
6. `.doe/execution/run.sh` → iterate until **GREEN**.

> Constraint: you touch ONLY the tests declared in `Impact on existing tests`. If you want
> to change a test that is not listed → STOP → back to `/directive` (either the code is
> wrong, or the directive is incomplete).

> **Red-test rule:** a red test means the code is wrong, never the test. Modify a test ONLY
> when this directive declared it obsolete for the planned changes.

## Verification (L3)

1. [ ] `.doe/execution/run.sh` exits GREEN (static analysis + whole suite).
2. [ ] Test Contract fully covered (edge cases included).
3. [ ] Everything registered/wired where the project requires it.
4. [ ] Directive complete → **delete this file** from `.doe/directives/`.

## Notes

- [Dependencies on other directives, warnings]
