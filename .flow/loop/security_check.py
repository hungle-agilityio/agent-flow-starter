"""Security checks on the exact release commit: deploy settings, dependencies, secrets."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    from ops import flow_config
except ImportError:  # started from ops/: it is the first path entry
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]

DEPLOY_HOST = "starter.onrender.com"
TIMEOUT = 300
PIP_AUDIT = "pip-audit@2.10.1"
SECRET_PATTERN = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{32,}"
    r"|sk-ant-[A-Za-z0-9_-]{20,}"
)
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
GIT = ("git", "-c", "core.quotePath=false")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    lines: tuple[str, ...]


class CouldNotRun(Exception):
    """A check could not run; the message is the reason."""


def _run(
    cmd: Sequence[str],
    cwd: Path,
    env: Mapping[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=TIMEOUT,
    )


def _git(tree: Path, *args: str) -> str:
    return _run([*GIT, "-C", str(tree), *args], tree, check=True).stdout


def reason(error: Exception) -> str:
    """The short reason a check could not run."""
    if isinstance(error, CouldNotRun):
        return str(error)
    if isinstance(error, subprocess.CalledProcessError):
        cmd = error.cmd
        first = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else str(cmd)
        return f"{Path(str(first)).name} exited {error.returncode}"
    return type(error).__name__


def _guarded(name: str, check: Callable[[], CheckResult]) -> CheckResult:
    try:
        return check()
    except Exception as error:
        return CheckResult(name, False, ("could not run: " + reason(error),))


def app_folder(tree: Path, app_dir: str) -> Path:
    return tree if app_dir in (".", "") else tree / app_dir


def check_deploy(app: Path) -> CheckResult:
    name = "deploy settings"
    if not (app / "manage.py").is_file():
        return CheckResult(name, True, ("skipped: no manage.py",))
    env = {
        **os.environ,
        "DJANGO_DEBUG": "0",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
        "DJANGO_ALLOWED_HOSTS": DEPLOY_HOST,
    }
    cmd = ["uv", "run", "--frozen", "python", "manage.py", "check", "--deploy"]
    done = _run([*cmd, "--fail-level", "WARNING"], app, env=env)
    if done.returncode == 0:
        return CheckResult(name, True, ())
    found = tuple(
        line
        for line in [*done.stdout.splitlines(), *done.stderr.splitlines()]
        if "(security." in line
    )
    if not found:
        last = [line for line in done.stderr.splitlines() if line.strip()]
        found = (last[-1],) if last else ()
    return CheckResult(name, False, found)


def audit_findings(stdout: str) -> tuple[str, ...] | None:
    """One line per vulnerability, or None when the report is not a pip-audit report."""
    try:
        report = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(report, dict):
        return None
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list):
        return None
    lines: list[str] = []
    for dep in dependencies:
        if not isinstance(dep, dict):
            return None
        vulns = dep.get("vulns") or []
        if not isinstance(vulns, list):
            return None
        for vuln in vulns:
            if not isinstance(vuln, dict):
                return None
            lines.append(f"{dep.get('name')} {dep.get('version')} {vuln.get('id')}")
    return tuple(lines)


def check_dependencies(app: Path, scratch: Path) -> CheckResult:
    name = "dependencies"
    if not (app / "uv.lock").is_file():
        return CheckResult(name, True, ("skipped: no uv.lock",))
    requirements = scratch / "requirements.txt"
    export = _run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-hashes",
            "--no-emit-project",
            "-o",
            str(requirements),
        ],
        app,
    )
    if export.returncode != 0:
        raise CouldNotRun(f"uv exited {export.returncode}")
    audit = _run(
        [
            "uvx",
            PIP_AUDIT,
            "-r",
            str(requirements),
            "--no-deps",
            "--disable-pip",
            "--progress-spinner",
            "off",
            "--format",
            "json",
        ],
        app,
    )
    if audit.returncode == 0:
        return CheckResult(name, True, ())
    if audit.returncode == 1:
        findings = audit_findings(audit.stdout)
        if findings is not None:
            return CheckResult(name, False, findings)
    raise CouldNotRun(f"pip-audit exited {audit.returncode}")


def added_lines(diff: str) -> Iterator[tuple[str, int, str]]:
    """Yield (path, new line number, text) of each added line of a zero-context diff."""
    path: str | None = None
    number = old_left = new_left = 0
    after_added = False  # the last content line was an added one: a bare line is its tail
    for line in diff.split("\n"):
        if line.startswith(("@@ ", "diff --git ")):
            old_left = new_left = 0  # a content line starts with +, - or a space, never with these
            after_added = False
        elif after_added and line and not line.startswith("\\"):
            # After an added line git prints only "+", "\" or a header: anything else is the
            # tail of a line whose carriage return became a newline, so it is scanned too.
            if not line.startswith("+"):
                if path is not None:
                    yield path, number - 1, line
                continue
            if old_left == 0 and new_left == 0:  # a "+" tail used up the hunk's count
                if path is not None:
                    yield path, number, line[1:]
                number += 1
                continue
        if old_left > 0 or new_left > 0:
            if line.startswith("+"):
                if path is not None:
                    yield path, number, line[1:]
                number += 1
                new_left -= 1
                after_added = True
            elif line.startswith("-"):
                old_left -= 1
            continue
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            target = line[4:]
            if target.endswith("\t"):
                target = target[:-1]
            if target == "/dev/null":
                path = None
            elif target.startswith('"') and target.endswith('"') and len(target) >= 2:
                inner = target[1:-1]
                path = inner[2:] if inner.startswith("b/") else inner
            elif target.startswith("b/"):
                path = target[2:]
            else:
                path = None
        else:
            found = HUNK.match(line)
            if found:
                old_left = int(found.group(1)) if found.group(1) is not None else 1
                number = int(found.group(2))
                new_left = int(found.group(3)) if found.group(3) is not None else 1


def tracked_lines(tree: Path, sha: str) -> Iterator[tuple[str, int, str]]:
    names = _git(tree, "ls-tree", "-r", "--full-tree", "--name-only", sha).splitlines()
    for name in names:
        file = tree / name
        if file.is_symlink():
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.split("\n"), start=1):
            yield name, number, line


def check_secrets(tree: Path, sha: str, since: str | None) -> CheckResult:
    if since:
        diff = _git(
            tree,
            "diff",
            "--no-color",
            "--no-ext-diff",
            "--no-relative",
            "--no-renames",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--unified=0",
            since,
            sha,
        )
        source = added_lines(diff)
    else:
        source = tracked_lines(tree, sha)
    lines = tuple(
        f"{path}:{number}" for path, number, text in source if SECRET_PATTERN.search(text)
    )
    return CheckResult("secrets", not lines, lines)


def run_checks(sha: str, since: str | None, cwd: Path) -> tuple[CheckResult, ...]:
    """Run the three checks on a clean checkout of sha; only a failed checkout raises."""
    app_dir = flow_config.load().project_app_dir
    scratch = Path(tempfile.mkdtemp(prefix="release-security-"))
    tree = scratch / "release-tree"
    try:
        _run([*GIT, "worktree", "add", "--detach", str(tree), sha], cwd, check=True)
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    try:
        app = app_folder(tree, app_dir)
        return (
            _guarded("deploy settings", lambda: check_deploy(app)),
            _guarded("dependencies", lambda: check_dependencies(app, scratch)),
            _guarded("secrets", lambda: check_secrets(tree, sha, since)),
        )
    finally:
        try:
            _run([*GIT, "worktree", "remove", "--force", str(tree)], cwd, check=False)
        except Exception:
            pass
        shutil.rmtree(scratch, ignore_errors=True)
