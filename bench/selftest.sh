#!/usr/bin/env bash
#
# Self-test for the benchmark scorer — the equivalent of guard_selftest.py.
#
# A scorer that stops discriminating between a real test suite and an assertion-free one does
# not turn anything red. It just quietly produces a beautiful, wrong benchmark. This is the
# thing that notices.
#
# It checks both directions, on a known-good and a known-bad run:
#
#   1. mutation score separates an asserting suite from a smoke-test suite
#   2. the hidden acceptance suite passes a correct solution and fails a plausible wrong one
#   3. score.py end-to-end: resolve, regression, touched-old-tests, mutation
#   4. analyze.py produces a report without falling over
#
set -euo pipefail

BENCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK="$BENCH/tasks/T01_volume_discounts"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; OFF=$'\033[0m'
[[ -t 1 ]] || { GREEN=""; RED=""; OFF=""; }
FAILED=0
ok()   { echo "${GREEN}✓${OFF} $1"; }
bad()  { echo "${RED}✗${OFF} $1"; FAILED=1; }

score_of() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['score'])" "$1"; }

# ── 1. mutation score discriminates ────────────────────────────────────────────
for kind in good lazy; do
  d="$TMP/mut_$kind"
  mkdir -p "$d"
  cp -r "$BENCH/selftest/src" "$d/src"
  cp -r "$BENCH/selftest/tests_$kind" "$d/tests"
  "$BENCH/mutation.py" --root "$d" --src src \
    --test-cmd "python3 -m unittest discover -s tests -t ." \
    --max-mutants 40 --json "$TMP/$kind.json" > /dev/null
done
GOOD=$(score_of "$TMP/good.json")
LAZY=$(score_of "$TMP/lazy.json")
echo "mutation score — asserting suite: $GOOD · smoke-test suite: $LAZY"
python3 - "$GOOD" "$LAZY" <<'PY' && ok "mutation score separates real tests from smoke tests" || bad "mutation score no longer discriminates (good=$GOOD lazy=$LAZY)"
import sys
good, lazy = float(sys.argv[1]), float(sys.argv[2])
sys.exit(0 if good >= 0.7 and lazy <= 0.15 and good - lazy >= 0.5 else 1)
PY

# ── 2 & 3. score.py on a known-good and a known-bad run ────────────────────────
RESULTS="$TMP/results"
build_run() {  # build_run ARM SOLUTION TESTS_DIR REPLACE_FIXTURE_TESTS
  local arm="$1" solution="$2" tests="$3" replace="$4"
  local cell="$RESULTS/$arm/T01_volume_discounts/0"
  mkdir -p "$cell"
  cp -r "$TASK/fixture" "$cell/workdir"
  cp "$BENCH/selftest/solutions/$solution" "$cell/workdir/src/pricing.py"
  if [[ "$replace" == "replace" ]]; then
    cp "$BENCH/selftest/$tests/test_pricing.py" "$cell/workdir/tests/test_pricing.py"
  else
    cp "$BENCH/selftest/$tests/test_pricing.py" "$cell/workdir/tests/test_discounts.py"
  fi
  cat > "$cell/meta.json" <<JSON
{"arm": "$arm", "task": "T01_volume_discounts", "seed": 0, "model": "selftest",
 "tokens": $5, "usd": null, "seconds": 1, "approvals": 0, "truncated": false}
JSON
}

build_run PASSING reference.py tests_good keep 40000
build_run FAILING broken.py    tests_lazy replace 12000

"$BENCH/score.py" "$RESULTS" > /dev/null

read_metric() { python3 -c "
import json,sys
m=json.load(open(sys.argv[1]))
print(json.dumps({
  'resolved': m['hidden']['resolved'],
  'regression_green': (m['regression'] or {}).get('green'),
  'touched': (m['pre_existing_tests'] or {}).get('count'),
  'mutation': (m['mutation'] or {}).get('score') if (m['mutation'] or {}).get('scored') else None,
}))" "$1"; }

P=$(read_metric "$RESULTS/PASSING/T01_volume_discounts/0/metrics.json")
F=$(read_metric "$RESULTS/FAILING/T01_volume_discounts/0/metrics.json")
echo "correct run: $P"
echo "broken run:  $F"

python3 - "$P" <<'PY' && ok "a correct run scores as resolved, green, untouched tests, high mutation" || bad "the scorer failed a correct run"
import json, sys
m = json.loads(sys.argv[1])
sys.exit(0 if (m["resolved"] and m["regression_green"] and m["touched"] == 0
               and (m["mutation"] or 0) >= 0.7) else 1)
PY

python3 - "$F" <<'PY' && ok "a broken run is caught on every axis it is broken on" || bad "the scorer passed a broken run — this is the failure that produces a beautiful, wrong benchmark"
import json, sys
m = json.loads(sys.argv[1])
problems = []
if m["resolved"]:
    problems.append("hidden suite passed a wrong implementation")
if m["regression_green"]:
    problems.append("restored fixture suite missed the dropped guard")
if not m["touched"]:
    problems.append("edited pre-existing test not detected")
if m["mutation"] is not None and m["mutation"] > 0.15:
    problems.append("smoke tests scored as real tests")
for p in problems:
    print("   " + p)
sys.exit(1 if problems else 0)
PY

# ── 4. analyze.py survives a real results tree ─────────────────────────────────
"$BENCH/analyze.py" "$RESULTS" --report "$TMP/REPORT.md" \
  --treatment PASSING --control FAILING > /dev/null
grep -q "Per-arm" "$TMP/REPORT.md" \
  && ok "analyze.py produced a report" \
  || bad "analyze.py produced no report"

echo
if [[ $FAILED -eq 0 ]]; then
  echo "${GREEN}bench selftest: the scorer discriminates in both directions${OFF}"
else
  echo "${RED}bench selftest: FAILED${OFF}"
fi
exit $FAILED
