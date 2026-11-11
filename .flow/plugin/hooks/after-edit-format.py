#!/usr/bin/env python3
"""After Claude edits or writes a Python file of the project: fix it with ruff, then format it.

Runs as a PostToolUse hook on Edit and Write. Only `.py` files inside the project are touched,
one file per call, with the ruff settings of pyproject.toml (migrations stay excluded).
It never undoes an edit: when ruff fails (a syntax error, ruff missing) the file is left as
Claude wrote it and exit code 2 sends one line back to Claude.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str], Path], tuple[int, str]]

TIMEOUT_SECONDS = 30
# An import added in one edit is often used only in the next one: never remove it here.
KEEP = ["--extend-unfixable", "F401"]
MAX_REASON = 200


def real_run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
    except FileNotFoundError:
        return 127, f"{args[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, f"ruff timed out after {TIMEOUT_SECONDS} seconds"
    return done.returncode, done.stdout + done.stderr


def ruff_command(project: Path) -> list[str]:
    """The project's own ruff, so the hook does not depend on the Python that runs it."""
    local = project / ".venv" / "bin" / "ruff"
    return [str(local)] if local.exists() else ["uv", "run", "--quiet", "ruff"]


def target_file(payload: object, project: Path) -> Path | None:
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.endswith(".py"):
        return None
    path = Path(file_path).resolve()
    if not path.is_relative_to(project.resolve()):
        return None
    return path


def first_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return (lines[0] if lines else "no output")[:MAX_REASON]


def evaluate(payload: object, project: Path, run: Runner, ruff: list[str]) -> str | None:
    path = target_file(payload, project)
    if path is None:
        return None
    steps = [
        [*ruff, "check", "--fix", *KEEP, "--exit-zero", "--force-exclude", str(path)],
        [*ruff, "format", "--force-exclude", str(path)],
    ]
    for args in steps:
        code, output = run(args, project)
        if code != 0:
            name = path.relative_to(project.resolve())
            return f"after-edit-format: {name} was not formatted: {first_line(output)}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    message = evaluate(payload, project, real_run, ruff_command(project))
    if message is None:
        return 0
    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
