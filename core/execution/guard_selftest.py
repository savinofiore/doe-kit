#!/usr/bin/env python3
"""
Self-test for the directive guard.

The guard is the only thing that makes the DOE process mechanical. If it breaks, it breaks
silently: no test fails, no gate turns red — it just stops protecting, and nobody notices
until it is too late. This file is its regression suite.

Two classes of error, and the second one is the dangerous one:

  - FALSE NEGATIVE — a write gets through: the process can be bypassed unnoticed.
  - FALSE POSITIVE — legitimate work is blocked: the guard becomes unbearable, someone
    switches it off, and from then on it protects nothing.

    .doe/execution/guard_selftest.py        # runs in CI and by hand

The cases below use `src/` + `tests/` as protected roots. On a Dart/Flutter project the
roots are `lib/` + `test/`; the runner rewrites the cases accordingly, so the same file
covers both stacks.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GUARD = ROOT / ".doe/execution/directive_guard.py"

ALLOW = "allow"
DENY = "deny"

# ── Bash commands: (command, expected verdict) ──────────────────────────────────
BASH_CASES: list[tuple[str, str]] = [
    # Everyday work: gate, tests, build. Must never be touched.
    ("npm run test", ALLOW),
    ("npm run build", ALLOW),
    (".doe/execution/run.sh", ALLOW),
    (".doe/execution/run.sh tests/core/models", ALLOW),
    ("npx vitest run tests/core/errors/repository-error.test.ts", ALLOW),
    ("npx tsc --noEmit", ALLOW),
    ("npx eslint .", ALLOW),
    # Reads on protected paths: always allowed.
    ("cat src/core/errors/repository-error.ts", ALLOW),
    ("head -50 src/app/page.tsx", ALLOW),
    ("grep -rn 'RepositoryError' src/", ALLOW),
    ("ls -la src/core", ALLOW),
    ("find src -name '*.ts'", ALLOW),
    ("wc -l src/core/errors/repository-error.ts", ALLOW),
    ("cp src/core/errors/repository-error.ts /tmp/backup.ts", ALLOW),
    ("python3 -c \"print(open('src/app/page.tsx').read())\"", ALLOW),
    # Git: inspection and recovery stay free.
    ("git status", ALLOW),
    ("git diff src/", ALLOW),
    ("git add -A", ALLOW),
    ("git log --oneline -10", ALLOW),
    ("git checkout -- src/", ALLOW),
    ("git reset --hard HEAD", ALLOW),
    # Redirections outside the protected roots, and file-descriptor duplication.
    ("echo hello > /tmp/x.txt", ALLOW),
    ("npm run build 2>&1 | tail -20", ALLOW),
    ("npx vitest run --coverage 2>&1 | tail -3", ALLOW),
    ("npm test > /dev/null 2>&1", ALLOW),
    ("node .doe/execution/coverage-check.mjs --min 80 > /tmp/cov.txt", ALLOW),
    ("echo 'a > b'", ALLOW),
    ("node -e \"console.log(require('./package.json').name)\"", ALLOW),
    # Heredoc body: it is data, not shell. A commit message that DESCRIBES a redirection is
    # not a redirection — this case really did block the commit that introduced the Bash
    # guard.
    (
        "git commit -F - <<'EOF'\n"
        "Extend the guard to Bash writes\n\n"
        "The concrete case is `npx supabase gen types ... > src/types/database.ts`,\n"
        "a write into src/ that never goes through an Edit tool.\n"
        "EOF",
        ALLOW,
    ),
    ("cat <<'EOF' > /tmp/note.txt\nsed -i 's/a/b/' src/core/x.ts\nEOF", ALLOW),
    # Writes into the protected roots: all blocked.
    (
        "npx supabase gen types typescript --project-id PROJECT_ID > src/types/database.ts",
        DENY,
    ),
    ("npx supabase gen types typescript > $CLAUDE_PROJECT_DIR/src/types/database.ts", DENY),
    ("echo 'export const x = 1' > src/core/utils/x.ts", DENY),
    ("echo 'more' >> tests/core/errors/repository-error.test.ts", DENY),
    ("echo x > ./src/foo.ts", DENY),
    # The line that OPENS the heredoc contains a real redirection: still blocked.
    ("cat > src/core/models/post.ts <<'EOF'", DENY),
    ("cat > src/core/models/post.ts <<'EOF'\nexport const x = 1;\nEOF", DENY),
    ("sed -i 's/draft/published/' src/core/errors/repository-error.ts", DENY),
    ("sed -i '' 's/a/b/' tests/core/errors/repository-error.test.ts", DENY),
    ("cp /tmp/post.ts src/core/models/post.ts", DENY),
    ("mv /tmp/x.test.ts tests/core/x.test.ts", DENY),
    ("mv src/a.ts /tmp/a.ts", DENY),  # moving OUT of src/ is still a modification
    ("rm src/core/errors/repository-error.ts", DENY),
    ("rm -rf tests/core", DENY),
    ("touch src/core/models/post.ts", DENY),
    ("tee src/core/x.ts", DENY),
    ("python3 -c \"open('src/core/x.ts','w').write('hi')\"", DENY),
    ("node -e \"require('fs').writeFileSync('src/core/x.ts','hi')\"", DENY),
    ("git apply /tmp/feature.patch", DENY),
    ("git am /tmp/feature.patch", DENY),
    ("npm run build && echo done > src/marker.txt", DENY),
    ("mkdir -p src/core/utils && touch src/core/utils/slug.ts", DENY),
    ("FOO=bar sed -i 's/a/b/' src/core/errors/repository-error.ts", DENY),
]

# ── write tools: (tool, path, expected verdict) ─────────────────────────────────
#
# Absolute paths are built from ROOT at runtime: hardcoding them ties the test to the
# machine that wrote it. An absolute path from another machine falls outside the repo, and
# the guard — correctly — does not block what is outside the repo.
TOOL_CASES: list[tuple[str, str, str]] = [
    ("Write", "src/core/models/post.ts", DENY),
    ("Edit", "tests/core/models/post.test.ts", DENY),
    ("Write", str(ROOT / "src/x.ts"), DENY),
    ("Write", "/etc/passwd", ALLOW),  # outside the repo: none of the guard's business
    ("MultiEdit", "src/app/page.tsx", DENY),
    ("Write", ".doe/directives/01_auth.md", ALLOW),
    ("Write", "CLAUDE.md", ALLOW),
    ("Write", "docs/architecture.md", ALLOW),
    ("Read", "src/core/models/post.ts", ALLOW),
    ("Grep", "src/", ALLOW),
]

PATCH_CASES: list[tuple[str, str]] = [
    ("*** Begin Patch\n*** Update File: src/core/models/post.ts\n*** End Patch", DENY),
    ("*** Begin Patch\n*** Add File: tests/core/models/post.test.ts\n*** End Patch", DENY),
    ("*** Begin Patch\n*** Update File: docs/architecture.md\n*** End Patch", ALLOW),
]

# Root rewriting, so one case list covers every stack. Order matters: the longer name first,
# otherwise `src` inside `tests` would be rewritten twice.
CANONICAL_ROOTS = ("tests", "src")


def adapt(text: str, roots: tuple[str, ...]) -> str:
    """Rewrites `src/` and `tests/` in a case to the project's actual protected roots."""
    if len(roots) < 2 or roots[:2] == ("src", "tests"):
        return text
    code_root, test_root = roots[0], roots[1]
    return text.replace("tests/", f"{test_root}/").replace("src/", f"{code_root}/")


def load_guard():
    """
    Imports the guard as a module to test its pure functions.

    The test does NOT re-implement reading a directive's `STATE:` — that logic lives in the
    guard and stays there. Duplicating it here already broke it once: a substring search
    found `STATE: APPROVED` inside the instructions at the top of a DRAFT directive, the
    self-test skipped itself and exited 0. A false green in the test that exists precisely
    to prevent false greens.
    """
    # Without this, the import leaves a .pyc in .doe/execution/__pycache__/. The guard is a
    # hook run as a script, not a library: the only importer is this test, and a build
    # artifact inside .doe/ is just dirt.
    sys.dont_write_bytecode = True

    spec = importlib.util.spec_from_file_location("directive_guard", GUARD)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GUARD}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(payload: dict) -> str:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(ROOT)},
    )
    out = proc.stdout.strip()
    if not out:
        return ALLOW
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (json.JSONDecodeError, KeyError):
        return f"ERROR({proc.returncode}): {out[:120]}"


def main() -> int:
    guard = load_guard()
    roots = guard.protected_roots(ROOT)

    bash_cases = [(adapt(cmd, roots), expected) for cmd, expected in BASH_CASES]
    tool_cases = [(tool, adapt(path, roots), expected) for tool, path, expected in TOOL_CASES]
    patch_cases = [(adapt(patch, roots), expected) for patch, expected in PATCH_CASES]

    false_pos: list[tuple[str, str]] = []
    false_neg: list[tuple[str, str]] = []
    passed = 0

    # ── Level 1: the DETECTION functions, always ────────────────────────────────
    #
    # They are pure and do not depend on directive state, so they run every time — even
    # with the guard unlocked. That is what makes this self-test non-vacuous by
    # construction: whatever the repo state, the detection logic gets verified. Only
    # level 2 existed before, and with an APPROVED directive the whole file skipped itself.
    for command, expected in bash_cases:
        detected = bool(guard.find_writes(command, ROOT, roots))
        if detected == (expected == DENY):
            passed += 1
        elif expected == ALLOW:
            false_pos.append((command, "write detected"))
        else:
            false_neg.append((command, "no write detected"))

    for tool, path, expected in tool_cases:
        if tool not in guard.GUARDED_TOOLS:
            continue  # the tool-name filter is verified at level 2
        protected = guard.is_protected(ROOT, path, roots) is not None
        if protected == (expected == DENY):
            passed += 1
        elif expected == ALLOW:
            false_pos.append((f"{tool} → {path}", "path treated as protected"))
        else:
            false_neg.append((f"{tool} → {path}", "path not treated as protected"))

    for patch, expected in patch_cases:
        protected = any(guard.is_protected(ROOT, path, roots) for path in guard.patch_paths(patch))
        if protected == (expected == DENY):
            passed += 1
        elif expected == ALLOW:
            false_pos.append((f"apply_patch → {patch}", "path treated as protected"))
        else:
            false_neg.append((f"apply_patch → {patch}", "path not treated as protected"))

    total = (
        len(bash_cases)
        + sum(1 for t, _, _ in tool_cases if t in guard.GUARDED_TOOLS)
        + len(patch_cases)
    )

    # ── Level 2: the end-to-end wiring, only while the guard is armed ───────────
    #
    # An APPROVED directive unlocks the guard project-wide, so the DENY cases cannot be
    # verified through the process. Only THIS level is skipped, and it says so: no more
    # silent exit 0.
    approved = guard.approved_directives(ROOT)
    if approved:
        print(
            "end-to-end: SKIPPED — an APPROVED directive is active "
            f"({', '.join(p.name for p in approved)}), the guard is unlocked on purpose.\n"
            "Detection was verified anyway.\n"
        )
    else:
        for tool, path, expected in tool_cases:
            got = verdict({"tool_name": tool, "tool_input": {"file_path": path}})
            label = f"e2e {tool} → {path}"
            if got == expected:
                passed += 1
            elif expected == ALLOW:
                false_pos.append((label, got))
            else:
                false_neg.append((label, got))
        total += len(tool_cases)

        for patch, expected in patch_cases:
            got = verdict({"tool_name": "apply_patch", "tool_input": {"patch": patch}})
            label = f"e2e apply_patch → {patch}"
            if got == expected:
                passed += 1
            elif expected == ALLOW:
                false_pos.append((label, got))
            else:
                false_neg.append((label, got))
        total += len(patch_cases)

        e2e_bash = adapt("npx supabase gen types typescript > src/types/database.ts", roots)
        got = verdict({"tool_name": "Bash", "tool_input": {"command": e2e_bash}})
        if got == DENY:
            passed += 1
        else:
            false_neg.append((f"e2e Bash → {e2e_bash}", got))
        total += 1

        e2e_codex = adapt("printf x > src/codex-marker.ts", roots)
        got = verdict({"tool_name": "exec_command", "tool_input": {"cmd": e2e_codex}})
        if got == DENY:
            passed += 1
        else:
            false_neg.append((f"e2e exec_command → {e2e_codex}", got))
        total += 1

    print(f"directive-guard self-test: {passed}/{total}  (roots: {', '.join(roots)})\n")

    if false_neg:
        print(f"FALSE NEGATIVES ({len(false_neg)}) — the process can be bypassed:")
        for case, got in false_neg:
            print(f"  [{got}] {case}")
        print()

    if false_pos:
        print(f"FALSE POSITIVES ({len(false_pos)}) — legitimate work blocked:")
        for case, got in false_pos:
            print(f"  [{got}] {case}")
        print()

    if false_pos or false_neg:
        return 1

    print("No false positives, no false negatives.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
