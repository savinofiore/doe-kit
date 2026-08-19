#!/usr/bin/env bash
#
# DOE Kit installer.
#
# One-liner (clones itself into a temp dir, then installs into the current directory):
#   curl -fsSL https://raw.githubusercontent.com/savinofiore/doe-kit/main/install.sh | bash -s -- --stack flutter
#
# From a clone:
#   ./install.sh --stack web-ts             # installs into the current directory
#   ./install.sh --stack flutter /path/to/project
#   ./install.sh --stack web-ts --dry-run .
#
# Copies into the target project:
#   .doe/README.md            the method, where the agent will read it
#   .doe/doe.config.json      protected roots
#   .doe/directives/          the three templates
#   .doe/execution/           guard + self-test (core) and gate scripts (stack)
#   .claude/skills/           the DOE skills (core + stack)
#   .claude/settings.json     the PreToolUse hook, MERGED into any existing file
#
# Nothing under your source roots is touched. Existing files are never overwritten unless
# --force is given; settings.json is always merged, never replaced.

set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

REPO_URL="${DOE_KIT_REPO:-https://github.com/savinofiore/doe-kit.git}"
REPO_REF="${DOE_KIT_REF:-main}"

# Piped from curl: the "script directory" is wherever bash was launched, not a checkout.
# Detect it by looking for a file only the real kit has, and clone if it is missing.
if [[ -z "$KIT" || ! -f "$KIT/core/execution/directive_guard.py" ]]; then
  command -v git >/dev/null 2>&1 || { echo "doe-kit: git is required" >&2; exit 69; }
  KIT="$(mktemp -d)/doe-kit"
  echo "fetching doe-kit ($REPO_REF)..."
  git clone --quiet --depth 1 --branch "$REPO_REF" "$REPO_URL" "$KIT" \
    || { echo "doe-kit: could not clone $REPO_URL" >&2; exit 69; }
  trap 'rm -rf "$(dirname "$KIT")"' EXIT
fi

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
if [[ ! -t 1 ]]; then RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; fi

STACK=""
TARGET=""
FORCE=0
DRY=0
NEEDS_CONVENTIONS=0

usage() {
  sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  echo
  echo "Available stacks: $(/bin/ls -1 "$KIT/stacks" | grep -vE '\.md$|^shared$' | tr '\n' ' ')"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)   STACK="${2:-}"; shift 2 ;;
    --force)   FORCE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)        echo "${RED}unknown option: $1${OFF}" >&2; usage; exit 64 ;;
    *)         TARGET="$1"; shift ;;
  esac
done

[[ -n "$STACK"  ]] || { echo "${RED}--stack is required${OFF}" >&2; usage; exit 64; }
TARGET="${TARGET:-.}"   # the one-liner runs inside the project it is installing into

STACK_DIR="$KIT/stacks/$STACK"
[[ -d "$STACK_DIR" && "$STACK" != "shared" ]] \
  || { echo "${RED}unknown stack: $STACK${OFF}" >&2; usage; exit 64; }

TARGET="$(cd "$TARGET" && pwd)"
[[ -d "$TARGET" ]] || { echo "${RED}target does not exist: $TARGET${OFF}" >&2; exit 66; }

echo "${BOLD}DOE Kit${OFF} → $TARGET  (stack: $STACK)"
[[ $DRY -eq 1 ]] && echo "${YELLOW}dry run: nothing will be written${OFF}"
echo

run() {
  if [[ $DRY -eq 1 ]]; then
    echo "  would run: $*"
  else
    "$@"
  fi
}

# Copies $1 to $2, refusing to clobber unless --force.
copy() {
  local src="$1" dst="$2"
  if [[ -e "$dst" && $FORCE -eq 0 ]]; then
    echo "  ${YELLOW}skip${OFF}  ${dst#$TARGET/}  (exists — use --force to overwrite)"
    return
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp -R "$src" "$dst"
  echo "  ${GREEN}ok${OFF}    ${dst#$TARGET/}"
}

# ── .doe ────────────────────────────────────────────────────────────────────────

echo "${BOLD}.doe/${OFF}"

copy "$KIT/core/execution/directive_guard.py" "$TARGET/.doe/execution/directive_guard.py"
copy "$KIT/core/execution/guard_selftest.py"  "$TARGET/.doe/execution/guard_selftest.py"

for f in "$STACK_DIR/execution/"*; do
  copy "$f" "$TARGET/.doe/execution/$(basename "$f")"
done

for t in "$KIT/core/templates/"*.md; do
  copy "$t" "$TARGET/.doe/directives/$(basename "$t")"
done

# Convention template, when the stack ships one. Deliberately copied as `.example.json`:
# the stack skills refuse to run without `.doe/conventions.json`, and a half-filled config
# naming another project's design tokens is worse than no config — it produces "fixes" that
# compile and are wrong.
if [[ -f "$STACK_DIR/conventions.example.json" ]]; then
  copy "$STACK_DIR/conventions.example.json" "$TARGET/.doe/conventions.example.json"
  NEEDS_CONVENTIONS=1
fi

# The method doc travels with the project: the agent reads .doe/README.md, not this repo.
if [[ -e "$TARGET/.doe/README.md" && $FORCE -eq 0 ]]; then
  echo "  ${YELLOW}skip${OFF}  .doe/README.md  (exists — use --force to overwrite)"
elif [[ $DRY -eq 1 ]]; then
  echo "  would write: .doe/README.md  (methodology + stack notes)"
else
  mkdir -p "$TARGET/.doe"
  {
    cat "$KIT/docs/methodology.md"
    echo
    echo "---"
    echo
    sed -n '/^## Gate/,$p' "$STACK_DIR/README.md"
  } > "$TARGET/.doe/README.md"
  echo "  ${GREEN}ok${OFF}    .doe/README.md"
fi

# Protected roots, per stack.
case "$STACK" in
  flutter) ROOTS='["lib", "test"]' ;;
  *)       ROOTS='["src", "tests"]' ;;
esac

if [[ -e "$TARGET/.doe/doe.config.json" && $FORCE -eq 0 ]]; then
  echo "  ${YELLOW}skip${OFF}  .doe/doe.config.json  (exists)"
elif [[ $DRY -eq 1 ]]; then
  echo "  would write: .doe/doe.config.json  → protected_roots: $ROOTS"
else
  printf '{\n  "protected_roots": %s\n}\n' "$ROOTS" > "$TARGET/.doe/doe.config.json"
  echo "  ${GREEN}ok${OFF}    .doe/doe.config.json  (protected_roots: $ROOTS)"
fi

if [[ $DRY -eq 0 ]]; then
  chmod +x "$TARGET/.doe/execution/"*.sh "$TARGET/.doe/execution/"*.py 2>/dev/null || true
  chmod +x "$TARGET/.doe/execution/"*.mjs 2>/dev/null || true
fi

# ── .claude/skills ──────────────────────────────────────────────────────────────

echo
echo "${BOLD}.claude/skills/${OFF}"

# Every skill lives once, in $KIT/skills/. Each level's skills.txt says which of them it
# installs, so the plugin (which loads them all) and this installer never drift apart.
install_skills_from() {
  local manifest="$1" name
  [[ -f "$manifest" ]] || return 0
  while IFS= read -r name; do
    name="${name%%#*}"; name="${name// /}"
    [[ -z "$name" ]] && continue
    if [[ ! -d "$KIT/skills/$name" ]]; then
      echo "  ${RED}missing${OFF} skill '$name' listed in ${manifest#$KIT/}" >&2
      continue
    fi
    copy "$KIT/skills/$name" "$TARGET/.claude/skills/$name"
  done < "$manifest"
}

install_skills_from "$KIT/core/skills.txt"
install_skills_from "$KIT/stacks/shared/skills.txt"
install_skills_from "$STACK_DIR/skills.txt"

# ── .claude/settings.json (merge) ───────────────────────────────────────────────

echo
echo "${BOLD}.claude/settings.json${OFF}"

if [[ $DRY -eq 1 ]]; then
  echo "  would merge the PreToolUse hook into .claude/settings.json"
else
  mkdir -p "$TARGET/.claude"
  python3 - "$TARGET" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
settings_path = target / ".claude/settings.json"

hook = {
    "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
    "hooks": [
        {
            "type": "command",
            "command": 'python3 "$CLAUDE_PROJECT_DIR/.doe/execution/directive_guard.py"',
            "timeout": 5,
            "statusMessage": "DOE directive guard...",
        }
    ],
}

settings = {}
if settings_path.is_file():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("  settings.json is not valid JSON — not touching it.")
        print("  Add the hook by hand (see docs/adoption.md).")
        raise SystemExit(0)

hooks = settings.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])

already = any(
    "directive_guard.py" in json.dumps(entry) for entry in pre if isinstance(entry, dict)
)
if already:
    print("  hook already wired — left as is.")
    raise SystemExit(0)

pre.append(hook)
settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
print("  hook wired into .claude/settings.json")
PY
fi

# ── next steps ──────────────────────────────────────────────────────────────────

cat <<EOF

${BOLD}Next steps${OFF}

  1. Check the gate matches your project:  ${BOLD}.doe/execution/run.sh${OFF}
     It must be GREEN on a clean tree before you arm anything.
  2. Verify the guard:
       .doe/execution/directive_guard.py --status     → GUARD: ARMED
       .doe/execution/guard_selftest.py               → no false positives/negatives
  3. Add the process section to your CLAUDE.md — see docs/adoption.md § 6.
  4. Turn on CI — see docs/enforcement.md.

  Emergency escape, outside the process:  export DOE_BYPASS=1
EOF

if [[ $NEEDS_CONVENTIONS -eq 1 && ! -f "$TARGET/.doe/conventions.json" ]]; then
  cat <<EOF

${YELLOW}${BOLD}One more thing${OFF} — the stack skills need your project's conventions:

    cp .doe/conventions.example.json .doe/conventions.json
    \$EDITOR .doe/conventions.json

  Fill in YOUR token classes, paths and naming rules. ${BOLD}scaffold-feature${OFF},
  ${BOLD}fix-style${OFF} and ${BOLD}riverpod-architect${OFF} refuse to run without it, on purpose:
  guessing a design system produces fixes that compile and are wrong.
EOF
fi
