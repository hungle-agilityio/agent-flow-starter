#!/usr/bin/env bash
# Sourced by start-loop.sh and install-launchd.sh: `flow_value loop.tmux_session` prints one value
# of the flow config: the file named by FLOW_CONFIG, else flow.toml beside this script (.flow/loop/), else
# the one a folder up (.flow/ for .flow/loop/). Spec: docs/specs/flow-bootstrap/spec.md (AC5),
# docs/specs/project-layout/spec.md (AC12). It asks `python3 flow_config.py` beside it (the checked
# reader, Python 3.11+). The macOS system python3 is older and has no tomllib, so for a plain
# `key = "value"` line it reads the file itself.

flow_value() {
  local dir file key value err
  dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  file="$dir/flow.toml"
  if [ ! -f "$file" ] && [ -f "$dir/../flow.toml" ]; then
    file="$(cd "$dir/.." && pwd)/flow.toml"
  fi
  file="${FLOW_CONFIG:-$file}"
  key="${1#*.}"
  if python3 -c 'import tomllib' 2>/dev/null; then
    python3 "$dir/flow_config.py" "$1"
    return $?
  fi
  value="$(sed -n "s/^$key[[:space:]]*=[[:space:]]*\"\\(.*\\)\"[[:space:]]*\$/\\1/p" "$file" 2>/dev/null | head -n 1)"
  if [ -z "$value" ]; then
    err="$(python3 "$dir/flow_config.py" "$1" 2>&1 || true)"
    echo "flow.toml: cannot read $1 (${err:-no value in $file})" >&2
    return 2
  fi
  printf '%s\n' "${value/#\~/$HOME}"
}
