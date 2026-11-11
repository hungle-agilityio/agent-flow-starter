#!/usr/bin/env bash
# Run once on the Mac mini, at the root of a new repository made from this template:
# bash scripts/setup-project.sh --repo <owner/name> --owner <login> --name <display name> \
#   --slug <slug> --ntfy-topic <topic> --stack python|node|other [--dry-run] [--no-labels]
set -euo pipefail

cd "$(dirname "$0")/.."
exec python3 .flow/loop/setup_project.py "$@"
