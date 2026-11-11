#!/usr/bin/env python3
"""Before git add and git commit: refuse what the project forbids, and run the quick checks.

The call arrives as JSON on stdin. Exit code 2 blocks it and sends stderr back to Claude.

git add:    refuses force-adding, and the database file, secrets files and caches.
git commit: refuses staged forbidden files, a secret-like string in the staged lines, an
            attribution line in the message, a commit on main, and a failing lint or type check.
If anything goes wrong while checking an add or a commit, the command is blocked.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str], Path], tuple[int, str]]

FORBIDDEN = re.compile(
    r"(?:^|/)(?:db\.sqlite3|[^/]*\.sqlite3?|\.env(?:\..+)?|[^/]*\.(?:pem|key|p12|pfx)|id_rsa"
    r"|id_ed25519|\.coverage|CLAUDE\.local\.md|settings\.local\.json)$"
    r"|(?:^|/)(?:__pycache__|\.venv|\.mypy_cache|\.pytest_cache|\.ruff_cache)(?:/|$)"
)
EXAMPLE_FILE = re.compile(r"\.(?:example|sample)$")
SECRET = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{32,}"
)
ATTRIBUTION = re.compile(r"co-authored-by|generated with", re.I)
PREFIX = r"(?:^|[;&|\n]\s*)(?:\w+=\S+\s+)*git(?:\s+-[cC]\s+\S+)*\s+"
GIT_ADD = re.compile(PREFIX + r"add\b([^;&|\n]*)")
GIT_COMMIT = re.compile(PREFIX + r"commit\b([^;&|\n]*)")
QUOTED_HEREDOC = re.compile(r"<<-?\s*'(\w+)'[^\n]*\n.*?\n\s*\1[ \t]*(?:\n|$)", re.S)
SHELL_WORD = re.compile(r"\b(?:bash|sh|zsh|dash|ksh|eval|source)\b")
MAIN_BRANCHES = {"main", "master"}


def real_run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=180, check=False
        )
    except FileNotFoundError:
        return 127, f"{args[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(args)}: timed out"
    return done.returncode, done.stdout + done.stderr


def without_inert_heredocs(command: str) -> str:
    def drop(match: re.Match[str]) -> str:
        line_start = command.rfind("\n", 0, match.start()) + 1
        head = command[line_start : match.start()] + match.group(0).split("\n", 1)[0]
        return match.group(0) if SHELL_WORD.search(head) else "\n"

    return QUOTED_HEREDOC.sub(drop, command)


def forbidden(path: str) -> bool:
    name = path.strip().strip("'\"")
    return bool(FORBIDDEN.search(name)) and not EXAMPLE_FILE.search(name)


def words(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def names(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.strip()]


def check_add(args: str, cwd: Path, run: Runner) -> list[str]:
    tokens = words(args)
    problems: list[str] = []
    flags = [t for t in tokens if t.startswith("-")]
    if any(t == "--force" or (not t.startswith("--") and "f" in t[1:]) for t in flags):
        problems.append("git add --force is not allowed: ignored files stay ignored")
    for token in (t for t in tokens if not t.startswith("-")):
        if forbidden(token):
            problems.append(
                f"staging {token} is not allowed (database, secrets and caches are never committed)"
            )
    adds_all = any(t in ("--all", "-A") or (not t.startswith("--") and "A" in t[1:]) for t in flags)
    if adds_all or "." in tokens:
        problems.extend(forbidden_in_work_tree(cwd, run))
    return problems


def forbidden_in_work_tree(cwd: Path, run: Runner) -> list[str]:
    _, output = run(["git", "status", "--porcelain"], cwd)
    paths = [line[3:].split(" -> ")[-1] for line in names(output)]
    return [f"git add would stage {p}, which is never committed" for p in paths if forbidden(p)]


def check_commit(command: str, args: str, cwd: Path, run: Runner) -> list[str]:
    tokens = words(args)
    problems: list[str] = []
    _, staged_output = run(["git", "diff", "--cached", "--name-only"], cwd)
    problems.extend(
        f"{p} is staged and must never be committed" for p in names(staged_output) if forbidden(p)
    )
    flags = [t for t in tokens if t.startswith("-") and not t.startswith("--")]
    if "--all" in tokens or any("a" in t[1:] and not t.startswith("-m") for t in flags):
        _, modified = run(["git", "diff", "--name-only"], cwd)
        problems.extend(
            f"git commit -a would commit {p}, which is never committed"
            for p in names(modified)
            if forbidden(p)
        )
    problems.extend(check_attribution(command, tokens, cwd))
    _, branch = run(["git", "branch", "--show-current"], cwd)
    if branch.strip() in MAIN_BRANCHES:
        problems.append(
            f"a commit on {branch.strip()} is not allowed: "
            "create a branch <kind>/<number>-<description> first"
        )
    _, added = run(["git", "diff", "--cached", "-U0"], cwd)
    if any(
        SECRET.search(line)
        for line in added.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ):
        problems.append(
            "a secret-like string is in the staged lines: remove it and use an environment variable"
        )
    if not problems:
        problems.extend(quick_checks(cwd, run))
    return problems


def check_attribution(command: str, tokens: list[str], cwd: Path) -> list[str]:
    found = bool(ATTRIBUTION.search(command))
    for flag in ("-F", "--file"):
        if flag in tokens and tokens.index(flag) + 1 < len(tokens):
            target = tokens[tokens.index(flag) + 1]
            path = cwd / target
            if target != "-" and path.is_file():
                found = found or bool(ATTRIBUTION.search(path.read_text(errors="ignore")))
    if found:
        return [
            "the commit message has an attribution line (Co-Authored-By or Generated with): "
            "the project forbids it"
        ]
    return []


def project_root(cwd: Path) -> Path:
    """The nearest folder, from cwd upwards, that holds pyproject.toml (else cwd)."""
    for folder in (cwd, *cwd.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return cwd


def quick_checks(cwd: Path, run: Runner) -> list[str]:
    problems: list[str] = []
    root = project_root(cwd)
    for label, args in (
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("mypy", ["uv", "run", "mypy", "."]),
    ):
        code, output = run(args, root)
        if code != 0:
            tail = " | ".join(names(output)[-4:])
            problems.append(f"{label} fails, so the commit is refused: {tail}")
    return problems


def evaluate(command: str, cwd: Path, run: Runner = real_run) -> list[str]:
    """Return the reasons to block a command, or an empty list when it may run."""
    stripped = without_inert_heredocs(command)
    adds = GIT_ADD.findall(stripped)
    commits = GIT_COMMIT.findall(stripped)
    if not adds and not commits:
        return []
    problems: list[str] = []
    for args in adds:
        problems.extend(check_add(args, cwd, run))
    for args in commits:
        problems.extend(check_commit(command, args, cwd, run))
    return list(dict.fromkeys(problems))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    if not re.search(r"\bgit\b", command):
        return 0
    cwd = Path(str(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()))
    try:
        problems = evaluate(command, cwd)
    except Exception as error:  # fail closed for an add or a commit
        stripped = without_inert_heredocs(command)
        if not (GIT_ADD.search(stripped) or GIT_COMMIT.search(stripped)):
            return 0
        problems = [f"the hook could not check this command ({error})"]
    if not problems:
        return 0
    print("Blocked by before-commit-check: " + "; ".join(problems) + ".", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
