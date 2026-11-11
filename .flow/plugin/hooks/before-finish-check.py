#!/usr/bin/env python3
"""Before Claude stops, in loop mode only: do not finish while lint, types or tests fail.

Runs as a Stop hook. Exit code 2 sends stderr back to Claude and keeps it working.
Loop mode is on when FLOW_LOOP=1; in an interactive session this hook
does nothing. The checks are `checks.commands` of ops/flow.toml, run in order.
A pull request round (the tick wrote out/pr-round.json) that added commits must also have
republished its verify report to a link (an `allowed ... url=` line in out/artifact-publish.log),
built at the new HEAD, and with screenshots when the issue has needs-ui (`"ui": true`).
A second stop in a row is always allowed (stop_hook_active), so a stuck issue ends in the
report as failed instead of looping for ever.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from importlib import util
from pathlib import Path
from typing import Any

Runner = Callable[[list[str], Path], tuple[int, str]]

TAIL_LINES = 30

LOOP_VARS = ("FLOW_LOOP",)


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


def real_run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=300, check=False
        )
    except FileNotFoundError:
        return 127, f"{args[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(args)}: timed out"
    return done.returncode, done.stdout + done.stderr


def check_commands(env: Mapping[str, str], project: Path | None = None) -> list[list[str]]:
    return [list(command) for command in flow_config(env, project).checks_commands]


def failures(project: Path, run: Runner, commands: list[list[str]]) -> list[str]:
    found: list[str] = []
    for args in commands:
        code, output = run(args, project)
        if code != 0:
            tail = "\n".join(output.strip().splitlines()[-TAIL_LINES:])
            found.append(f"`{' '.join(args)}` failed:\n{tail}")
    return found


def report_problems(project: Path, run: Runner) -> list[str]:
    """A pull request round with new commits republished its report to the pull request's link."""
    try:
        data = json.loads((project / "out" / "pr-round.json").read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or not data.get("head"):
        return []
    code, out = run(["git", "rev-parse", "HEAD"], project)
    if code != 0 or out.strip() == str(data["head"]):
        return []
    try:
        lines = (project / "out" / "artifact-publish.log").read_text().splitlines()
    except OSError:
        lines = []
    published = [line for line in lines if " allowed " in line and " url=https://" in f" {line}"]
    if not published:
        return [
            f"PR #{data.get('pr')}: this round added commits but did not republish the verify "
            "report. Rebuild it (build-verify-report, same mode as the issue), then republish "
            "report-share.html with share-report to the link in the pull request body, "
            "the same URL."
        ]
    return stale_report(project, published[-1], out.strip(), data)


def stale_report(project: Path, line: str, head: str, data: dict[str, Any]) -> list[str]:
    """The republished report shows this round's code: built at HEAD, with fresh screenshots."""
    pr = data.get("pr")
    match = re.search(r"(?:^|\s)file_path=(\S+)", line)
    report: dict[str, Any] | None = None
    if match:
        page = Path(match.group(1))
        try:
            loaded = json.loads(((project / page).parent / "report.json").read_text())
            report = loaded if isinstance(loaded, dict) else None
        except (OSError, ValueError):
            report = None
    mode = " (--browser --spec with the issue's Screens to capture block)" if data.get("ui") else ""
    rebuild = (
        f"Rebuild it with build-verify-report at this commit{mode}, "
        "then republish its report-share.html to the same link."
    )
    if report is None:
        if data.get("ui"):
            return [f"PR #{pr}: the republished page has no report.json beside it. {rebuild}"]
        return []
    commit = str(report.get("commit") or "")
    if not commit or not head.startswith(commit):
        return [
            f"PR #{pr}: the republished report was built at {commit or 'an unknown commit'}, "
            f"not at HEAD {head[:7]}, so it shows old code and old screenshots. {rebuild}"
        ]
    if data.get("ui") and not report.get("screenshots"):
        return [
            f"PR #{pr}: the issue has needs-ui but the republished report has no screenshots, "
            f"so the page still shows the screens of an earlier commit. {rebuild}"
        ]
    return []


def evaluate(payload: object, project: Path, env: Mapping[str, str], run: Runner) -> list[str]:
    if not is_loop(env):
        return []
    if isinstance(payload, dict) and payload.get("stop_hook_active"):
        return []
    try:
        commands = check_commands(env, project)
    except Exception as error:  # fail closed: no config means no proof the checks pass
        return [f"the checks of ops/flow.toml could not be read ({error})"]
    return failures(project, run, commands) + report_problems(project, run)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    problems = evaluate(payload, project, os.environ, real_run)
    if not problems:
        return 0
    print(
        "Blocked by before-finish-check: fix these, or report the issue as failed.\n"
        + "\n".join(problems),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
