#!/usr/bin/env python3
"""Before Edit and Write, in loop mode only: protect the rules, the gates and the tests on main.

The call arrives as JSON on stdin. Exit code 2 blocks it and sends stderr back to Claude.
Loop mode is on when FLOW_LOOP=1 (the unattended `work-queue` session);
in an interactive session this hook does nothing. In loop mode it fails closed.

The rule (which names are guarded) lives in guarded_paths.py beside this hook; this hook and
ops/epic_pull_request.py read it. When guarded_paths.py cannot be loaded, or cannot answer, the
edit is refused in loop mode, except for a file the issue lists (FLOW_ALLOWED_EDITS, below).

Refused in loop mode (names are compared without regard to letter case, the Mac file system
ignores it):
  - anything in a .github or .claude folder, on any path, and .mcp.json or flow.toml (any
    folder): the loop must not change its own rules, only a person does. The same for the flow
    plugin's source: plugins/ and .claude-plugin/ at the root of the git repository. In
    .claude/knowledge/ a new file is allowed, a file that already exists on main is not;
  - pyproject.toml, uv.lock, conftest.py and the other tool config files (ruff.toml, mypy.ini,
    pytest.ini, .coveragerc, ...): they set the lint, type, test and coverage gates;
  - a test file that already exists on main under a folder of `checks.protected_test_dirs` in
    ops/flow.toml, unless ALLOW_TEST_EDIT=1: fix the code, not the test. A file that the
    issue lists under `## Existing tests that change` is allowed: the tick passes those paths,
    relative to the project folder, one per line in FLOW_TEST_EDITS.

A file the issue lists (`## Files likely touched`, `## Existing tests that change`) is allowed
even when it is guarded: the tick passes those paths, relative to the project folder (`../` for
the git root), one per line in FLOW_ALLOWED_EDITS, and the hook answers allow (ADR-023).
Always refused in loop mode, even when listed: a path inside .git, and an edit of settings.json
or settings.local.json in a .claude folder that changes a key that turns guards off
(GUARD_KEYS); when the result cannot be worked out the edit is refused.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from importlib import util
from pathlib import Path
from types import ModuleType
from typing import Any

Runner = Callable[[list[str], Path], tuple[int, str]]

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

LOOP_VARS = ("FLOW_LOOP",)
SETTINGS_FILES = {"settings.json", "settings.local.json"}
GUARD_KEYS = ("disableAllHooks", "enabledPlugins", "extraKnownMarketplaces", "hooks")
DENY_KEY = "permissions.deny"
MISSING = object()


def is_loop(env: Mapping[str, str]) -> bool:
    """Loop mode is on when FLOW_LOOP=1."""
    return any(env.get(name) == "1" for name in LOOP_VARS)


def app_dir(env: Mapping[str, str], cwd: Path | str | None = None) -> Path:
    """The project: CLAUDE_PROJECT_DIR, else the cwd of the call; never this hook's own folder."""
    session = env.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(session or cwd or os.getcwd())


def config_path(app: Path, named: str | None) -> Path:
    """FLOW_CONFIG, else <project>/.flow/flow.toml when it exists, else <project>/ops/flow.toml."""
    if named:
        return Path(named)
    new = app / ".flow" / "flow.toml"
    return new if new.is_file() else app / "ops" / "flow.toml"


def new_layout_loader(config: Path) -> list[Path]:
    """`<paths.loop_dir>/flow_config.py` of a .flow/flow.toml (default .flow/loop); else none."""
    if config.parent.name != ".flow":
        return []
    folder = ".flow/loop"
    try:
        import tomllib

        named = tomllib.loads(config.read_text()).get("paths", {}).get("loop_dir")
        folder = named if isinstance(named, str) and named else folder
    except Exception:  # the loader reports a broken file with its own message
        pass
    return [config.parent.parent / folder / "flow_config.py"]


def loader_path(app: Path, named: str | None) -> Path:
    """The reader of the config's project (.flow/loop/ or ops/), else beside FLOW_CONFIG."""
    candidates = [
        *new_layout_loader(config_path(app, named)),
        app / "ops" / "flow_config.py",
        *new_layout_loader(config_path(app, None)),
    ]
    if named:
        candidates.append(Path(named).parent / "flow_config.py")
    session = os.environ.get("CLAUDE_PROJECT_DIR")
    if session:
        candidates.extend(new_layout_loader(config_path(Path(session), None)))
        candidates.append(Path(session) / "ops" / "flow_config.py")
    return next((path for path in candidates if path.is_file()), candidates[0])


def flow_config(env: Mapping[str, str], cwd: Path | str | None = None) -> Any:
    """The flow config of the project (.flow/flow.toml or ops/flow.toml), or FLOW_CONFIG's."""
    app = app_dir(env, cwd)
    named = env.get("FLOW_CONFIG")
    module_path = loader_path(app, named)
    spec = util.spec_from_file_location("flow_config", module_path)
    if spec is None or spec.loader is None:
        raise OSError(f"cannot load {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module.load(config_path(app, named))


def protected_test_parts(
    env: Mapping[str, str], project: Path | None = None
) -> list[tuple[str, ...]]:
    """Each folder of `checks.protected_test_dirs`, split into lowercase parts."""
    dirs = flow_config(env, project).checks_protected_test_dirs
    found = [tuple(p.casefold() for p in d.split("/") if p not in ("", ".")) for d in dirs]
    return [parts for parts in found if parts]


def under_any(parts: tuple[str, ...], folders: list[tuple[str, ...]]) -> bool:
    return any(
        parts[i : i + len(folder)] == folder for folder in folders for i in range(len(parts))
    )


def real_run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""
    return done.returncode, done.stdout


def load_rule() -> tuple[ModuleType | None, str]:
    """guarded_paths.py beside this hook, loaded by file path (the hook runs with python3 -I)."""
    try:
        module_path = Path(__file__).resolve().parent / "guarded_paths.py"
        spec = util.spec_from_file_location("guarded_paths", module_path)
        if spec is None or spec.loader is None:
            raise OSError(f"cannot load {module_path}")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not callable(getattr(module, "guarded_kind", None)) or not isinstance(
            getattr(module, "PLUGIN_DIRS", None), (set, frozenset)
        ):
            raise OSError(f"{module_path} does not hold the rule")
        return module, ""
    except Exception as error:  # fail closed: evaluate refuses the edit
        return None, str(error)


RULE, RULE_ERROR = load_rule()


def git_root(path: Path, run: Runner) -> Path | None:
    """The root of the git repository the path is in, or None when there is none."""
    folder = path.parent
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    code, top = run(["git", "rev-parse", "--show-toplevel"], folder)
    return Path(top.strip()).resolve() if code == 0 and top.strip() else None


def in_plugin_source(path: Path, run: Runner) -> bool:
    """plugins/ and .claude-plugin/ at the git root hold the flow plugin and its marketplace."""
    if RULE is None:
        return False
    root = git_root(path, run)
    if root is None:
        return False
    try:
        first = path.relative_to(root).parts[:1]
    except ValueError:
        return False
    return bool(first) and first[0].casefold() in RULE.PLUGIN_DIRS


def on_main(path: Path, project: Path, run: Runner) -> bool | None:
    """True when the file is on main, False when it is not, None when that cannot be told.

    The repository is the one the file itself is in, not the one of the session.
    """
    folder = path.parent
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    code, top = run(["git", "rev-parse", "--show-toplevel"], folder)
    if code != 0 or not top.strip():
        return None
    root = Path(top.strip()).resolve()
    try:
        rel = path.relative_to(root).as_posix().casefold()
    except ValueError:
        return None
    for ref in ("origin/main", "main"):
        code, names = run(["git", "ls-tree", "-r", "--name-only", ref], root)
        if code == 0:
            return rel in {line.casefold() for line in names.splitlines()}
    return None


def listed_test_edit(path: Path, project: Path, env: Mapping[str, str]) -> bool:
    """The issue names this test file under `## Existing tests that change` (FLOW_TEST_EDITS)."""
    listed = {
        line.strip().removeprefix("./").casefold()
        for line in env.get("FLOW_TEST_EDITS", "").splitlines()
        if line.strip()
    }
    if not listed:
        return False
    try:
        rel = path.relative_to(project).as_posix().casefold()
    except ValueError:
        return False
    return rel in listed


def listed_edit(path: Path, project: Path, env: Mapping[str, str]) -> bool:
    """The issue lists this file (FLOW_ALLOWED_EDITS), relative to the project folder."""
    target = str(path.resolve()).casefold()
    for line in env.get("FLOW_ALLOWED_EDITS", "").splitlines():
        rel = line.strip().removeprefix("./")
        if rel and str((project / rel).resolve()).casefold() == target:
            return True
    return False


def apply_edit(text: str, old: object, new: object, every: bool) -> str | None:
    """The text after one Edit, or None when the old text is not there."""
    if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
        return None
    return text.replace(old, new) if every else text.replace(old, new, 1)


def settings_after(path: Path, tool_name: str, tool_input: Mapping[str, Any]) -> str | None:
    """The settings file as the edit would leave it, or None when that cannot be worked out."""
    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None
    try:
        text: str | None = path.read_text() if path.exists() else ""
    except OSError:
        return None
    if tool_name == "Edit":
        edits: object = [tool_input]
    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits")
    else:
        return None
    if not isinstance(edits, list) or not edits:
        return None
    for edit in edits:
        if text is None or not isinstance(edit, Mapping):
            return None
        text = apply_edit(
            text, edit.get("old_string"), edit.get("new_string"), edit.get("replace_all") is True
        )
    return text


def guard_values(data: Mapping[str, Any]) -> dict[str, object]:
    values = {key: data.get(key, MISSING) for key in GUARD_KEYS}
    permissions = data.get("permissions", MISSING)
    values[DENY_KEY] = (
        permissions.get("deny", MISSING) if isinstance(permissions, Mapping) else permissions
    )
    return values


def changed_guard_keys(
    path: Path, tool_name: str, tool_input: Mapping[str, Any]
) -> list[str] | None:
    """The guard keys the edit changes, or None when the result cannot be worked out."""
    after = settings_after(path, tool_name, tool_input)
    try:
        before = json.loads(path.read_text()) if path.exists() else {}
        result = json.loads(after) if after is not None else None
    except (OSError, ValueError):
        return None
    if not isinstance(before, dict) or not isinstance(result, dict):
        return None
    old, new = guard_values(before), guard_values(result)
    return [key for key in (*GUARD_KEYS, DENY_KEY) if old[key] != new[key]]


def listed_problems(
    path: Path, parts: tuple[str, ...], tool_name: str, tool_input: Mapping[str, Any]
) -> list[str]:
    """A listed file is allowed, except the settings keys that turn guards off."""
    if parts[-1] in SETTINGS_FILES and ".claude" in parts[:-1]:
        keys = changed_guard_keys(path, tool_name, tool_input)
        if keys is None:
            keys = [*GUARD_KEYS, DENY_KEY]
        if keys:
            return [
                f"{path.name}: the loop never changes the keys that turn guards off "
                f"({', '.join(keys)}); ask the user"
            ]
    return []


def evaluate(
    file_path: str,
    project: Path,
    env: Mapping[str, str],
    run: Runner,
    tool_name: str = "",
    tool_input: Mapping[str, Any] | None = None,
) -> list[str]:
    if not is_loop(env):
        return []
    path = Path(file_path).resolve()
    parts = tuple(part.casefold() for part in path.parts)
    project = project.resolve()

    if ".git" in parts:
        return [f"{path.name} is inside .git; the loop never edits git's own files, ask the user"]
    if listed_edit(path, project, env):
        return listed_problems(path, parts, tool_name, tool_input or {})

    if RULE is None:
        return [f"{path.name} not checked: guarded_paths.py could not be loaded ({RULE_ERROR})"]
    try:
        kind = RULE.guarded_kind(parts)
    except Exception as error:  # fail closed
        return [f"{path.name} not checked: guarded_paths.py could not answer ({error})"]
    if kind == "rule":
        if ".github" not in parts and ".claude" in parts:
            after = parts[parts.index(".claude") + 1 :]
            if after[:1] == ("knowledge",) and len(after) > 1:
                known = on_main(path, project, run)
                if known is False:
                    return []
                reason = "is already on main" if known else "could not be compared with main"
                return [f"{path.name} {reason}; only a person changes existing knowledge files"]
        return [f"{path.name} is a rule file; the loop never changes its own rules, ask the user"]
    if in_plugin_source(path, run):
        return [
            f"{path.name} is part of the flow plugin; the loop never changes its own rules, "
            "ask the user"
        ]
    if kind == "gate":
        return [f"{path.name} sets the lint, type, test or dependency gates; ask the user"]
    if env.get("ALLOW_TEST_EDIT") == "1":
        return []
    try:
        folders = protected_test_parts(env, project)
    except Exception as error:  # fail closed
        return [f"{path.name} not checked: ops/flow.toml could not be read ({error})"]
    if under_any(parts, folders):
        known = on_main(path, project, run)
        if known is None:
            return [f"{path.name} could not be compared with main, so it is not edited"]
        if known and not listed_test_edit(path, project, env):
            return [f"{path.name} is a test that is already on main; fix the code, not the test"]
    return []


ALLOW_ANSWER = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "the issue lists this file (FLOW_ALLOWED_EDITS)",
    }
}


def main() -> int:
    loop = is_loop(os.environ)
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        if loop:
            print("Blocked by before-edit-check: the call could not be read.", file=sys.stderr)
            return 2
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in EDIT_TOOLS:
        return 0
    tool_input = payload.get("tool_input")
    file_path = ""
    if isinstance(tool_input, dict):
        file_path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    if not file_path:
        if loop:
            print("Blocked by before-edit-check: no file path to check.", file=sys.stderr)
            return 2
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    tool_name = str(payload.get("tool_name"))
    edit_input = tool_input if isinstance(tool_input, dict) else {}
    problems = evaluate(file_path, project, os.environ, real_run, tool_name, edit_input)
    if not problems:
        if loop and listed_edit(Path(file_path), project.resolve(), os.environ):
            print(json.dumps(ALLOW_ANSWER))
        return 0
    print("Blocked by before-edit-check: " + "; ".join(problems) + ".", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
