#!/usr/bin/env bash
# The template's own check: the tests of the setup script. scripts/setup-project.sh replaces this
# file with the check of the chosen stack (lint, types, tests).
set -euo pipefail

echo "+ python3 -m pytest .flow/loop/tests -q"
python3 -m pytest .flow/loop/tests -q -p no:cacheprovider
