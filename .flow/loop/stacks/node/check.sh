#!/usr/bin/env bash
# The one command that checks everything; the loop and CI run it. Stops at the first failure.
set -euo pipefail

run() {
  echo "+ $*"
  "$@"
}

run npm run lint
run npm run typecheck
run npm test
