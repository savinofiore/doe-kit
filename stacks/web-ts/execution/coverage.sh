#!/usr/bin/env bash
#
# DOE L2 — full gate (the one that runs in CI).
#
# typecheck + lint + vitest --coverage + a coverage threshold on EVERY `src/` file
# CHANGED against the base ref. A changed file with no test = red.
#
#   .doe/execution/coverage.sh                       # 80% threshold vs main
#   DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh   # custom threshold
#   DOE_BASE_REF=develop .doe/execution/coverage.sh  # custom diff base
#
# CI needs the base ref inside the clone (fetch-depth: 0, or an explicit branch fetch).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
if [[ ! -t 1 ]]; then RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; fi

COVERAGE_MIN="${DOE_COVERAGE_MIN:-80}"
BASE_REF="${DOE_BASE_REF:-main}"

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
step "lint" npx eslint .
step "test + coverage" npx vitest run --coverage

# The per-file threshold is evaluated only when the suite passed: on a red suite the
# coverage report is partial and would produce misleading failures.
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo
  echo "${BOLD}── coverage on changed files (min ${COVERAGE_MIN}%, base ${BASE_REF}) ──${OFF}"
  if node .doe/execution/coverage-check.mjs --min "$COVERAGE_MIN" --base "$BASE_REF"; then
    echo "${GREEN}✓ coverage${OFF}"
  else
    echo "${RED}✗ coverage${OFF}"
    FAILED+=("coverage")
  fi
fi

echo
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "${GREEN}${BOLD}GATE GREEN${OFF}"
  exit 0
fi

echo "${RED}${BOLD}GATE RED${OFF} — failed: ${FAILED[*]}"
exit 1
