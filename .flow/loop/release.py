"""Cut a sprint release: branch `release/sprint-N`, a date tag, and `deploy` moved to the commit.

Run by hand on the Mac mini: `uv run python ops/release.py [--dry-run] [--notes-url <url>]`.
Spec: specs/release-deploy/spec.md (AC4 to AC9). It never forces a push, never pushes `main`
and never changes an existing release ref. After the push it creates the GitHub Release page
of the new tag (specs/release-page/spec.md); a page that fails is a warning, not a failure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

try:
    from ops import flow_config
except ImportError:  # started as `python ops/release.py`: ops/ is the first path entry
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]

if TYPE_CHECKING:
    from ops import security_check

DEPLOY = "deploy"
SPRINT_PREFIX = "release/sprint-"
ZONE = ZoneInfo("UTC")
CI_WORKFLOW = ""
DEPLOY_LINE = ""
PR_NUMBER = re.compile(r"#(\d+)")
PROJECT_ROOT = flow_config.PROJECT_DIR
CODE_DIRS: tuple[str, ...] = ()
APP_DIR = "."
STATE_DIR = Path(".")
GITHUB_HOST = "github.com"
PAGE_TIMEOUT_SECONDS = 60
SETTINGS_FILE = ".claude/project-instructions.md"
SETTINGS_LINE = (
    "Project settings: " + SETTINGS_FILE + " changed since the last release; "
    "paste it into Project settings."
)


def configure(config: flow_config.FlowConfig) -> None:
    """Set the time zone, CI workflow, deploy line and code folders from the flow config."""
    global ZONE, CI_WORKFLOW, DEPLOY_LINE, CODE_DIRS, APP_DIR, STATE_DIR
    ZONE = ZoneInfo(config.release_timezone)
    CI_WORKFLOW = config.checks_ci_workflow
    DEPLOY_LINE = config.release_deploy_line
    CODE_DIRS = config.paths_code_dirs
    APP_DIR = config.project_app_dir
    STATE_DIR = config.loop_state_dir


configure(flow_config.load())


class Refusal(Exception):
    """The release must not happen; the message is the one line shown to the owner."""


@dataclass(frozen=True)
class Plan:
    sha: str
    title: str
    branch: str
    tag: str
    client_facing: tuple[str, ...]
    internal: tuple[str, ...]
    security: tuple[str, ...] = ()
    settings_changed: bool = False


def git(args: Sequence[str], cwd: Path, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)
    return done.stdout.strip()


def latest_checks(sha: str, cwd: Path) -> str | None:
    """The newest CI run of a commit: "success", another conclusion, "running" or None."""
    done = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            CI_WORKFLOW,
            "--commit",
            sha,
            "--limit",
            "1",
            "--json",
            "status,conclusion",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    runs = json.loads(done.stdout or "[]")
    if not runs:
        return None
    if runs[0]["status"] != "completed":
        return "running"
    return str(runs[0]["conclusion"] or "failure")


def run_security(sha: str, since: str | None, cwd: Path) -> tuple[security_check.CheckResult, ...]:
    """Run the security checks on the release commit."""
    try:
        from ops import security_check as checks
    except ImportError:  # started as `python ops/release.py`
        import security_check as checks  # type: ignore[import-not-found,no-redef,unused-ignore]

    return checks.run_checks(sha, since, cwd)


def security_lines(
    results: tuple[security_check.CheckResult, ...], since: str | None, sha: str
) -> tuple[str, ...]:
    """The printed security block of a release plan."""
    lines = ["Security checks:"]
    for result in results:
        lines.append("  " + result.name + (": ok" if result.ok else ": FAILED"))
        lines.extend("    " + line for line in result.lines)
    if since:
        lines.append("Security review diff: " + since[:7] + ".." + sha[:7])
    else:
        lines.append("Security review diff: " + sha[:7] + " (first release)")
    return tuple(lines)


def remote_names(cwd: Path, kind: str) -> set[str]:
    out = git(["ls-remote", "--" + kind, "origin"], cwd)
    return {line.split("\t")[1].split("/", 2)[2] for line in out.splitlines() if "\t" in line}


def next_branch(branches: set[str]) -> str:
    numbers = [
        int(b[len(SPRINT_PREFIX) :])
        for b in branches
        if b.startswith(SPRINT_PREFIX) and b[len(SPRINT_PREFIX) :].isdigit()
    ]
    return SPRINT_PREFIX + str(max(numbers, default=0) + 1)


def next_tag(tags: set[str], now: datetime) -> str:
    base = "v" + now.astimezone(ZONE).strftime("%Y.%m.%d")
    tag, count = base, 1
    while tag in tags:
        count += 1
        tag = base + "." + str(count)
    return tag


def code_prefixes() -> tuple[str, ...]:
    """Path prefixes, from the repository root, of the code folders."""
    base = "" if APP_DIR == "." else APP_DIR + "/"
    return tuple(base + code_dir + "/" for code_dir in CODE_DIRS)


def is_client_facing(cwd: Path, merge: str) -> bool:
    """A pull request is client-facing when it changes a file inside a code folder."""
    out = git(["diff", "--name-only", merge + "^1", merge], cwd)
    prefixes = code_prefixes()
    return any(path.startswith(prefixes) for path in out.splitlines())


def merged_pull_requests(
    cwd: Path, since: str | None, sha: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    span = since + ".." + sha if since else sha
    out = git(
        ["log", "--merges", "--first-parent", "--reverse", "--format=%H%x00%s%x00%b%x1e", span],
        cwd,
    )
    client_facing: list[str] = []
    internal: list[str] = []
    for record in out.split("\x1e"):
        merge, _, rest = record.strip().partition("\x00")
        subject, _, body = rest.partition("\x00")
        found = PR_NUMBER.search(subject)
        if not found:
            continue
        title = next((ln.strip() for ln in body.splitlines() if ln.strip()), subject)
        line = "#" + found.group(1) + " " + title
        (client_facing if is_client_facing(cwd, merge) else internal).append(line)
    return tuple(client_facing), tuple(internal)


def settings_changed(cwd: Path, since: str | None, sha: str) -> bool:
    """The Project settings text on the release commit differs from the last release."""
    path = ("" if APP_DIR == "." else APP_DIR + "/") + SETTINGS_FILE
    try:
        new = git(["ls-tree", sha, "--", path], cwd)
        old = git(["ls-tree", since, "--", path], cwd) if since else ""
    except (subprocess.CalledProcessError, OSError):
        return False
    return bool(new) and new != old


def make_plan(cwd: Path, now: datetime) -> Plan:
    git(["fetch", "origin"], cwd)
    sha = git(["rev-parse", "origin/main"], cwd)
    short = sha[:7]
    status = latest_checks(sha, cwd)
    if status is None:
        raise Refusal("no " + CI_WORKFLOW + " run found for " + short)
    if status == "running":
        raise Refusal(CI_WORKFLOW + " are still running for " + short)
    if status != "success":
        raise Refusal(CI_WORKFLOW + " did not succeed for " + short + " (" + status + ")")
    deploy = git(["rev-parse", "--verify", "-q", "refs/remotes/origin/" + DEPLOY], cwd, check=False)
    if deploy == sha:
        raise Refusal("nothing new to release")
    if deploy:
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", deploy, sha], cwd=cwd)
        if ancestor.returncode != 0:
            raise Refusal("origin/" + DEPLOY + " is not an ancestor of " + short)
    results = run_security(sha, deploy or None, cwd)
    security = security_lines(results, deploy or None, sha)
    failed = [result.name for result in results if not result.ok]
    if failed:
        print("\n".join(security), file=sys.stderr)
        raise Refusal("security check failed: " + ", ".join(failed))
    tags = remote_names(cwd, "tags") | set(git(["tag", "-l"], cwd).splitlines())
    client_facing, internal = merged_pull_requests(cwd, deploy or None, sha)
    return Plan(
        sha=sha,
        title=git(["log", "-1", "--format=%s", sha], cwd),
        branch=next_branch(remote_names(cwd, "heads")),
        tag=next_tag(tags, now),
        client_facing=client_facing,
        internal=internal,
        security=security,
        settings_changed=settings_changed(cwd, deploy or None, sha),
    )


def describe(plan: Plan) -> list[str]:
    lines = [
        "Commit: " + plan.sha[:7] + " " + plan.title,
        "Branch: " + plan.branch,
        "Tag: " + plan.tag,
        *plan.security,
        "Client-facing pull requests:",
        *(["  " + pr for pr in plan.client_facing] or ["  (none)"]),
        "Internal pull requests:",
        *(["  " + pr for pr in plan.internal] or ["  (none)"]),
    ]
    if plan.settings_changed:
        lines.append(SETTINGS_LINE)
    return lines


def push(plan: Plan, cwd: Path) -> None:
    git(["tag", "-a", plan.tag, plan.sha, "-m", plan.branch], cwd)
    try:
        git(
            [
                "push",
                "--atomic",
                "origin",
                plan.sha + ":refs/heads/" + plan.branch,
                "refs/tags/" + plan.tag + ":refs/tags/" + plan.tag,
                plan.sha + ":refs/heads/" + DEPLOY,
            ],
            cwd,
        )
    except subprocess.CalledProcessError:
        git(["tag", "-d", plan.tag], cwd, check=False)
        raise


def notes_text(plan: Plan, notes_url: str | None) -> str:
    """The notes of the Release page: the two pull request groups, then the notes link if any."""
    lines = [
        "Release " + plan.tag + " (" + plan.branch + ", commit " + plan.sha[:7] + ")",
        "",
        "Client-facing pull requests:",
        *(["- " + pr for pr in plan.client_facing] or ["- (none)"]),
        "",
        "Internal pull requests:",
        *(["- " + pr for pr in plan.internal] or ["- (none)"]),
    ]
    if notes_url:
        lines += ["", "Release notes: " + notes_url]
    return "\n".join(lines) + "\n"


def last_line(text: str | None) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def release_page(plan: Plan, cwd: Path, notes_url: str | None) -> str | None:
    """The first stdout line for the new Release page; a failure is one warning on stderr."""
    if GITHUB_HOST not in git(["remote", "get-url", "origin"], cwd, check=False):
        return None
    notes = (STATE_DIR / ("release-" + plan.tag + ".md")).absolute()
    command = ["gh", "release", "create", plan.tag, "--title", plan.tag]
    command += ["--notes-file", str(notes), "--verify-tag"]
    try:
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text(notes_text(plan, notes_url))
        done = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=PAGE_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as failure:
        reason = last_line(failure.stderr) or last_line(failure.stdout)
        reason = reason or "exit " + str(failure.returncode)
    except (subprocess.TimeoutExpired, OSError) as failure:
        reason = type(failure).__name__
    else:
        url = last_line(done.stdout)
        return "Release page: " + url if url else None
    retry = " ".join(command)
    print("warning: GitHub Release not created (" + reason + "); run: " + retry, file=sys.stderr)
    return None


def main(
    argv: Sequence[str] | None = None, cwd: Path = PROJECT_ROOT, now: datetime | None = None
) -> int:
    parser = argparse.ArgumentParser(description="Cut a sprint release.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, push nothing")
    parser.add_argument("--notes-url", help="link to the release notes page, for the Release page")
    args = parser.parse_args(argv)
    try:
        plan = make_plan(cwd, now or datetime.now(ZONE))
        if args.dry_run:
            print("\n".join(describe(plan)))
            return 0
        push(plan, cwd)
    except Refusal as refusal:
        print(str(refusal), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as failure:
        detail = (failure.stderr or "").strip().splitlines()
        print("git or gh failed: " + (detail[-1] if detail else str(failure.cmd)), file=sys.stderr)
        return 1
    except (subprocess.TimeoutExpired, OSError) as failure:
        print("git or gh failed: " + type(failure).__name__, file=sys.stderr)
        return 1
    page = release_page(plan, cwd, args.notes_url)
    if page:
        print(page)
    print("\n".join(describe(plan)))
    if DEPLOY_LINE:
        print(DEPLOY_LINE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
