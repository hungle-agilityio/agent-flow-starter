#!/usr/bin/env bash
# Start the loop at login: a user LaunchAgent that runs start-loop.sh (beside it) once. No sudo.
# Spec: docs/specs/notify-fix/spec.md (AC7). Run by hand on the Mac mini: .flow/loop/README.md, "Start at login".
set -euo pipefail

# The loop folder is this script's own (.flow/loop/, or .flow/loop/ in a new project); the project is the
# folder that holds it (spec: docs/specs/project-layout/spec.md, AC12).
LOOP="$(cd "$(dirname "$0")" && pwd)"
if [ "$(basename "$LOOP")" = "loop" ] && [ "$(basename "$(dirname "$LOOP")")" = ".flow" ]; then
  LAB="$(cd "$LOOP/../.." && pwd)"
else
  LAB="$(cd "$LOOP/.." && pwd)"
fi
REL="${LOOP#"$LAB"/}"
# shellcheck source=flow-value.sh
source "$LOOP/flow-value.sh"
LABEL="$(flow_value loop.launchd_label)"
STATE="$(flow_value loop.state_dir)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ "${1:-}" = "--remove" ]; then
  launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
  if [ -f "$PLIST" ]; then
    mkdir -p "$STATE/archive"
    mv "$PLIST" "$STATE/archive/$LABEL-$(date +%Y%m%d-%H%M%S).plist"
    echo "Removed. The plist is in $STATE/archive/."
  else
    echo "Nothing to remove: $PLIST does not exist."
  fi
  exit 0
fi

mkdir -p "$STATE" "$(dirname "$PLIST")"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$LOOP/start-loop.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$LAB</string>
  <key>RunAtLoad</key>
  <true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$STATE/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$STATE/launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed $PLIST. The loop starts at each login; remove it with: $REL/install-launchd.sh --remove"
