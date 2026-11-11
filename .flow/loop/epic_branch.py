"""#263: the tick keeps one branch per epic, `epic/<N>-<slug>` (spec epic-branch AC1 to AC6)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GREEN = {"SUCCESS", "NEUTRAL", "SKIPPED"}
SLUG_LIMIT = 40
CONFLICT_REMINDER_SECONDS = 3600
EPIC_PREFIX = "epic/"


def epic_number(body: str) -> int | None:
    """The first `Part of the epic #N` line of a task's issue body."""
    match = re.search(r"^\s*Part of the epic #(\d+)", body or "", re.MULTILINE)
    return int(match.group(1)) if match else None


def number_of(branch: str) -> int | None:
    """The epic number of an `epic/<N>-<slug>` branch, None for any other branch."""
    match = re.fullmatch(r"epic/(\d+)-.*", branch)
    return int(match.group(1)) if match else None


def slug(title: str) -> str:
    """The epic title without `Epic:`, lowercase, letters and digits only, 40 characters."""
    text = re.sub(r"^\s*epic\s*:\s*", "", title, flags=re.IGNORECASE).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text[:SLUG_LIMIT].strip("-")


def branch_name(number: int, title: str) -> str:
    return f"{EPIC_PREFIX}{number}-{slug(title)}"


def is_green(pr: dict[str, Any]) -> bool:
    """At least one check, and every check completed and green."""
    checks = pr.get("statusCheckRollup") or []
    if not checks:
        return False
    for check in checks:
        status = str(check.get("status") or "").upper()
        conclusion = str(check.get("conclusion") or "").upper()
        state = str(check.get("state") or "").upper()
        if status and status != "COMPLETED":
            return False
        if conclusion:
            if conclusion not in GREEN:
                return False
        elif state != "SUCCESS":
            return False
    return True


class EpicBranches:
    """One tick's work on the epic branches; `tick` is the agent_tick.Tick."""

    def __init__(self, tick: Any, repo: str, repo_root: Path, name: str) -> None:
        self.tick = tick
        self.repo = repo
        self.root = repo_root
        self.name = name

    def git(self, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        code, out = self.tick.host.run(["git", "-C", str(cwd or self.root), *args])
        return code, str(out)

    def keep(self, prs: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
        """#364: main goes into every epic branch; a failure never stops the tick."""
        epics = [i for i in issues if "epic" in {label["name"] for label in i.get("labels") or []}]
        if self.git("fetch", "origin", "--prune")[0] != 0:
            self.tick.say("epic branches: git fetch failed; next tick")
            return
        open_epics = {e["number"] for e in epics}
        for epic in sorted(epics, key=lambda e: e["number"]):
            try:
                self.keep_one(epic)
            except RuntimeError as error:
                self.tick.say(f"epic #{epic['number']}: {error}; next tick")
        self.delete_ended(prs, open_epics)

    def exists(self, branch: str) -> bool:
        return self.git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")[0] == 0

    def keep_one(self, epic: dict[str, Any]) -> None:
        number = epic["number"]
        branch = branch_name(number, epic.get("title") or "")
        if not self.exists(branch):
            return  # #364 AC1: the first task of the epic creates it
        work = self.tick.home / "epic-work" / str(number)
        self.git("worktree", "remove", "--force", str(work))
        work.parent.mkdir(parents=True, exist_ok=True)
        code, out = self.git("worktree", "add", "--detach", str(work), f"origin/{branch}")
        if code != 0:
            raise RuntimeError(f"worktree failed ({first_line(out)})")
        try:
            self.merge_main(number, branch, work)
        finally:
            self.git("worktree", "remove", "--force", str(work))

    def contains(self, work: Path, commit: str) -> bool:
        return self.git("merge-base", "--is-ancestor", commit, "HEAD", cwd=work)[0] == 0

    def merge_main(self, number: int, branch: str, work: Path) -> None:
        if not self.contains(work, "origin/main"):
            code, out = self.git(
                "merge", "--no-ff", "-m", f"Merge main into {branch}", "origin/main", cwd=work
            )
            if code != 0:
                self.git("merge", "--abort", cwd=work)
                if "CONFLICT" in out:  # any other failure is a log line, never a message
                    self.remind_conflict(number, branch)
                    self.tick.say(f"epic #{number}: branch {branch}, conflict with main")
                else:
                    self.tick.say(f"epic #{number}: merge of main failed ({first_line(out)})")
                return
            self.clear_conflict(number)
            code, out = self.git("push", "origin", f"HEAD:refs/heads/{branch}", cwd=work)
            if code != 0:
                raise RuntimeError(f"{branch} not pushed ({first_line(out)})")
        self.tick.say(f"epic #{number}: branch {branch}, up to date with main")

    def ask_redo(self, pr: dict[str, Any], branch: str) -> None:
        """AC4: one `/redo` per pull request head; the conflict stays until it is fixed."""
        record = self.tick.home / "epic-redo"
        seen = set(record.read_text().split()) if record.exists() else set()
        key = f"{pr['number']}:{pr.get('headRefOid')}"
        self.tick.say(f"epic: PR #{pr['number']} conflicts with {branch}")
        if key in seen:
            return
        text = f"/redo merge origin/{branch} into this branch and fix the conflict"
        code, _ = self.tick.gh("pr", "comment", str(pr["number"]), "--body", text)
        if code == 0:
            record.write_text("\n".join(sorted(seen | {key})))

    def remind_conflict(self, number: int, branch: str) -> None:
        """AC4: one ntfy message per hour while origin/main does not merge into the branch."""
        record = self.tick.home / f"epic-conflict-{number}"
        now = self.tick.host.now()
        try:
            last = float(record.read_text()) if record.exists() else None
        except ValueError:
            last = None
        if last is not None and now - last < CONFLICT_REMINDER_SECONDS:
            return
        record.write_text(str(now))
        self.tick.notify(f"{self.name} {branch} does not merge with main: conflict")

    def clear_conflict(self, number: int) -> None:
        (self.tick.home / f"epic-conflict-{number}").unlink(missing_ok=True)

    def has_open_base(self, branch: str) -> bool:
        """Any open pull request, the owner's own too; an unreadable answer counts as open."""
        code, out = self.tick.gh(
            "pr", "list", "--base", branch, "--state", "open", "--json", "number"
        )
        if code != 0:
            return True
        try:
            return any(
                isinstance(p, dict) and p.get("baseRefName", branch) == branch
                for p in json.loads(out)
            )
        except (ValueError, TypeError):
            return True

    def epic_closed(self, number: int) -> bool:
        """The list holds open issues only, so a missing epic is checked before its branch goes."""
        code, out = self.tick.gh("issue", "view", str(number), "--json", "state")
        if code != 0:
            return False
        try:
            return str(json.loads(out).get("state")).upper() == "CLOSED"
        except (ValueError, AttributeError):
            return False

    def delete_ended(self, prs: list[dict[str, Any]], open_epics: set[int]) -> None:
        """AC6: an epic branch of a closed epic, with no open pull request based on it."""
        code, out = self.git(
            "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/epic"
        )
        if code != 0:
            return
        for line in out.split():
            branch = line.removeprefix("origin/")
            match = re.fullmatch(r"epic/(\d+)-.*", branch)
            if not match or int(match.group(1)) in open_epics:
                continue
            if any(p.get("state") == "OPEN" and p.get("baseRefName") == branch for p in prs):
                continue
            if not self.epic_closed(int(match.group(1))) or self.has_open_base(branch):
                continue
            code, out = self.tick.host.run(
                ["gh", "api", "-X", "DELETE", f"repos/{self.repo}/git/refs/heads/{branch}"]
            )
            if code != 0:
                self.tick.say(f"branch {branch} not deleted ({first_line(out)}); next tick")
                continue
            self.git("branch", "-D", branch)
            self.git("fetch", "origin", "--prune")
            self.tick.say(f"branch {branch}: deleted, its epic is closed")


def first_line(text: str) -> str:
    return (text.strip().splitlines() or ["no output"])[0]
