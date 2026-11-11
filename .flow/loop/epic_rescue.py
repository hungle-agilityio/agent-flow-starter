"""#329: a pull request merged into an epic branch gets a new one into main (spec epic-close)."""

from __future__ import annotations

import json
import re
import traceback
from pathlib import Path
from typing import Any

EPIC_PREFIX = "epic/"
RECORD = "epic-rescued"
READY = "pr:ready-for-review"
STACKED_LINE = re.compile(r"^.*Stacked on [^\n]*through epic/\S+.*\n?", re.MULTILINE)
STACKED_PARENTS = re.compile(r"Stacked on ((?:#\d+(?:, )?)+) through epic/\S+")
CLOSES = re.compile(r"Closes #(\d+)")
PULL_URL = re.compile(r"/pull/(\d+)")
VIEW_FIELDS = "number,state,baseRefName,headRefName,headRefOid,title,body,labels"


def rescued(home: Path) -> set[int]:
    record = home / RECORD
    return {int(n) for n in record.read_text().split()} if record.exists() else set()


def remember(home: Path, number: int) -> None:
    record = home / RECORD
    record.write_text("\n".join(str(n) for n in sorted(rescued(home) | {number})))


def parents_of(body: str) -> list[int]:
    match = STACKED_PARENTS.search(body)
    return [int(n) for n in re.findall(r"#(\d+)", match.group(1))] if match else []


def without_stacked(body: str) -> str:
    return STACKED_LINE.sub("", body)


class EpicRescue:
    """One tick's rescue; `tick` is the agent_tick.Tick, `marker` the loop's comment marker."""

    def __init__(self, tick: Any, root: Path) -> None:
        self.tick = tick
        self.root = root

    def run(self, prs: list[dict[str, Any]], open_issues: set[int]) -> None:
        """AC1 to AC4: one failure is one log line and never stops the others."""
        done = rescued(self.tick.home)
        by_number = {pr["number"]: pr for pr in prs}
        for old in prs:
            number = old["number"]
            match = CLOSES.search(old.get("body") or "")
            issue = int(match.group(1)) if match else None
            if old.get("state") != "MERGED" or number in done:
                continue
            if issue is None or issue not in open_issues:
                continue
            try:
                self.one(number, issue, by_number)
            except Exception as error:  # noqa: BLE001 - the tick must go on
                self.tick.say(
                    f"pr-{number}: epic rescue failed ({type(error).__name__}); next tick"
                )
                traceback.print_exc()

    def one(self, number: int, issue: int, by_number: dict[int, dict[str, Any]]) -> None:
        tick = self.tick
        code, out = tick.gh("pr", "view", str(number), "--json", VIEW_FIELDS)
        if code != 0:
            tick.say(f"pr-{number}: epic rescue could not read it ({out.strip()}); next tick")
            return

        old = json.loads(out)
        base = str(old.get("baseRefName") or "")
        if not base.startswith(EPIC_PREFIX):
            return
        if not parents_of(str(old.get("body") or "")):
            remember(tick.home, number)  # #364 AC4: a task merged into its epic branch stays there
            return
        head = str(old.get("headRefName") or "")
        in_main = self.in_main(str(old.get("headRefOid") or ""))
        if in_main is None:
            tick.say(f"pr-{number}: epic rescue could not check main; next tick")
            return
        if in_main:
            remember(tick.home, number)
            return
        body = str(old.get("body") or "")
        state = self.parents(parents_of(body), by_number)
        for parent, parent_state in state.items():
            if parent_state == "OPEN":
                tick.say(
                    f"pr-{number}: merged into {base}; waits for #{parent} "
                    "before opening a pull request into main"
                )
                return
        closed = [p for p, s in state.items() if s != "MERGED"]
        if closed:
            tick.say(f"pr-{number}: merged into {base}; #{closed[0]} was closed without merge")
            tick.notify(
                f"PR #{number} was merged into {base}, not main, and #{closed[0]} "
                f"was closed without merge: nothing opened for #{issue}"
            )
            remember(tick.home, number)
            return
        if self.open_into_main(head):
            remember(tick.home, number)
            return
        self.open(number, issue, old, base, head, body)

    def in_main(self, oid: str) -> bool | None:
        """True when the commit is in origin/main, False when not, None when git cannot say."""
        if not oid:
            return None
        code, _ = self.tick.host.run(
            ["git", "-C", str(self.root), "merge-base", "--is-ancestor", oid, "origin/main"]
        )
        return {0: True, 1: False}.get(code)

    def parents(self, numbers: list[int], by_number: dict[int, dict[str, Any]]) -> dict[int, str]:
        found: dict[int, str] = {}
        for parent in numbers:
            known = by_number.get(parent)
            if known is not None:
                found[parent] = str(known.get("state"))
                continue
            code, out = self.tick.gh("pr", "view", str(parent), "--json", "state")
            found[parent] = "OPEN" if code != 0 else str(json.loads(out)["state"])
        return found

    def open_into_main(self, head: str) -> bool:
        found = self.tick.gh_json(
            "pr", "list", "--head", head, "--base", "main", "--state", "open", "--json", "number"
        )
        return bool(found)

    def open(
        self, number: int, issue: int, old: dict[str, Any], base: str, head: str, body: str
    ) -> None:
        tick = self.tick
        path = tick.home / f"epic-rescue-{number}.md"
        path.write_text(without_stacked(body))
        code, out = tick.gh(
            "pr", "create", "--base", "main", "--head", head,
            "--title", str(old.get("title") or ""), "--body-file", str(path),
        )  # fmt: skip
        if code != 0:
            tick.say(f"pr-{number}: new pull request not opened ({out.strip()}); next tick")
            return
        remember(tick.home, number)
        match = PULL_URL.search(out)
        new = match.group(1) if match else "?"
        names = {label["name"] for label in old.get("labels") or []}
        if new != "?" and READY in names:
            tick.gh("pr", "edit", new, "--add-label", READY)
        tick.gh("issue", "edit", str(issue), "--add-label", "agent:review")
        tick.rescued.add(issue)
        tick.say(f"pr-{number}: merged into {base}; opened PR #{new} into main for #{issue}")
        tick.notify(f"PR #{number} was merged into {base}, not main: opened PR #{new} for #{issue}")
