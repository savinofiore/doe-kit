#!/usr/bin/env bash
#
# DOE L2 — fast gate (Python).
#
# typecheck (mypy) + lint (ruff) + unit tests (pytest).
# This is the deterministic gate: a directive is done if and only if this script exits 0.
#
#   .doe/execution/run.sh                    # full gate
#   .doe/execution/run.sh tests/core         # narrow to a path
#   .doe/execution/run.sh --name "discount"  # filter by test name
#   .doe/execution/run.sh --quick            # skip lint + typecheck (fast RED→GREEN loop)
#
# For the gate with coverage (the one that runs in CI): .doe/execution/coverage.sh
#
# Adjust SRC below if your package does not live in src/.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SRC="${DOE_SRC_DIR:-src}"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
if [[ ! -t 1 ]]; then RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; fi

QUICK=0
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)
      QUICK=1
      shift
      ;;
    --name)
      if [[ $# -lt 2 ]]; then
        echo "${RED}run.sh: --name requires a value${OFF}" >&2
        exit 64
      fi
      PYTEST_ARGS+=(-k "$2")
      shift 2
      ;;
    -h|--help)
      sed -n '3,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

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

# A missing tool must fail the gate, never pass quietly: a gate that skips the step it
# cannot run is a gate that reports green on unchecked code.
require() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "${RED}✗ $1 not found${OFF} — install it (${2}) or remove the step from run.sh" >&2
  FAILED+=("$1 missing")
  return 1
}

if [[ $QUICK -eq 0 ]]; then
  require mypy "pip install mypy" && step "typecheck" mypy "$SRC"
  require ruff "pip install ruff" && step "lint" ruff check .
else
  echo
  echo "${YELLOW}── typecheck + lint (skipped: --quick) ──${OFF}"
fi

require pytest "pip install pytest" \
  && step "test" pytest -q ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}

echo
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "${GREEN}${BOLD}GATE GREEN${OFF}"
  exit 0
fi

echo "${RED}${BOLD}GATE RED${OFF} — failed: ${FAILED[*]}"
echo "${YELLOW}Remember: a red test means the code is wrong, never the test.${OFF}"
exit 1
