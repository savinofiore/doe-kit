#!/usr/bin/env bash
# Applies the hidden acceptance suite to a finished run. Exit 0 = the task is resolved.
#
#   verify.sh WORKDIR
#
# The suite is copied in at scoring time and removed again, so nothing the agent saw during
# the run can contain it.
set -euo pipefail

WORKDIR="${1:?usage: verify.sh WORKDIR}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HIDDEN="$WORKDIR/_bench_hidden"

cleanup() { rm -rf "$HIDDEN"; }
trap cleanup EXIT

rm -rf "$HIDDEN"
cp -r "$TASK_DIR/hidden" "$HIDDEN"
cd "$WORKDIR"
python3 -m unittest discover -s _bench_hidden -t . -v
