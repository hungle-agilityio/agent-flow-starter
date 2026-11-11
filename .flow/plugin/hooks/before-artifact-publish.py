#!/usr/bin/env python3
"""Before the Artifact tool publishes: a verify report may only go out when the sharing gate allows.

The call arrives as JSON on stdin. Exit code 2 blocks it and sends stderr back to Claude.
Any Artifact call that names a file inside out/verify/<report> is checked with the share-report
skill's share_gate.py (in this plugin, else in the project's .claude/skills/): the masking check
of the report must be clean and the standing approval must be on. Other artifacts are not
touched by this hook. If the gate cannot be run for a report, the call is blocked.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

GATE_REL = Path("skills") / "share-report" / "share_gate.py"
REPORT_FOLDER = re.compile(r"^(.*/out/verify/[^/]+)(?:/|$)")


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


def report_folders(tool_input: dict[str, Any], cwd: Path) -> list[Path]:
    folders: list[Path] = []
    for text in strings(tool_input):
        path = Path(text)
        absolute = path if path.is_absolute() else cwd / path
        match = REPORT_FOLDER.match(absolute.as_posix())
        if match and Path(match.group(1)) not in folders:
            folders.append(Path(match.group(1)))
    return folders


def gate_path(env: Mapping[str, str], cwd: Path) -> Path:
    """The sharing gate of this plugin's share-report skill, else the one of the project."""
    own = Path(__file__).resolve().parents[1] / GATE_REL
    if own.is_file():
        return own
    return Path(env.get("CLAUDE_PROJECT_DIR") or cwd) / ".claude" / GATE_REL


def gate(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("share_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(cwd: Path, decision: str, tool_input: dict[str, Any]) -> None:
    """One line per Artifact call in out/artifact-publish.log (git-ignored): what was asked."""
    try:
        log = cwd / "out" / "artifact-publish.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        text = " ".join(
            f"{k}={v}" for k, v in tool_input.items() if k in ("action", "file_path", "url")
        )
        with log.open("a") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {decision} {text}\n")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Artifact":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or tool_input.get("action") not in (None, "publish"):
        return 0
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    decision = "allowed"
    try:
        folders = report_folders(tool_input, cwd)
        if not folders:
            return 0
        module = gate(gate_path(os.environ, cwd))
        rules_override = os.environ.get("SHARE_RULES_FILE")
        problems: list[str] = []
        for folder in folders:
            allowed, reason = (
                module.decide(folder, Path(rules_override))
                if rules_override
                else module.decide(folder)
            )
            if not allowed:
                problems.append(f"{folder.name}: {reason}")
    except Exception as error:  # fail closed for a report
        problems = [f"the sharing gate could not be checked ({error})"]
    decision = "blocked" if problems else "allowed"
    audit(cwd, decision, tool_input)
    if not problems:
        return 0
    print(
        "Blocked by before-artifact-publish: "
        + "; ".join(problems)
        + ". The report stays on this machine; tell the user why.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
