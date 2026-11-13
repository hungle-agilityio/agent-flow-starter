"""Roll the live site back to an earlier release through Render's API.

Usage: uv run python ops/rollback.py [--dry-run] [--to <tag>]

Spec: specs/post-release/spec.md (AC11 to AC15). It finds the current release (the newest release
tag on origin/deploy) and the target (the release tag before it, or --to), lists the migrations
and the pull requests between them, finds Render's deploy of the target and asks Render to roll
back to it. `deploy` and the tags are never moved and Auto-Deploy stays on. A refusal is one line
on stderr with exit code 1, before any change. Standard library only.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

try:
    from ops import flow_config, live_check
except ImportError:  # run as a script: python3 ops/rollback.py
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]
    import live_check  # type: ignore[import-not-found,no-redef,unused-ignore]

if TYPE_CHECKING:
    from types import ModuleType

RENDER_API = "https://api.render.com/v1"
TIMEOUT = 30.0
KEY_VAR = "RENDER_API_KEY"
SERVICE_VAR = "RENDER_SERVICE_ID"
DEPLOY_REF = "refs/remotes/origin/deploy"
RELEASE_TAG = re.compile(r"v(\d{4})\.(\d{2})\.(\d{2})(?:\.(\d+))?")
ROLLBACK_STATUSES = ("live", "deactivated")
MIGRATIONS = "migrations"

Request = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int | None, bytes]]


class RollbackError(Exception):
    """The rollback must not go on; the message is its one line on stderr."""


@dataclass(frozen=True)
class Release:
    tag: str
    sha: str
    order: tuple[int, int, int, int]


@dataclass(frozen=True)
class Target:
    current: Release
    target: Release
    deploy_sha: str


@dataclass(frozen=True)
class Settings:
    config: flow_config.FlowConfig
    live: flow_config.LiveConfig
    key: str
    service: str


@dataclass(frozen=True)
class Plan:
    lines: tuple[str, ...]
    settings: Settings
    deploy_id: str
    target: Release


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an answer, never followed: the key must not go to another host."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def request(
    method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
) -> tuple[int | None, bytes]:
    """One HTTP request; the status is None when there is no answer in time or no connection."""
    prepared = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with _OPENER.open(prepared, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""
    except (OSError, ValueError, http.client.HTTPException):
        return None, b""


def tag_order(tag: str) -> tuple[int, int, int, int] | None:
    """The sort key of a release tag (date, then the number, none counts as 1), else None."""
    found = RELEASE_TAG.fullmatch(tag)
    if found is None:
        return None
    year, month, day, number = found.groups()
    return int(year), int(month), int(day), int(number) if number else 1


def _failure(arguments: tuple[str, ...], stderr: str) -> RollbackError:
    lines = stderr.strip().splitlines()
    return RollbackError(f"git {' '.join(arguments)} failed: {lines[0] if lines else ''}")


def _run_git(cwd: Path, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise _failure(arguments, str(error)) from error


def _git(cwd: Path, *arguments: str) -> str:
    done = _run_git(cwd, arguments)
    if done.returncode != 0:
        raise _failure(arguments, done.stderr)
    return done.stdout.strip()


def load_settings(environ: Mapping[str, str], config_path: Path | None) -> Settings:
    """The flow config, its [live] table, the Render key and the service id."""
    try:
        config = flow_config.load(config_path)
    except flow_config.FlowConfigError as error:
        raise RollbackError(str(error)) from error
    if config.live is None:
        raise RollbackError("no [live] table in flow.toml")
    values = live_check.load_settings(config, environ)
    for name in (KEY_VAR, SERVICE_VAR):
        if not values.get(name, ""):
            raise RollbackError(f"{name} is not set in agent.env")
    return Settings(config, config.live, values[KEY_VAR], values[SERVICE_VAR])


def release_tags(cwd: Path) -> list[Release]:
    """Every release tag with its commit, oldest first."""
    listed = _git(
        cwd, "tag", "--list", "v*", "--format=%(refname:strip=2) %(objectname) %(*objectname)"
    )
    releases: list[Release] = []
    for line in listed.splitlines():
        parts = line.split()
        order = tag_order(parts[0]) if len(parts) >= 2 else None
        if order is not None:
            releases.append(Release(parts[0], parts[-1], order))
    return sorted(releases, key=lambda found: found.order)


def _is_ancestor(cwd: Path, commit: str, of: str) -> bool:
    arguments = ("merge-base", "--is-ancestor", commit, of)
    done = _run_git(cwd, arguments)
    if done.returncode not in (0, 1):
        raise _failure(arguments, done.stderr)
    return done.returncode == 0


def find_target(cwd: Path, to: str | None) -> Target:
    """The current release on origin/deploy and the release to roll back to."""
    _git(cwd, "fetch", "origin", "--tags")
    if _run_git(cwd, ("rev-parse", "--verify", "-q", DEPLOY_REF)).returncode != 0:
        raise RollbackError("origin/deploy not found")
    deploy_sha = _git(cwd, "rev-parse", DEPLOY_REF + "^{commit}")
    releases = release_tags(cwd)
    on_deploy = [found for found in releases if found.sha == deploy_sha]
    if not on_deploy:
        raise RollbackError("origin/deploy is not a release tag")
    current = on_deploy[-1]
    if to is not None:
        named = next((found for found in releases if found.tag == to), None)
        if named is None or named.sha == deploy_sha or not _is_ancestor(cwd, named.sha, deploy_sha):
            raise RollbackError(f"{to} is not an earlier release")
        return Target(current, named, deploy_sha)
    earlier = [
        found for found in releases if found.sha != deploy_sha and found.order < current.order
    ]
    if not earlier:
        raise RollbackError("no earlier release to roll back to")
    return Target(current, earlier[-1], deploy_sha)


def count_migrations(cwd: Path, app_dir: str, since: str, until: str) -> int:
    """The migration files of the app folder changed between two commits."""
    changed = _git(cwd, "diff", "--name-only", f"{since}..{until}")
    prefix = "" if app_dir in ("", ".") else app_dir.rstrip("/") + "/"
    count = 0
    for line in changed.splitlines():
        if not line.startswith(prefix):
            continue
        path = PurePosixPath(line[len(prefix) :])
        if MIGRATIONS in path.parts[:-1] and path.suffix == ".py" and path.name != "__init__.py":
            count += 1
    return count


def migrations_line(tag: str, count: int, persistent: bool) -> str:
    """The plan's migrations line; a refusal when the database keeps its data."""
    if count == 0:
        return f"Migrations since {tag}: 0"
    if persistent:
        word = "migration" if count == 1 else "migrations"
        raise RollbackError(
            f"{count} {word} since {tag} and the database is persistent: "
            "write a reversing migration on main and release it"
        )
    return (
        f"Migrations since {tag}: {count} "
        "(the live database is rebuilt from demo data at start; nothing to reverse)"
    )


def _release_module(config: flow_config.FlowConfig) -> ModuleType:
    """ops/release.py, configured with this run's flow config (it loads the default on import)."""
    try:
        try:
            from ops import release
        except ImportError:  # run as a script: python3 ops/rollback.py
            import release  # type: ignore[import-not-found,no-redef,unused-ignore]
    except flow_config.FlowConfigError as error:
        raise RollbackError(str(error)) from error
    release.configure(config)
    return release


def pull_request_lines(
    cwd: Path, config: flow_config.FlowConfig, since: str, until: str
) -> list[str]:
    """The pull requests merged between two commits, client-facing first, as release.py lists."""
    release = _release_module(config)
    try:
        client_facing, internal = release.merged_pull_requests(cwd, since, until)
    except subprocess.CalledProcessError as error:
        arguments = tuple(str(part) for part in error.cmd[1:])
        raise _failure(arguments, str(error.stderr or "")) from error
    except OSError as error:
        raise _failure(("log",), str(error)) from error
    lines = ["  " + str(line) for line in (*client_facing, *internal)]
    return lines or ["  (none)"]


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def _service_url(service: str, path: str) -> str:
    return f"{RENDER_API}/services/{urllib.parse.quote(service, safe='')}/{path}"


def _call(
    request: Request, method: str, url: str, headers: dict[str, str], body: bytes | None
) -> bytes:
    status, answer = request(method, url, headers, body, TIMEOUT)
    if status is None:
        raise RollbackError("Render API failed: no answer")
    if not 200 <= status < 300:
        raise RollbackError(f"Render API failed: HTTP {status}")
    return answer


def _created(deploy: dict[str, Any]) -> datetime | None:
    """createdAt as a UTC date; a date without an offset is read as UTC."""
    try:
        created = datetime.fromisoformat(str(deploy.get("createdAt", "")))
    except ValueError:
        return None
    return created if created.tzinfo else created.replace(tzinfo=UTC)


def find_deploy(request: Request, settings: Settings, target: Release) -> str:
    """The id of Render's newest live or deactivated deploy of the target commit."""
    url = _service_url(settings.service, "deploys?limit=100")
    answer = _call(request, "GET", url, _headers(settings.key), None)
    try:
        items = json.loads(answer)
    except ValueError:
        raise RollbackError("Render API failed: unreadable answer") from None
    found: list[tuple[datetime, str]] = []
    for item in items if isinstance(items, list) else []:
        deploy = item.get("deploy") if isinstance(item, dict) else None
        if not isinstance(deploy, dict):
            continue
        commit = deploy.get("commit")
        created = _created(deploy)
        if (
            isinstance(commit, dict)
            and commit.get("id") == target.sha
            and deploy.get("status") in ROLLBACK_STATUSES
            and created is not None
            and deploy.get("id")
        ):
            found.append((created, str(deploy["id"])))
    if not found:
        raise RollbackError(f"no Render deploy of {target.tag} ({target.sha[:7]}) found")
    return max(found, key=lambda pair: pair[0])[1]


def start_rollback(request: Request, settings: Settings, deploy_id: str) -> None:
    """Ask Render to roll back to the deploy; Render leaves Auto-Deploy as it is."""
    headers = {**_headers(settings.key), "Content-Type": "application/json"}
    body = json.dumps({"deployId": deploy_id}).encode()
    _call(request, "POST", _service_url(settings.service, "rollback"), headers, body)


def make_plan(
    cwd: Path,
    request: Request,
    environ: Mapping[str, str],
    to: str | None,
    config_path: Path | None,
) -> Plan:
    """Settings and tags, target, migrations, pull requests (all git work), then Render's list."""
    settings = load_settings(environ, config_path)
    found = find_target(cwd, to)
    target, current = found.target, found.current
    count = count_migrations(cwd, settings.config.project_app_dir, target.sha, found.deploy_sha)
    migrations = migrations_line(target.tag, count, settings.live.persistent_database)
    subject = _git(cwd, "log", "-1", "--format=%s", target.sha)
    pull_requests = pull_request_lines(cwd, settings.config, target.sha, found.deploy_sha)
    deploy_id = find_deploy(request, settings, target)
    lines = (
        f"Current: {current.tag} {current.sha[:7]}",
        f"Roll back to: {target.tag} {target.sha[:7]} {subject}",
        f"Render deploy: {deploy_id}",
        migrations,
        "Pull requests undone:",
        *pull_requests,
    )
    return Plan(lines, settings, deploy_id, target)


def main(
    argv: list[str] | None = None,
    *,
    request: Request = request,
    environ: Mapping[str, str] = os.environ,
    cwd: Path = flow_config.PROJECT_DIR,
    config_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Roll the live site back to an earlier release.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    parser.add_argument("--to", help="the release tag to roll back to (default: the one before)")
    args = parser.parse_args(argv)
    try:
        plan = make_plan(cwd, request, environ, args.to, config_path)
    except RollbackError as error:
        print(error, file=sys.stderr)
        return 1
    for line in plan.lines:
        print(line)
    if args.dry_run:
        return 0
    try:
        start_rollback(request, plan.settings, plan.deploy_id)
    except RollbackError as error:
        print(error, file=sys.stderr)
        return 1
    check = f"uv run python ops/live_check.py --commit {plan.target.sha}"
    print(f"Rollback started. Check it with: {check}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
