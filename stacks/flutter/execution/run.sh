#!/usr/bin/env bash
#
# DOE L2 — Execution: the deterministic gate for directives (Flutter / Dart).
# Generated code is correct if and only if this gate exits 0.
#
# Perimeter: ONLY deterministic, offline unit tests. Widget tests are out of the gate — a
# `testWidgets` drags in the framework bootstrap and as many sources of non-determinism
# (timers, frames, assets, plugins). They live in `test/widget/`, which is not part of the
# target; a `testWidgets(` outside that folder fails the gate with an explicit message.
# See .doe/README.md, section "Test scope".
#
# Usage:
#   .doe/execution/run.sh                 # full gate: analyze + whole unit suite
#   .doe/execution/run.sh test/models     # narrow to a path
#   .doe/execution/run.sh --name "Quiz"   # filter by test name
#
# Every argument is forwarded to `flutter test`.
#
# bash 3.2 compatible (macOS): no mapfile/readarray, no associative arrays.
set -euo pipefail

# Walk up to the project root (this file lives in .doe/execution/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# ── Guard: no widget tests inside the gate ───────────────────────────────────
# Matches the `testWidgets(` invocation rather than the bare word, so a mention in a
# comment or a doc does not turn the gate red by accident.
# `|| true` because grep exits 1 when it finds nothing (the healthy case) and `set -e`
# would kill the script.
echo "▶ widget-test guard (unit perimeter)"
offenders="$(grep -rlE '(^|[^A-Za-z0-9_])testWidgets[[:space:]]*\(' test --include='*.dart' 2>/dev/null \
  | grep -v '^test/widget/' || true)"
if [ -n "$offenders" ]; then
  echo "✗ widget tests outside test/widget/:"
  printf '    %s\n' $offenders
  echo "  Widget tests are outside the gate perimeter (.doe/README.md § Test scope)."
  echo "  Move the file to test/widget/, or extract the logic and test it as a unit."
  exit 1
fi

echo "▶ flutter analyze"
flutter analyze

# test/widget/ stays out of the target when the gate runs without arguments.
# While the folder does not exist the command is identical to the plain one (same suite,
# same count): the explicit branch only kicks in the day someone creates it.
# `run.sh test` and `run.sh test/` are documented forms in the header: without this
# normalisation they would let back in through the window the widget tests that the
# no-argument branch keeps out of the door.
if [ "$#" -eq 1 ] && { [ "$1" = "test" ] || [ "$1" = "test/" ]; }; then
  set --
fi

if [ "$#" -eq 0 ] && [ -d test/widget ]; then
  TARGETS="$(/bin/ls -d test/* | grep -v '^test/widget$' | tr '\n' ' ')"
  echo "▶ flutter test $TARGETS(test/widget/ excluded: out of perimeter)"
  # Deliberately unquoted: TARGETS is a list of paths meant to be split.
  # shellcheck disable=SC2086
  flutter test $TARGETS
else
  echo "▶ flutter test $*"
  flutter test "$@"
fi

echo "✓ GATE GREEN"
