# Contributing

## The bar

This kit exists because agents are confident and confidence is not correctness. The same
standard applies to changes here.

- **A change to the guard needs a case in `guard_selftest.py`.** Both directions: what must be
  blocked, and what must keep working. A guard change with no new ALLOW case is usually a
  future false positive.
- **A change to a template must survive a real directive.** Write one, run it end to end, then
  propose the change.
- **No rule without its incident.** Every rule in `docs/` traces back to something that actually
  went wrong. If you cannot state the failure a rule prevents, it is a preference, and
  preferences make the process heavier without making it safer.

## Running the checks

```bash
bash -n install.sh
for f in stacks/*/execution/*.sh; do bash -n "$f"; done

# install into a fixture and verify the guard end to end
mkdir -p /tmp/fixture && cd /tmp/fixture && git init -q . && touch package.json
/path/to/doe-kit/install.sh --stack web-ts /tmp/fixture
.doe/execution/directive_guard.py --status     # GUARD: ARMED
.doe/execution/guard_selftest.py               # no false positives, no false negatives
```

CI runs exactly this, for both stacks, plus the i18n validator. See
`.github/workflows/kit-selftest.yml`.

## Adding a stack

See [stacks/README.md](stacks/README.md). The contract is two scripts:

- `run.sh` — deterministic, offline, narrowable by path, exit 0 iff everything passes.
- `coverage.sh` — per-file threshold on changed files, every exclusion logged, red when it
  cannot evaluate.

Then add the protected roots to the `case` in `install.sh`, and to the auto-detection in
`core/execution/directive_guard.py` if the stack has an unambiguous marker file.

## Changing the guard

Two failure modes, and the second is the dangerous one:

- **False negative** — a write gets through: the process can be bypassed unnoticed.
- **False positive** — legitimate work is blocked: someone switches the guard off, and from
  then on it protects nothing.

Which is why the guard deliberately does not block reads, `git status`, the gate, or
redirections to unprotected paths. If your change blocks any of those, it is wrong even if it
closes a real hole. Find another way.

The Bash analysis is a heuristic, not a shell parser, and that is a decision rather than a
limitation: it stops the process being bypassed by inattention. Anyone determined to bypass it
already has `DOE_BYPASS=1`, which at least is explicit and visible.

## Style

- English, in code and in docs.
- Comments explain **why**, never what. The what is in the code.
- Skills are instructions to an agent: imperative, specific, and explicit about what is
  forbidden. "Prefer X" gets ignored; "Never Y — if you need Y, STOP and do Z" does not.
