#!/usr/bin/env bash
#
# DOE L2 — fast gate (TypeScript / Vitest).
#
# typecheck (tsc --noEmit) + lint (eslint) + unit tests (vitest run).
# This is the deterministic gate: a directive is done if and only if this script exits 0.
#
#   .doe/execution/run.sh                    # full gate
#   .doe/execution/run.sh tests/core/models  # narrow to a path
#   .doe/execution/run.sh --name "Post"      # filter by test name
#   .doe/execution/run.sh --quick            # skip lint (fast RED→GREEN loop)
#
# For the gate with coverage (the one that runs in CI): .doe/execution/coverage.sh

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
if [[ ! -t 1 ]]; then RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; fi

QUICK=0
VITEST_ARGS=()

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
      VITEST_ARGS+=(-t "$2")
      shift 2
      ;;
    -h|--help)
      sed -n '3,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      VITEST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ ! -d node_modules ]]; then
  echo "${YELLOW}node_modules missing → npm ci${OFF}"
  npm ci || exit 1
fi

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

step "typecheck" npx tsc --noEmit

if [[ $QUICK -eq 0 ]]; then
  step "lint" npx eslint .
else
  echo
  echo "${YELLOW}── lint (skipped: --quick) ──${OFF}"
fi

step "test" npx vitest run "${VITEST_ARGS[@]}"

echo
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "${GREEN}${BOLD}GATE GREEN${OFF}"
  exit 0
fi

echo "${RED}${BOLD}GATE RED${OFF} — failed: ${FAILED[*]}"
echo "${YELLOW}Remember: a red test means the code is wrong, never the test.${OFF}"
exit 1
