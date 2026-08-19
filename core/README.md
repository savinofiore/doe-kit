# Core

Everything here is stack-agnostic. A stack adapter never modifies these files; it only answers
"what is the gate".

```
core/
├── skills/       what the agent runs
├── templates/    what a directive looks like
└── execution/    what makes the process mechanical
```

## skills/

| Skill | Phase | What it does |
|---|---|---|
| `directive` | 1 | Interviews, writes `NN_name.md` at `STATE: DRAFT`. Writes **zero** code. |
| `execute` | 2 | Runs an APPROVED directive: baseline → RED → fix → green gate → cleanup. |
| `review` | — | Analysis only. Classifies findings by severity **and testability**; materialises one directive per tier. Edits nothing. |
| `review-fix` | — | Applies a review on two tracks: DOE directives through the gate, direct fixes with `Edit`. |
| `diagnose` | — | Three competing hypotheses, minimal logging, no fix until the logs confirm the cause. |
| `delta-check` | — | Read-only pre-commit check on the branch diff. |
| `port-commits` | — | Enumerate → plan → port atomically → coverage-check. Silent skips become impossible. |

`directive` and `execute` are the process. The other five are the habits that stop the process
being routed around: a review that quietly starts fixing, a debug session that fixes the first
plausible cause, a port that drops nine files.

## templates/

`00_FEATURE_TEMPLATE.md` · `00_BUG_TEMPLATE.md` · `00_REVIEW_TEMPLATE.md`

The installer copies all three into `.doe/directives/`. The `00_` prefix is load-bearing: the
guard skips those files when looking for an APPROVED directive, so a template can never unlock
anything even if someone writes `STATE: APPROVED` inside one by mistake.

Two sections carry the weight:

- **Test Contract** — the tests, as code, before the code. Without it the directive is not
  executable.
- **Impact on existing tests** — the whitelist of tests execution is allowed to modify. Default
  empty, and every non-empty row must map to a declared behaviour change. This is what turns
  "never edit a test to make it pass" from a hope into a rule.

## execution/

| File | Role |
|---|---|
| `directive_guard.py` | `PreToolUse` hook. Blocks writes into the protected roots until an APPROVED directive exists. Covers both write tools and Bash write constructs. |
| `guard_selftest.py` | The guard's regression suite. Tests both false negatives (bypass) and false positives (legitimate work blocked). |

Protected roots come from `.doe/doe.config.json`, then `DOE_PROTECTED_ROOTS`, then
auto-detection. One guard serves every stack.

Details: [../docs/enforcement.md](../docs/enforcement.md).
