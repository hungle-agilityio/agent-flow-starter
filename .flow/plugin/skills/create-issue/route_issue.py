#!/usr/bin/env python3
"""Print the area and loop labels of an issue, read from its Files likely touched section.

Usage: route_issue.py <issue body file> [--settings <settings.json>]. Prints two labels:
area:flow or area:app, then agent:ready. Every issue is agent:ready (ADR-023): the tick passes the
listed files to the build and before-edit-check lets it edit exactly those, guarded ones
included. A path outside the git repository is not routed. `--settings` is kept for old callers
and ignored. The config is .flow/flow.toml when it exists, else ops/flow.toml (or the file named
by FLOW_CONFIG). The folder prefix stripped from each path is its `project.app_dir`; `.` means no
prefix. The flow folders are its `paths.flow_dirs` and `paths.plugin_dir`. A path under a
.claude folder gets a warning on stderr: Claude Code's safetyCheck stops `claude -p` from
editing it, so that issue is built by hand with no agent:* label (ADR-023, "Exception: .claude/").
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import sys
from importlib import util
from pathlib import Path
from types import ModuleType

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
SETTINGS = PROJECT / ".claude" / "settings.json"
NEW_LAYOUT = (PROJECT / ".flow" / "flow.toml").is_file()
FLOW_MODULE = PROJECT / (".flow/loop" if NEW_LAYOUT else "ops") / "flow_config.py"
# Today's folders; a config with a [paths] table replaces them with paths.flow_dirs.
FLOW_FOLDERS = ("ops/", ".claude/", ".github/", "specs/", "docs/learning/")
PLUGIN_FOLDERS = ("../plugins/", "plugins/")
SECTION = re.compile(r"^##\s+Files likely touched\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
BULLET_PATH = re.compile(r"^\s*[-*]\s+`([^`]+)`(.*)$", re.M)


def load_module(name: str, path: Path) -> ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module  # a dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module


FLOW = load_module("flow_config", FLOW_MODULE)


def prefix_for(app_dir: str) -> str:
    """The app folder as a path prefix; `.` (the app is the repository root) means none."""
    folder = app_dir.strip().strip("/")
    return "" if folder in ("", ".") else f"{folder}/"


CONFIG = FLOW.load(FLOW.find_config(PROJECT)) if hasattr(FLOW, "find_config") else FLOW.load()
LAB_PREFIX = prefix_for(CONFIG.project_app_dir)


def folder_prefix(folder: str) -> str:
    return folder.strip().removeprefix("./").rstrip("/") + "/"


def flow_prefixes() -> tuple[str, ...]:
    """paths.flow_dirs and the plugin folder (paths.plugin_dir) of the config, plus plugins/."""
    flow = tuple(getattr(CONFIG, "paths_flow_dirs", FLOW_FOLDERS))
    plugin = getattr(CONFIG, "paths_plugin_dir", "")
    extra = (folder_prefix(plugin),) if plugin else ()
    return tuple(dict.fromkeys((*flow, *extra, *PLUGIN_FOLDERS)))


def paths_of(text: str, prefix: str | None = None) -> list[str]:
    """Paths are relative to the app folder; the repository root is written as ../."""
    strip = LAB_PREFIX if prefix is None else prefix
    match = SECTION.search(text)
    if match is None:
        raise ValueError("the issue has no '## Files likely touched' section")
    paths: list[str] = []
    for raw, note in BULLET_PATH.findall(match.group(1)):
        path = raw.strip().removeprefix("./")
        if strip:
            path = path.removeprefix(strip)
        if "repository root" in note.lower() and not path.startswith("../"):
            path = f"../{path}"
        paths.append(path)
    if not paths:
        raise ValueError("the '## Files likely touched' section names no `path`")
    return paths


def outside_repository(path: str) -> bool:
    """The path climbs out of the git repository (more ../ than the app folder is deep)."""
    joined = posixpath.normpath(posixpath.join(LAB_PREFIX or ".", path))
    return joined == ".." or joined.startswith("../") or posixpath.isabs(path)


CLAUDE_WARNING = (
    "WARNING: {path} is under .claude/; claude -p cannot edit it (safetyCheck, ADR-023). "
    "Build this issue by hand and give it no agent:* label."
)


def claude_folder_paths(paths: list[str]) -> list[str]:
    """The listed paths inside a .claude folder, which the loop cannot edit."""
    return [p for p in paths if ".claude" in (part.casefold() for part in p.split("/"))]


def route(text: str, allow: list[str] | None = None) -> list[str]:
    """area:flow when any path is in a flow folder or the plugin; every issue is agent:ready."""
    paths = paths_of(text)
    for path in paths:
        if outside_repository(path):
            raise ValueError(f"{path} is outside the repository")
    flow = any(p.startswith(flow_prefixes()) for p in paths)
    return ["area:flow" if flow else "area:app", "agent:ready"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("issue", type=Path)
    parser.add_argument("--settings", type=Path, default=SETTINGS, help="ignored (ADR-023)")
    args = parser.parse_args(argv)
    text = args.issue.read_text()
    try:
        print(" ".join(route(text)))
        for path in claude_folder_paths(paths_of(text)):
            print(CLAUDE_WARNING.format(path=path), file=sys.stderr)
    except ValueError as error:
        print(f"NOT ROUTED: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
