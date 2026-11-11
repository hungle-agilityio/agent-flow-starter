"""Read the project values of the flow from its `flow.toml`; a missing value stops with its name.

Spec: specs/flow-bootstrap/spec.md (AC2 to AC4), specs/project-layout/spec.md (AC1 to AC3).
The file is `.flow/flow.toml` in a project with the new layout, else `ops/flow.toml`. Shell
scripts call `python3 <loop folder>/flow_config.py <section.key>`. Standard library only; the
only defaults are those of the optional `[paths]` table, which are this repository's layout.
"""

from __future__ import annotations

import os
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENV_VAR = "FLOW_CONFIG"
NEW_CONFIG = Path(".flow") / "flow.toml"
OLD_CONFIG = Path("ops") / "flow.toml"
STRING = "string"
WORDS = "list of strings"
COMMANDS = "list of lists of strings"


def project_of(module_dir: Path) -> Path:
    """The project of a loop folder: `<project>/.flow/loop` or `<project>/ops`."""
    if module_dir.name == "loop" and module_dir.parent.name == ".flow":
        return module_dir.parent.parent
    return module_dir.parent


def find_config(project: Path, env: Mapping[str, str] | None = None) -> Path:
    """FLOW_CONFIG when set, else `<project>/.flow/flow.toml` when it exists, else ops/flow.toml."""
    named = (os.environ if env is None else env).get(ENV_VAR)
    if named:
        return Path(named)
    new = project / NEW_CONFIG
    return new if new.is_file() else project / OLD_CONFIG


PROJECT_DIR = project_of(Path(__file__).resolve().parent)
DEFAULT_PATH = find_config(PROJECT_DIR, {})

# section -> key -> expected kind; the order is the order of the file.
SCHEMA: dict[str, dict[str, str]] = {
    "project": {
        "repo": STRING,
        "owner": STRING,
        "app_dir": STRING,
        "display_name": STRING,
        "slug": STRING,
    },
    "loop": {
        "state_dir": STRING,
        "tmux_session": STRING,
        "launchd_label": STRING,
        "setup_command": WORDS,
        "alone_words": WORDS,
    },
    "checks": {
        "commands": COMMANDS,
        "ci_workflow": STRING,
        "protected_test_dirs": WORDS,
    },
    "release": {"timezone": STRING, "deploy_line": STRING},
    "plugin": {"id": STRING, "marketplace": STRING},
    "paths": {
        "loop_dir": STRING,
        "plugin_dir": STRING,
        "intent_file": STRING,
        "specs_dir": STRING,
        "spec_pr_dirs": WORDS,
        "plans_dir": STRING,
        "decisions_dir": STRING,
        "templates_dir": STRING,
        "code_dirs": WORDS,
        "flow_dirs": WORDS,
    },
}
# A file written before the plugin existed has no [plugin] table; the tick stops on the empty key.
OPTIONAL_SECTIONS = {"plugin", "paths"}
# A missing key of [paths] takes this repository's layout.
PATH_DEFAULTS: dict[str, str | list[str]] = {
    "loop_dir": ".flow/loop",
    "plugin_dir": ".flow/plugin",
    "intent_file": "docs/intent/{feature}.md",
    "specs_dir": "docs/specs",
    "spec_pr_dirs": ["docs/intent", "docs/specs"],
    "plans_dir": "docs/plans",
    "decisions_dir": "docs/decisions",
    "templates_dir": "docs/templates",
    "code_dirs": ["src"],
    "flow_dirs": [".flow/", ".claude/", ".github/", "docs/intent/", "docs/specs/", "scripts/"],
}


class FlowConfigError(Exception):
    """The config file is unreadable or wrong; the message names the file and the key."""


@dataclass(frozen=True)
class FlowConfig:
    project_repo: str
    project_owner: str
    project_app_dir: str
    project_display_name: str
    project_slug: str
    loop_state_dir: Path
    loop_tmux_session: str
    loop_launchd_label: str
    loop_setup_command: tuple[str, ...]
    loop_alone_words: tuple[str, ...]
    checks_commands: tuple[tuple[str, ...], ...]
    checks_ci_workflow: str
    checks_protected_test_dirs: tuple[str, ...]
    release_timezone: str
    release_deploy_line: str
    plugin_id: str = ""
    plugin_marketplace: str = ""
    paths_loop_dir: str = ".flow/loop"
    paths_plugin_dir: str = ".flow/plugin"
    paths_intent_file: str = "docs/intent/{feature}.md"
    paths_specs_dir: str = "docs/specs"
    paths_spec_pr_dirs: tuple[str, ...] = ("docs/intent", "docs/specs")
    paths_plans_dir: str = "docs/plans"
    paths_decisions_dir: str = "docs/decisions"
    paths_templates_dir: str = "docs/templates"
    paths_code_dirs: tuple[str, ...] = ("src",)
    paths_flow_dirs: tuple[str, ...] = (
        ".flow/", ".claude/", ".github/", "docs/intent/", "docs/specs/", "scripts/"
    )


def _is_words(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(word, str) for word in value)


def _has_kind(value: object, kind: str) -> bool:
    if kind == STRING:
        return isinstance(value, str)
    if kind == WORDS:
        return _is_words(value)
    return isinstance(value, list) and all(_is_words(item) for item in value)


def _label(path: Path) -> str:
    """The file as shown in a message: `ops/flow.toml` or `.flow/flow.toml` for the project's."""
    resolved = path.resolve()
    for known in (OLD_CONFIG, NEW_CONFIG):
        if resolved == (PROJECT_DIR / known).resolve():
            return known.as_posix()
    return str(path)


def _read(path: Path) -> dict[str, Any]:
    label = _label(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        reason = error.strerror or error
        if path.name == OLD_CONFIG.name and path.parent.name == OLD_CONFIG.parent.name:
            other = path.parent.parent / NEW_CONFIG
            if not other.is_file():
                reason = f"{reason}; {NEW_CONFIG.as_posix()} is missing too"
        raise FlowConfigError(f"{label}: cannot read ({reason})") from error
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise FlowConfigError(f"{label}: not valid TOML ({error})") from error


def _check(data: dict[str, Any], label: str) -> None:
    for section in data:
        if section not in SCHEMA:
            raise FlowConfigError(f"{label}: unknown {section}")
    for section, keys in SCHEMA.items():
        values = data.get(section)
        if values is None and section in OPTIONAL_SECTIONS:
            continue
        if not isinstance(values, dict):
            raise FlowConfigError(f"{label}: missing {section}.{next(iter(keys))}")
        for key in values:
            if key not in keys:
                raise FlowConfigError(f"{label}: unknown {section}.{key}")
        for key, kind in keys.items():
            if key not in values and section == "paths":
                continue
            if key not in values:
                raise FlowConfigError(f"{label}: missing {section}.{key}")
            if not _has_kind(values[key], kind):
                raise FlowConfigError(f"{label}: {section}.{key} must be a {kind}")


def load(path: Path | None = None) -> FlowConfig:
    """Read `path`, else the file named by FLOW_CONFIG, else this project's flow.toml."""
    if path is None:
        path = find_config(PROJECT_DIR)
    data = _read(path)
    _check(data, _label(path))
    project, loop, checks, release = (data[s] for s in list(SCHEMA)[:4])
    plugin = data.get("plugin", {})
    paths: dict[str, Any] = {**PATH_DEFAULTS, **data.get("paths", {})}
    return FlowConfig(
        project_repo=project["repo"],
        project_owner=project["owner"],
        project_app_dir=project["app_dir"],
        project_display_name=project["display_name"],
        project_slug=project["slug"],
        loop_state_dir=Path(loop["state_dir"]).expanduser(),
        loop_tmux_session=loop["tmux_session"],
        loop_launchd_label=loop["launchd_label"],
        loop_setup_command=tuple(loop["setup_command"]),
        loop_alone_words=tuple(loop["alone_words"]),
        checks_commands=tuple(tuple(command) for command in checks["commands"]),
        checks_ci_workflow=checks["ci_workflow"],
        checks_protected_test_dirs=tuple(checks["protected_test_dirs"]),
        release_timezone=release["timezone"],
        release_deploy_line=release["deploy_line"],
        plugin_id=plugin.get("id", ""),
        plugin_marketplace=plugin.get("marketplace", ""),
        paths_loop_dir=_text(paths["loop_dir"]),
        paths_plugin_dir=_text(paths["plugin_dir"]),
        paths_intent_file=_text(paths["intent_file"]),
        paths_specs_dir=_text(paths["specs_dir"]),
        paths_spec_pr_dirs=tuple(paths["spec_pr_dirs"]),
        paths_plans_dir=_text(paths["plans_dir"]),
        paths_decisions_dir=_text(paths["decisions_dir"]),
        paths_templates_dir=_text(paths["templates_dir"]),
        paths_code_dirs=tuple(paths["code_dirs"]),
        paths_flow_dirs=tuple(paths["flow_dirs"]),
    )


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _words(value: object) -> str:
    if isinstance(value, tuple):
        return " ".join(_words(item) for item in value)
    return str(value)


def lookup(config: FlowConfig, dotted: str, label: str) -> str:
    """The value of `section.key` on one line; a list is space-separated words."""
    section, _, key = dotted.partition(".")
    if key not in SCHEMA.get(section, {}):
        raise FlowConfigError(f"{label}: unknown {dotted}")
    return _words(getattr(config, f"{section}_{key}"))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python3 flow_config.py <section.key>", file=sys.stderr)
        return 2
    path = find_config(PROJECT_DIR)
    try:
        print(lookup(load(path), argv[0], _label(path)))
    except FlowConfigError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
