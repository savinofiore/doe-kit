#!/usr/bin/env bash
#
# DOE L2 — full gate (the one that runs in CI). Python.
#
# typecheck + lint + pytest --cov + a coverage threshold on EVERY source file CHANGED
# against the base ref. A changed file with no test = red.
#
#   .doe/execution/coverage.sh                       # 80% threshold vs main
#   DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh   # custom threshold
#   DOE_BASE_REF=develop .doe/execution/coverage.sh  # custom diff base
#   DOE_SRC_DIR=mypkg    .doe/execution/coverage.sh  # package outside src/
#
# CI needs the base ref inside the clone (fetch-depth: 0, or an explicit branch fetch).
#
# Perimeter: SKIP_PATTERNS below excludes what a deterministic offline unit test cannot
# reach. Every exclusion is LOGGED with its reason — an invisible skip-list turns the gate
# into theatre.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

MIN="${DOE_COVERAGE_MIN:-80}"
BASE="${DOE_BASE_REF:-main}"
SRC="${DOE_SRC_DIR:-src}"
XML="coverage.xml"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
if [[ ! -t 1 ]]; then RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; fi

# ── Skip-list: layers outside the unit perimeter ─────────────────────────────
# Format: "path substring|reason". A file enters here because it is NOT reachable by a
# deterministic offline unit test, never because excluding it is convenient.
# Replace these examples with your own, and justify every addition in .doe/README.md.
SKIP_PATTERNS=(
  "/migrations/|schema migrations: executed by the migration tool, not by a unit test"
  "/__main__.py|process entry point: argument parsing only, no branch worth a test"
  "/conftest.py|pytest fixtures: test support, not production code"
)

skip_reason() {
  local f="$1" entry pat
  for entry in ${SKIP_PATTERNS[@]+"${SKIP_PATTERNS[@]}"}; do
    pat="${entry%%|*}"
    case "$f" in
      *"$pat"*) printf '%s' "${entry#*|}"; return 0 ;;
    esac
  done
  printf ''
}

FAILED=()

step() {
  local label="$1"; shift
  echo
  echo "${BOLD}── ${label} ──${OFF}"
  if "$@"; then
    echo "${GREEN}✓ ${label}${OFF}"
  else
    echo "${RED}✗ ${label}${OFF}"
    FAILED+=("$label")
  fi
}

require() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "${RED}✗ $1 not found${OFF} — install it (${2})" >&2
  FAILED+=("$1 missing")
  return 1
}

require mypy   "pip install mypy"                && step "typecheck" mypy "$SRC"
require ruff   "pip install ruff"                && step "lint" ruff check .
require pytest "pip install pytest pytest-cov"   \
  && step "test + coverage" pytest -q --cov="$SRC" --cov-report=xml --cov-report=term-missing

# The per-file threshold is evaluated only when the suite passed: on a red suite the
# coverage report is partial and would produce misleading failures.
if [[ ${#FAILED[@]} -ne 0 ]]; then
  echo
  echo "${RED}${BOLD}GATE RED${OFF} — failed: ${FAILED[*]}"
  exit 1
fi

[[ -f "$XML" ]] || { echo "${RED}✗ $XML not generated — coverage gate failed${OFF}"; exit 1; }

# A missing base ref must fail, never pass quietly.
git rev-parse --verify --quiet "$BASE" >/dev/null \
  || { echo "${RED}✗ base ref '$BASE' not in this clone${OFF} — fetch it (CI: fetch-depth 0)"; exit 1; }

CHANGED="$(git diff --name-only --diff-filter=d "$BASE"...HEAD -- "$SRC" | grep '\.py$' || true)"

if [[ -z "$CHANGED" ]]; then
  echo
  echo "${GREEN}✓ no $SRC/ file changed vs $BASE → coverage gate not applicable${OFF}"
  echo "${GREEN}${BOLD}GATE GREEN${OFF}"
  exit 0
fi

echo
echo "${BOLD}── coverage on changed files (min ${MIN}%, base ${BASE}) ──${OFF}"

MEASURED=""
skipped=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  reason="$(skip_reason "$f")"
  if [[ -n "$reason" ]]; then
    printf "  ⊘ %-52s skip (%s)\n" "$f" "$reason"
    skipped=$(( skipped + 1 ))
    continue
  fi
  MEASURED="${MEASURED}${f}"$'\n'
done <<EOF
$CHANGED
EOF

fail=0
if [[ -n "$MEASURED" ]]; then
  DOE_FILES="$MEASURED" DOE_MIN="$MIN" DOE_XML="$XML" python3 <<'PY' || fail=1
import os
import sys
import xml.etree.ElementTree as ET

files = [f for f in os.environ["DOE_FILES"].splitlines() if f.strip()]
minimum = int(os.environ["DOE_MIN"])

# coverage.py writes <class filename="..."> relative to each <source> root, so a repo-relative
# path from git may or may not match. Index by path and compare on suffix.
report = {}
for cls in ET.parse(os.environ["DOE_XML"]).getroot().iter("class"):
    name = cls.get("filename") or ""
    lines = cls.find("lines")
    if lines is None:
        continue
    total = hit = 0
    for line in lines.iter("line"):
        total += 1
        hit += 1 if int(line.get("hits", "0")) else 0
    report[name] = (hit, total)


def lookup(path):
    if path in report:
        return report[path]
    for name, value in report.items():
        if path.endswith("/" + name) or name.endswith("/" + path):
            return value
    return None


failed = 0
sum_hit = sum_total = 0
for path in files:
    entry = lookup(path)
    if entry is None:
        print(f"  ✗ {path:<52} absent from the coverage report (never imported by a test)")
        failed += 1
        continue
    hit, total = entry
    if total == 0:
        print(f"  ⊘ {path:<52} skip (no executable line)")
        continue
    pct = hit * 100 // total
    sum_hit += hit
    sum_total += total
    mark = "✓" if pct >= minimum else "✗"
    print(f"  {mark} {path:<52} {pct}% ({hit}/{total})")
    if pct < minimum:
        failed += 1

if sum_total:
    print(f"▶ total of measured files: {sum_hit * 100 // sum_total}% ({sum_hit}/{sum_total})")
if failed:
    print(f"✗ COVERAGE GATE RED — {failed} file(s) below {minimum}% or untested")
    sys.exit(1)
PY
fi

echo "▶ changed files: $(printf '%s' "$MEASURED" | grep -c . || true) measured, ${skipped} excluded (out of perimeter, see ⊘)"

echo
if [[ $fail -eq 0 ]]; then
  echo "${GREEN}${BOLD}GATE GREEN${OFF}"
  exit 0
fi
echo "${RED}${BOLD}GATE RED${OFF} — coverage"
exit 1
