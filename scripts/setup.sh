#!/usr/bin/env bash
# The template's own setup: pytest for the setup tests. scripts/setup-project.sh replaces this
# file with the setup of the chosen stack.
set -euo pipefail

python3 -m pip install --quiet pytest
