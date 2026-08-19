#!/usr/bin/env python3
"""
DOE — directive guard (PreToolUse hook).

Makes the rule "no code change without a directive" mechanical. It blocks two write paths
into the protected roots until `.doe/directives/` holds a non-template directive with
`STATE: APPROVED`:

  1. the write tools — Edit / Write / MultiEdit / NotebookEdit;
  2. Bash commands that write — redirections (`>`, `>>`, `tee`), `sed -i`, `cp`/`mv`,
     `rm`, `git apply`, interpreter one-liners.

Path 2 exists for a concrete case: regenerating generated types is often
`npx supabase gen types ... > src/types/database.ts` — a write into `src/` that never goes
through an Edit tool. Without it, the whole process is bypassed by a redirection.

Outside the protected roots (docs, `.doe/`, config) nothing is blocked: the directive itself
must be writable while the guard is armed.

Configuration — `.doe/doe.config.json` at the repo root:

    { "protected_roots": ["lib", "test"] }

Falls back to `DOE_PROTECTED_ROOTS` (comma-separated), then to auto-detection
(`lib`+`test` if a `pubspec.yaml` exists, otherwise `src`+`tests`).

Wiring: `.claude/settings.json` → hooks.PreToolUse.

Manual use (diagnosis, without going through Claude):

    .doe/execution/directive_guard.py --status
    .doe/execution/directive_guard.py --explain 'npx supabase gen types > src/types/database.ts'

Emergency escape, outside the process:

    export DOE_BYPASS=1
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import traceback
from pathlib import Path

# Tools that write to disk. Read/Grep/Glob are not intercepted: the guard protects writing,
# not reading. A guard that blocks `grep` gets disabled within the hour, and a disabled
# guard protects nothing.
GUARDED_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

DIRECTIVES_DIR = Path(".doe/directives")
CONFIG_FILE = Path(".doe/doe.config.json")

# Templates are not directives: they never unlock the guard, even if someone writes
# APPROVED inside one by mistake.
TEMPLATE_PREFIX = "00_"

DEFAULT_ROOTS = ("src", "tests")
DART_ROOTS = ("lib", "test")


# ── configuration ───────────────────────────────────────────────────────────────


def protected_roots(root: Path) -> tuple[str, ...]:
    """Protected roots, repo-relative. Config file → env → auto-detection."""
    config = root / CONFIG_FILE
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            roots = data.get("protected_roots")
            if isinstance(roots, list) and roots:
                return tuple(str(r).strip("/") for r in roots)
        except (OSError, json.JSONDecodeError):
            pass  # a broken config must not silently disarm the guard

    env = os.environ.get("DOE_PROTECTED_ROOTS")
    if env:
        return tuple(part.strip().strip("/") for part in env.split(",") if part.strip())

    if (root / "pubspec.yaml").is_file():
        return DART_ROOTS
    return DEFAULT_ROOTS


# ── Bash command analysis ───────────────────────────────────────────────────────

# Redirection to a file: `> f`, `>> f`, `2> f`, `&> f`, `>| f`.
# The `(?!&)` excludes `2>&1`, which duplicates a file descriptor and writes to no path.
REDIRECT_RE = re.compile(
    r"""(?:^|[\s;&|(])
        (?:\d+|&)?
        >{1,2}
        \|?
        \s*
        (?!&)
        ['"]?(?P<path>[^\s'";&|<>()`]+)
    """,
    re.VERBOSE,
)

# Commands where EVERY path-looking argument is a write target.
# `mv` sits here rather than in WRITE_LAST_ARG because it also removes the source: moving a
# file OUT of a protected root modifies it just as much as writing into it.
WRITE_ALL_ARGS = {"rm", "rmdir", "unlink", "truncate", "shred", "touch", "patch", "tee", "mv"}

# Commands where only the LAST argument is the destination: `cp src/a.ts /tmp/b.ts` reads
# from the protected root and leaves it intact, so it passes.
WRITE_LAST_ARG = {"cp", "ln", "install", "rsync"}

# Wrappers to skip through to find the real command.
WRAPPERS = {"sudo", "env", "nice", "time", "command", "builtin", "exec", "xargs", "nohup"}

INTERPRETERS = {"python", "python3", "node", "nodejs", "perl", "ruby", "php", "deno", "bun"}

# Write hints inside an interpreter one-liner. Without one of these, an interpreter that
# names a protected root is reading — and reading is allowed.
#
# Deliberately does NOT contain `open(`: `open(p).read()` is a read, and blocking it is
# exactly the kind of false positive that gets the guard turned off. Real writes always go
# through an explicit verb (`write`, `unlink`, `rename`, …).
INTERPRETER_WRITE_HINTS = (
    "write",
    "unlink",
    "rename",
    "truncate",
    "mkdir",
    "rmdir",
    "rmsync",
    "appendfile",
    "os.remove",
    "shutil",
)

# git subcommands that materialize code from a patch. `checkout`/`restore`/`reset` are
# deliberately absent: they are recovery operations, and blocking them only causes pain.
GIT_WRITE_SUBCMDS = {"apply", "am"}


def repo_root() -> Path:
    """Repo root. `CLAUDE_PROJECT_DIR` when available, otherwise the script location."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent.parent


def directive_state(path: Path) -> str:
    """Reads the `STATE:` declared in a directive. Returns 'UNKNOWN' when absent."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "UNKNOWN"

    for raw in text.splitlines():
        line = raw.strip().strip("*").strip()
        upper = line.upper()
        # `STATO` is accepted as a legacy alias so directives written before the English
        # rename keep unlocking the guard.
        if not (upper.startswith("STATE") or upper.startswith("STATO")):
            continue
        _, _, value = line.partition(":")
        value = value.strip().strip("*").strip().upper()
        if value:
            return value.split()[0]
    return "UNKNOWN"


def list_directives(root: Path) -> list[tuple[Path, str]]:
    """Every non-template directive with its state, sorted by name."""
    directory = root / DIRECTIVES_DIR
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith(TEMPLATE_PREFIX):
            continue
        found.append((path, directive_state(path)))
    return found


def approved_directives(root: Path) -> list[Path]:
    return [path for path, state in list_directives(root) if state == "APPROVED"]


def is_protected(
    root: Path, file_path: str, roots: tuple[str, ...], cwd: Path | None = None
) -> str | None:
    """Returns the repo-relative path when the file sits under a protected root, else None."""
    if not file_path:
        return None

    token = file_path.strip().strip("'\"")
    if not token:
        return None

    # Paths with unexpanded variables (`$CLAUDE_PROJECT_DIR/src/...`) cannot be resolved,
    # but a protected segment inside one still has to count.
    if "$" in token or "~" in token:
        for root_name in roots:
            if re.search(rf"(?:^|/){re.escape(root_name)}/", token):
                return token
        return None

    target = Path(token)
    if not target.is_absolute():
        target = ((cwd or root) / target).resolve()
    else:
        target = target.resolve()

    try:
        rel = target.relative_to(root)
    except ValueError:
        # Outside the repo: none of the guard's business.
        return None

    parts = rel.parts
    if parts and parts[0] in roots:
        return rel.as_posix()
    return None


HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(?P<delim>[A-Za-z_][A-Za-z0-9_]*)(['\"]?)")


def strip_heredoc_bodies(command: str) -> str:
    """
    Drops the BODY of heredocs, keeping the command line that opens them.

    A heredoc body is data, not shell: a commit message that *describes* a redirection
    (`... > src/types/database.ts`) is not a redirection. Without this, the guard blocks the
    commit that documents the guard — which happened — and that is exactly the kind of false
    positive that gets enforcement switched off.

    The opening line stays: `cat > src/x.ts <<'EOF'` contains a real redirection.
    """
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        match = HEREDOC_RE.search(line)
        if match:
            delim = match.group("delim")
            index += 1
            while index < len(lines) and lines[index].strip() != delim:
                index += 1
            if index < len(lines):
                kept.append(lines[index])
        index += 1
    return "\n".join(kept)


def split_segments(command: str) -> list[str]:
    """Splits a shell line into the simple commands that compose it."""
    return [seg for seg in re.split(r"\|\||&&|[;\n|]", command) if seg.strip()]


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        # Unbalanced quoting: a coarse analysis beats no analysis.
        return segment.split()


def real_command(tokens: list[str]) -> tuple[str, list[str]]:
    """Skips variable assignments and wrappers to find the real command and its arguments."""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            i += 1
            continue
        if Path(token).name in WRAPPERS:
            i += 1
            continue
        break
    if i >= len(tokens):
        return "", []
    return Path(tokens[i]).name, tokens[i + 1 :]


def find_writes(
    command: str, root: Path, roots: tuple[str, ...], cwd: Path | None = None
) -> list[tuple[str, str]]:
    """
    Finds writes into the protected roots inside a shell command.

    Returns a list of `(path, construct)`. Empty list = no write detected.

    This is not a shell parser and does not pretend to be one: it catches the constructs
    people actually use. The guard exists to stop the process being bypassed by
    *inattention*, not to resist someone bypassing it on purpose — for that there is
    already DOE_BYPASS, which at least is explicit and visible.
    """
    writes: list[tuple[str, str]] = []
    command = strip_heredoc_bodies(command)

    def record(path: str | None, construct: str) -> None:
        if path and (path, construct) not in writes:
            writes.append((path, construct))

    # 1. Redirections, searched over the whole line: they cross segment boundaries.
    for match in REDIRECT_RE.finditer(command):
        record(is_protected(root, match.group("path"), roots, cwd), "redirection")

    # 2. Commands that write their own arguments.
    for segment in split_segments(command):
        tokens = tokenize(segment)
        if not tokens:
            continue

        name, args = real_command(tokens)
        if not name:
            continue

        positional = [a for a in args if not a.startswith("-")]

        if name == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub in GIT_WRITE_SUBCMDS:
                targets = [is_protected(root, a, roots, cwd) for a in positional[1:]]
                if any(targets):
                    for target in targets:
                        record(target, f"git {sub}")
                else:
                    # The patch content is not inspectable from here and almost always
                    # touches code: with the guard armed there is no legitimate use.
                    record(f"(patch: {' '.join(positional[1:]) or 'stdin'})", f"git {sub}")
            continue

        if name in {"sed", "perl"} and any(
            a.startswith("-i") or a == "--in-place" for a in args
        ):
            for arg in positional:
                record(is_protected(root, arg, roots, cwd), f"{name} in-place")
            continue

        if name in WRITE_ALL_ARGS:
            for arg in positional:
                record(is_protected(root, arg, roots, cwd), name)
            continue

        if name in WRITE_LAST_ARG and positional:
            record(is_protected(root, positional[-1], roots, cwd), f"{name} (destination)")
            continue

        if name in INTERPRETERS:
            inline = " ".join(args)
            has_inline_flag = any(a in {"-c", "-e", "--eval", "--print"} for a in args)
            lowered = inline.lower()
            if has_inline_flag and any(h in lowered for h in INTERPRETER_WRITE_HINTS):
                alternation = "|".join(re.escape(r) for r in roots)
                for candidate in re.findall(rf"[\w./$~-]*(?:{alternation})/[\w./-]+", inline):
                    record(is_protected(root, candidate, roots, cwd), f"{name} one-liner")
            continue

    return writes


# ── hook output ─────────────────────────────────────────────────────────────────


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def allow() -> None:
    sys.exit(0)


NEXT_STEPS = """\
What to do now, in order:

  1. Do NOT work around the block and do NOT write code.
  2. Start the interview: /directive
     First question, always: is this a FEATURE or a BUG?
  3. Analyse the files and tests involved, run the baseline (.doe/execution/run.sh),
     then write .doe/directives/NN_name.md with STATE: DRAFT — Test Contract section
     included — and STOP.
  4. The human re-reads it and sets STATE: APPROVED by hand. Only then does the guard
     unlock and /execute NN become possible.
"""

BLOCK_MESSAGE = """\
DOE directive-guard: write BLOCKED on {rel}

No directive with `STATE: APPROVED` in .doe/directives/ — so {roots} are read-only.
This is not a style preference: it is the gate of the DOE process.

{next_steps}{state_report}
Full spec: .doe/README.md
"""

BASH_BLOCK_MESSAGE = """\
DOE directive-guard: Bash command BLOCKED

The command writes into a protected directory without going through an Edit tool:

{targets}

No directive with `STATE: APPROVED` in .doe/directives/, so {roots} are read-only — and the
rule holds for every write path, not just Edit/Write.

{next_steps}{state_report}
Full spec: .doe/README.md
"""


def state_report(root: Path) -> str:
    directives = list_directives(root)
    if not directives:
        return "\nCurrent state: .doe/directives/ contains no directive.\n"
    lines = ["\nDirectives present:"]
    for path, state in directives:
        lines.append(f"  - {path.name}: STATE: {state}")
    lines.append("")
    return "\n".join(lines)


def handle_hook() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        allow()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Unparseable payload: not a recognisable write event.
        allow()
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    root = repo_root()
    roots = protected_roots(root)
    roots_label = " and ".join(f"{r}/" for r in roots)

    cwd_raw = payload.get("cwd")
    cwd = Path(cwd_raw).resolve() if cwd_raw else None

    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not command.strip():
            allow()

        writes = find_writes(command, root, roots, cwd)
        if not writes:
            allow()

        if approved_directives(root):
            allow()

        targets = "\n".join(f"  - {path}  ({construct})" for path, construct in writes)
        deny(
            BASH_BLOCK_MESSAGE.format(
                targets=targets,
                roots=roots_label,
                next_steps=NEXT_STEPS,
                state_report=state_report(root),
            )
        )

    if tool_name not in GUARDED_TOOLS:
        allow()

    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

    rel = is_protected(root, file_path, roots, cwd)
    if rel is None:
        allow()

    if approved_directives(root):
        allow()

    deny(
        BLOCK_MESSAGE.format(
            rel=rel,
            roots=roots_label,
            next_steps=NEXT_STEPS,
            state_report=state_report(root),
        )
    )


def handle_status() -> None:
    root = repo_root()
    roots = protected_roots(root)
    directives = list_directives(root)
    approved = [p for p, s in directives if s == "APPROVED"]

    print(f"repo root:   {root}")
    print(f"bypass:      {'ACTIVE (DOE_BYPASS=1)' if os.environ.get('DOE_BYPASS') == '1' else 'no'}")
    print(f"protected:   {', '.join(r + '/' for r in roots)}")
    print(f"intercepts:  {', '.join(sorted(GUARDED_TOOLS))}, Bash (writes)")
    print()

    if not directives:
        print("directives:  none")
    else:
        print("directives:")
        for path, state in directives:
            print(f"  - {path.name:<40} STATE: {state}")
    print()

    if os.environ.get("DOE_BYPASS") == "1":
        print("GUARD: BYPASSED — protected roots are writable (emergency escape).")
    elif approved:
        names = ", ".join(p.name for p in approved)
        print(f"GUARD: UNLOCKED by {names} — protected roots are writable.")
    else:
        print("GUARD: ARMED — protected roots are read-only. Run /directive.")


def handle_explain(command: str) -> None:
    """Shows how the guard reads a command, without running it."""
    root = repo_root()
    roots = protected_roots(root)
    writes = find_writes(command, root, roots)
    print(f"command: {command}")
    if not writes:
        print("verdict: no protected write detected → ALLOW")
        return
    print("writes detected:")
    for path, construct in writes:
        print(f"  - {path}  ({construct})")
    print(
        "verdict: DENY"
        if not approved_directives(root)
        else "verdict: ALLOW (an APPROVED directive unlocks the guard)"
    )


def main() -> None:
    if "--status" in sys.argv:
        handle_status()
        return

    if "--explain" in sys.argv:
        index = sys.argv.index("--explain")
        if index + 1 >= len(sys.argv):
            print("--explain requires a command to analyse", file=sys.stderr)
            sys.exit(64)
        handle_explain(sys.argv[index + 1])
        return

    if os.environ.get("DOE_BYPASS") == "1":
        allow()

    handle_hook()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - the guard fails closed, but stays diagnosable
        deny(
            "DOE directive-guard: internal hook error, write blocked for safety.\n\n"
            + traceback.format_exc()
            + "\nIf the guard itself is broken, fix .doe/execution/directive_guard.py "
            "(it is not under a protected root, so it is writable) or use DOE_BYPASS=1."
        )
