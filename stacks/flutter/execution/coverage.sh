#!/usr/bin/env bash
#
# DOE — Coverage gate (full gate, local / CI). Flutter / Dart.
# Green if and only if: `flutter analyze` is clean, every test passes, and coverage of each
# GATE-ELIGIBLE lib/ file changed vs base (default develop) is >= threshold (default 80%).
# A changed gate-eligible file with no covered line = RED.
#
# Perimeter: the gate measures only code covered by deterministic, offline unit tests
# (models, providers, repositories, utils). The widget/platform layer is out of perimeter
# and listed in SKIP_PATTERNS: those files are LOGGED as excluded, never ignored in silence
# (an invisible skip-list turns the gate into theatre).
# KEEP_PATTERNS is the exception to the exception: pure logic living inside an excluded
# folder that must stay measured.
#
# Usage:
#   .doe/execution/coverage.sh                      # 80% threshold on files changed vs develop
#   DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh  # custom threshold
#   DOE_BASE_REF=main  .doe/execution/coverage.sh   # custom diff base
#
# bash 3.2 compatible (macOS): no mapfile/readarray, no associative arrays.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

MIN="${DOE_COVERAGE_MIN:-80}"
BASE="${DOE_BASE_REF:-develop}"

# ── Keep-list: pure logic inside out-of-perimeter folders ────────────────────
# Wins over the skip-list. It exists because skips are per folder, but inside those folders
# lives code that is plain Dart and deserves to be measured like any model.
# Rule: a file enters here when it has no dependency on widgets / BuildContext / plugins.
# This list can only make the gate STRICTER, never more permissive.
#
# Format: "path substring|reason". Replace the examples with your own.
KEEP_PATTERNS=(
  "lib/pages/chat/markdown/markdown_parser.dart|pure Dart parser: testable line by line"
  "lib/components/haptics/vibration_type.dart|enum with vibration patterns: pure logic"
)

# ── Skip-list: layers outside the unit perimeter ─────────────────────────────
# Format: "path substring|reason". A file enters here because it is NOT testable with
# deterministic offline unit tests, never because excluding it is convenient.
# The list is documented in .doe/README.md ("Test scope"): keep it short and justify every
# addition, otherwise the gate stops biting where it matters.
SKIP_PATTERNS=(
  "lib/pages/|widget layer: extract the logic into lib/utils and test it there, not the widget"
  "lib/components/|widget layer: same reason"
  "lib/themes/|design tokens: no branch to cover"
  "lib/animations/|route transitions: need a widget tree"
  "_dialog_helper.dart|opens a dialog: needs a real BuildContext"
  "lib/services/screenshot/|native channels: capture and share do not exist off-device"
  "/firebase_|platform-bound plugin: Firebase SDK"
  # Single-FILE exclusions inside folders that stay measured: the pattern is the full path
  # precisely so it does not swallow the folder (see .doe/README.md).
  "lib/api/api_error_type.dart|static const only: zero executable lines, no lcov record possible"
  "lib/repositories/interfaces/|abstract classes and typedefs: no body to execute"
  "lib/providers/route/route_provider.dart|GoRouter + builder with BuildContext: needs a widget tree"
)
# Note on the plugin patterns: they are anchored to the file-name PREFIX (`/firebase_`) and
# not to the bare substring. With a bare substring, a future pure-logic file such as
# lib/utils/firebase_message_parser.dart would silently drop out of the measurement, inside
# folders the README declares "stay measured".

# Keep reason for $1, empty string when the file is not in the keep-list.
keep_reason() {
  local f="$1" entry pat
  for entry in "${KEEP_PATTERNS[@]}"; do
    pat="${entry%%|*}"
    case "$f" in
      *"$pat"*) printf '%s' "${entry#*|}"; return 0 ;;
    esac
  done
  printf ''
}

# Skip reason for $1, empty string when the file is gate-eligible.
skip_reason() {
  local f="$1" entry pat
  [ -n "$(keep_reason "$f")" ] && { printf ''; return 0; }
  for entry in "${SKIP_PATTERNS[@]}"; do
    pat="${entry%%|*}"
    case "$f" in
      *"$pat"*) printf '%s' "${entry#*|}"; return 0 ;;
    esac
  done
  printf ''
}

# The same substrings, one per line, for the KPI computation in awk.
skip_pats=""
for entry in "${SKIP_PATTERNS[@]}"; do
  skip_pats="${skip_pats}${entry%%|*}
"
done
keep_pats=""
for entry in "${KEEP_PATTERNS[@]}"; do
  keep_pats="${keep_pats}${entry%%|*}
"
done

# Project KPI: the global lcov total is dominated by the widget layer that sits outside the
# perimeter, so it is not the number that measures the gate's work and must not be read as
# a failure. The gate prints the KPI computed on the perimeter alone (same skip/keep
# classification as the per-file loop).
print_kpi() {
  # Patterns travel through ENVIRON rather than -v: on BSD awk a newline inside a -v value
  # breaks the assignment.
  DOE_SKIP_PATS="$skip_pats" DOE_KEEP_PATS="$keep_pats" awk '
    BEGIN {
      n = split(ENVIRON["DOE_SKIP_PATS"], P, "\n")
      m = split(ENVIRON["DOE_KEEP_PATS"], K, "\n")
    }
    /^SF:/ {
      sf = substr($0, 4); skip = 0
      for (i = 1; i <= n; i++) if (P[i] != "" && index(sf, P[i]) > 0) { skip = 1; break }
      if (skip) for (i = 1; i <= m; i++) if (K[i] != "" && index(sf, K[i]) > 0) { skip = 0; break }
    }
    /^LF:/ { v = substr($0, 4) + 0; t_lf += v; if (!skip) nw_lf += v }
    /^LH:/ { v = substr($0, 4) + 0; t_lh += v; if (!skip) nw_lh += v }
    END {
      if (nw_lf > 0)
        printf "▶ non-widget KPI (gate perimeter): %d/%d = %.1f%%\n", nw_lh, nw_lf, nw_lh * 100 / nw_lf
      if (t_lf > 0)
        printf "  global lcov: %d/%d = %.1f%% (includes the widget layer outside the perimeter: not the number to watch)\n", t_lh, t_lf, t_lh * 100 / t_lf
    }
  ' "$LCOV"
}

# ── Widget-test guard ────────────────────────────────────────────────────────
# Duplicated from run.sh on purpose: .gitignore tracks only run.sh, coverage.sh and
# directive_guard.py (`/.doe/execution/*` + negations), so a shared file such as
# _widget_guard.sh would never reach the CI clone and this script — which is exactly the
# one running in CI — would fail on the source.
echo "▶ widget-test guard (unit perimeter)"
offenders="$(grep -rlE '(^|[^A-Za-z0-9_])testWidgets[[:space:]]*\(' test --include='*.dart' 2>/dev/null \
  | grep -v '^test/widget/' || true)"
if [ -n "$offenders" ]; then
  echo "✗ widget tests outside test/widget/:"
  printf '    %s\n' $offenders
  echo "  Widget tests are outside the gate perimeter (.doe/README.md § Test scope)."
  exit 1
fi

echo "▶ flutter analyze"
flutter analyze

# Same target as run.sh: test/widget/ never enters the measured suite.
if [ -d test/widget ]; then
  COV_TARGETS="$(/bin/ls -d test/* | grep -v '^test/widget$' | tr '\n' ' ')"
  echo "▶ flutter test --coverage $COV_TARGETS(test/widget/ excluded: out of perimeter)"
  # shellcheck disable=SC2086
  flutter test --coverage $COV_TARGETS
else
  echo "▶ flutter test --coverage"
  flutter test --coverage
fi

LCOV="coverage/lcov.info"
[ -f "$LCOV" ] || { echo "✗ $LCOV not generated — coverage gate failed"; exit 1; }

# Dart files under lib/ changed vs base (generated files excluded).
# --diff-filter=d excludes DELETED files: they no longer exist, have no lines to cover and
# no lcov record. Without this filter they landed in the "no coverage" branch and removing
# dead code failed the gate.
CHANGED="$(git diff --name-only --diff-filter=d "$BASE"...HEAD -- lib \
  | grep '\.dart$' | grep -v '\.g\.dart$' | grep -v '\.freezed\.dart$' || true)"

if [ -z "$CHANGED" ]; then
  echo "✓ No lib/ file changed vs $BASE → coverage gate not applicable"
  print_kpi
  echo "✓ GATE GREEN (coverage)"
  exit 0
fi

echo "▶ coverage of changed files (threshold ${MIN}%):"
fail=0
total_lf=0
total_lh=0
measured=0
skipped=0
kept=0

# Heredoc (not a pipe) → the while runs in the current shell, so the variables persist.
while IFS= read -r f; do
  [ -z "$f" ] && continue

  reason="$(skip_reason "$f")"
  if [ -n "$reason" ]; then
    printf "  ⊘ %-52s skip (%s)\n" "$f" "$reason"
    skipped=$(( skipped + 1 ))
    continue
  fi

  # Deleted in the working tree but not committed yet: same reasoning as committed
  # deletions, there is no file to cover.
  if [ ! -f "$f" ]; then
    printf "  ⊘ %-52s skip (absent from the working tree)\n" "$f"
    skipped=$(( skipped + 1 ))
    continue
  fi

  [ -n "$(keep_reason "$f")" ] && kept=$(( kept + 1 ))

  # Extract LH/LF from the file's lcov record. SF may be relative or absolute: match on
  # equality or on suffix.
  vals="$(awk -v file="$f" '
    /^SF:/ { sf=substr($0,4); found = (sf==file || sf ~ ("/" file "$")) ? 1 : 0 }
    found && /^LF:/ { lf=substr($0,4) }
    found && /^LH:/ { lh=substr($0,4) }
    found && /^end_of_record/ { print (lh+0), (lf+0); exit }
  ' "$LCOV")"
  lh="$(echo "$vals" | awk '{print $1}')"; lh="${lh:-0}"
  lf="$(echo "$vals" | awk '{print $2}')"; lf="${lf:-0}"

  measured=$(( measured + 1 ))
  if [ "$lf" -eq 0 ]; then
    printf "  ✗ %-52s no coverage (untested file)\n" "$f"
    fail=1
    continue
  fi
  pct=$(( lh * 100 / lf ))
  total_lf=$(( total_lf + lf ))
  total_lh=$(( total_lh + lh ))
  if [ "$pct" -lt "$MIN" ]; then
    printf "  ✗ %-52s %d%% (%d/%d)\n" "$f" "$pct" "$lh" "$lf"
    fail=1
  else
    printf "  ✓ %-52s %d%% (%d/%d)\n" "$f" "$pct" "$lh" "$lf"
  fi
done <<EOF
$CHANGED
EOF

echo "▶ changed files: ${measured} measured, ${skipped} excluded (out of perimeter, see ⊘)"
if [ "$kept" -gt 0 ]; then
  echo "  of which ${kept} inside excluded folders but measured via keep-list (pure logic)"
fi
if [ "$total_lf" -gt 0 ]; then
  echo "▶ total of measured files: $(( total_lh * 100 / total_lf ))% (${total_lh}/${total_lf})"
fi
print_kpi

if [ "$fail" -ne 0 ]; then
  echo "✗ COVERAGE GATE RED — one or more files below ${MIN}% or untested"
  exit 1
fi

echo "✓ GATE GREEN (coverage)"
