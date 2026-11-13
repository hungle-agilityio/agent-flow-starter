#!/usr/bin/env python3
"""Print the review level of a branch: "high" when it touches a sensitive path, else "standard".

Usage: review_level.py --base <ref>, run from the app folder. The sensitive paths are the glob
patterns of `paths.review_sensitive` in the flow config (.flow/flow.toml when it exists, else
ops/flow.toml, or the file named by FLOW_CONFIG), relative to the app folder; `../` reaches the
repository root. The files are those the branch changed since its merge base with <ref>,
committed or not, plus new files not yet added. "high" is followed by one line per matching
file: two spaces, the path from the repository root, two spaces, the first matching pattern in
parentheses. Exit code 0; a git or config failure prints `review_level: <reason>` to stderr and
exits 2. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from fnmatch import fnmatchcase
from importlib import util
from pathlib import Path
from types import ModuleType

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
NEW_LAYOUT = (PROJECT / ".flow" / "flow.toml").is_file()
FLOW_MODULE = PROJECT / (".flow/loop" if NEW_LAYOUT else "ops") / "flow_config.py"


class ReviewLevelError(Exception):
    """Git failed or the config cannot be loaded; the message is the one-line reason."""


def load_module(name: str, path: Path) -> ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module  # a dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module


def one_line(text: object) -> str:
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    return lines[0] if lines else "unknown error"


def load_settings() -> tuple[str, tuple[str, ...]]:
    """The app folder and the sensitive patterns of the flow config; no key means no pattern."""
    try:
        flow = load_module("flow_config", FLOW_MODULE)
        config = (
            flow.load(flow.find_config(PROJECT)) if hasattr(flow, "find_config") else flow.load()
        )
    except Exception as error:  # the config's own error class lives in the loaded module
        raise ReviewLevelError(one_line(error) or type(error).__name__) from error
    patterns = tuple(str(pattern) for pattern in getattr(config, "paths_review_sensitive", ()))
    return str(config.project_app_dir), patterns


def git(args: list[str], cwd: Path | None = None) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as error:
        raise ReviewLevelError(f"git {args[0]}: {one_line(error)}") from error
    if done.returncode != 0:
        raise ReviewLevelError(f"git {args[0]}: {one_line(done.stderr)}")
    return done.stdout


def changed_files(base: str) -> list[str]:
    """Every file the branch changed since its merge base, committed or not, from the root."""
    root = Path(git(["rev-parse", "--show-toplevel"]).strip())
    start = git(["merge-base", base, "HEAD"], root).strip()
    tracked = git(["diff", "--name-only", start], root)
    new = git(["ls-files", "--others", "--exclude-standard", "--full-name"], root)
    return sorted({line for line in (tracked + new).splitlines() if line})


def rooted(pattern: str, app_dir: str) -> str:
    """The pattern from the repository root: the app folder in front, `<app>/../` removed."""
    folder = app_dir.strip().strip("/")
    if folder in ("", "."):
        return pattern
    return f"{folder}/{pattern}".removeprefix(f"{folder}/../")


def matches(files: list[str], patterns: tuple[str, ...], app_dir: str) -> list[tuple[str, str]]:
    """Each matching file with its first matching pattern, as written in the config."""
    found: list[tuple[str, str]] = []
    for name in files:
        for pattern in patterns:
            if fnmatchcase(name, rooted(pattern, app_dir)):
                found.append((name, pattern))
                break
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--base", required=True, help="the ref the branch started from")
    args = parser.parse_args(argv)
    try:
        app_dir, patterns = load_settings()
        found = matches(changed_files(args.base), patterns, app_dir)
    except ReviewLevelError as error:
        print(f"review_level: {error}", file=sys.stderr)
        return 2
    if not found:
        print("standard")
        return 0
    print("high")
    for name, pattern in found:
        print(f"  {name}  ({pattern})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
