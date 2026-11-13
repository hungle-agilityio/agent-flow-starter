"""#366: one pull request per epic from its branch into main (spec epic-review-once)."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Sequence
from importlib import util
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    from ops import epic_branch, flow_config
except ImportError:  # run as a script from ops/
    import epic_branch  # type: ignore[import-not-found,no-redef,unused-ignore]
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]

IN_EPIC = "agent:in-epic"
EPIC_TITLE_PREFIX = re.compile(r"^\s*epic\s*:\s*", re.IGNORECASE)
REPORT = re.compile(r"https://claude\.ai/artifact/[^\s)>\]]+")
CLOSES = re.compile(r"Closes #(\d+)")
PULL_URL = re.compile(r"/pull/(\d+)")
CHANGED_TESTS = "## Tests changed by the tasks"
FIRST_CLOSES = re.compile(r"^Closes #", re.MULTILINE)
GUARD_HEADING = "## Guard files changed"
GUARD_SECTION = re.compile(
    rf"\n*^{GUARD_HEADING}\n.*?(?=^##\s|^Closes #|\Z)", re.MULTILINE | re.DOTALL
)
SELF_FIXES = "## Self-decided fixes"
SELF_FIX_SECTION = re.compile(
    rf"\n*^{SELF_FIXES}\n.*?(?=^##\s|^Closes #|\Z)", re.MULTILINE | re.DOTALL
)
REVIEW_CHECKLIST = (
    "## Review checklist\n"
    "\n"
    "- [ ] Every task meets its ACs (open each verify report in the table above)\n"
    "- [ ] Guard files changed: each listed file is expected\n"
    "- [ ] Query budget: each page of the epic stays within the `## Query budget` of its"
    " `tasks.md`\n"
    "- [ ] Self-decided fixes: each fix is acceptable"
)
QUEUE_MARKER = "<!-- work-queue -->"
SELF_FIX_MARKER = "<!-- self-fix -->"


@functools.cache
def _rule_at(module_path: str) -> ModuleType | None:
    """guarded_paths.py loaded by file path; None when it cannot be loaded."""
    try:
        spec = util.spec_from_file_location("guarded_paths", module_path)
        if spec is None or spec.loader is None:
            return None
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module if callable(getattr(module, "guarded_kind", None)) else None
    except Exception:
        return None


def rule_module() -> ModuleType | None:
    """The plugin's guarded_paths.py, found through the flow config at each call."""
    try:
        plugin = flow_config.PROJECT_DIR / flow_config.load().paths_plugin_dir
        return _rule_at(str(plugin / "hooks" / "guarded_paths.py"))
    except Exception:
        return None


def labels_of(item: dict[str, Any]) -> set[str]:
    return {label["name"] for label in item.get("labels") or []}


def title_for(epic: dict[str, Any]) -> str:
    return "[EPIC] " + EPIC_TITLE_PREFIX.sub("", str(epic.get("title") or "")).strip()


def merged_pr(task: int, branch: str, prs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest pull request of the task merged into the epic branch."""
    merged = [
        p
        for p in prs
        if p.get("state") == "MERGED"
        and p.get("baseRefName") == branch
        and CLOSES.search(p.get("body") or "")
        and int(CLOSES.findall(p.get("body") or "")[0]) == task
    ]
    return max(merged, key=lambda p: p["number"]) if merged else None


def row_for(task: int, branch: str, prs: list[dict[str, Any]]) -> str:
    """One table row: the task, its pull request and its verify report."""
    newest = merged_pr(task, branch, prs)
    if newest is None:
        return f"| #{task} | — | — |"
    found = REPORT.search(newest.get("body") or "")
    return f"| #{task} | #{newest['number']} | {found.group(0) if found else '—'} |"


def is_test(path: str) -> bool:
    parts = path.split("/")
    return "tests" in parts or parts[-1].startswith("test_")


def guarded(status: str, path: str, test_dirs: Sequence[tuple[str, ...]]) -> bool:
    """The files before-edit-check guards in loop mode; a new test file is not guarded."""
    return _guarded_by(rule_module(), status, path, test_dirs)


def _guarded_by(
    rule: ModuleType | None, status: str, path: str, test_dirs: Sequence[tuple[str, ...]]
) -> bool:
    """guarded_kind of the plugin's module decides; without the module every file is guarded."""
    parts = tuple(part.casefold() for part in path.split("/") if part)
    if not parts:
        return False
    if rule is None:
        return True
    try:
        if rule.guarded_kind(parts) is not None:
            return True
    except Exception:  # fail closed: a rule that cannot answer guards the file
        return True
    in_tests = any(
        parts[i : i + len(folder)] == folder for folder in test_dirs for i in range(len(parts))
    )
    return in_tests and not status.startswith("A")


def guard_paths(name_status: str, protected_test_dirs: Sequence[str]) -> list[str]:
    """The guarded files of `git diff --name-status` output, in its order (ADR-023)."""
    test_dirs = [
        tuple(p.casefold() for p in folder.split("/") if p not in ("", "."))
        for folder in protected_test_dirs
    ]
    test_dirs = [folder for folder in test_dirs if folder]
    found: list[str] = []
    rule = rule_module()
    for line in name_status.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        path = fields[-1].strip()
        if _guarded_by(rule, fields[0], path, test_dirs) and path not in found:
            found.append(path)
    return found


def guard_block(paths: Sequence[str]) -> str:
    listed = "\n".join(f"- `{path}`" for path in paths) if paths else "None."
    return f"{GUARD_HEADING}\n\n{listed}\n"


def with_guard_section(body: str, paths: Sequence[str]) -> str:
    """The section stands just above the first `Closes` line; an old one is replaced."""
    body = GUARD_SECTION.sub("\n\n", body).rstrip("\n") + "\n"
    block = guard_block(paths)
    match = FIRST_CLOSES.search(body)
    if match is None:
        return f"{body.rstrip()}\n\n{block}"
    before = body[: match.start()].rstrip("\n")
    return f"{before}\n\n{block}\n{body[match.start() :]}"


def lists_guard_files(body: str) -> bool:
    """The body's Guard files section names at least one file."""
    match = GUARD_SECTION.search(body)
    return match is not None and "\n- `" in match.group(0)


def self_fix_urls(comments: Sequence[dict[str, Any]]) -> list[str]:
    """The links of the comments whose first lines are the work-queue and self-fix markers."""
    found: list[str] = []
    for comment in comments:
        lines = str(comment.get("body") or "").strip().splitlines()
        if [line.strip() for line in lines[:2]] == [QUEUE_MARKER, SELF_FIX_MARKER]:
            found.append(str(comment.get("url") or ""))
    return found


def self_fix_block(lines: Sequence[str]) -> str:
    return f"{SELF_FIXES}\n\n{chr(10).join(lines) if lines else 'None.'}\n"


def with_self_fixes(body: str, lines: Sequence[str]) -> str:
    """fail-fix AC12: the section stands just above the first `Closes` line; an old one goes."""
    body = SELF_FIX_SECTION.sub("\n\n", body).rstrip("\n") + "\n"
    block = self_fix_block(lines)
    match = FIRST_CLOSES.search(body)
    if match is None:
        return f"{body.rstrip()}\n\n{block}"
    before = body[: match.start()].rstrip("\n")
    return f"{before}\n\n{block}\n{body[match.start() :]}"


def body_for(
    marker: str,
    epic: int,
    branch: str,
    tasks: list[int],
    prs: list[dict[str, Any]],
    changes: list[str],
    guards: Sequence[str] | None = None,
    fixes: Sequence[str] | None = None,
) -> str:
    rows = [row_for(task, branch, prs) for task in tasks]
    closing = [f"Closes #{task}" for task in tasks] + [f"Closes #{epic}"]
    lines = [marker, "", "| Task | Pull request | Verify report |", "|---|---|---|", *rows]
    lines += ["", REVIEW_CHECKLIST]
    if changes:
        lines += ["", CHANGED_TESTS, "", *changes]
    if fixes is not None:
        lines += ["", self_fix_block(fixes).rstrip("\n")]
    if guards is not None:
        lines += ["", guard_block(guards).rstrip("\n")]
    return "\n".join([*lines, "", *closing]) + "\n"


def with_line(body: str, epic: int, task: int) -> str:
    """The task's `Closes` line goes just above the epic's, the last of the list."""
    line = f"Closes #{task}"
    last = re.compile(rf"^Closes #{epic}\b", re.MULTILINE)
    if last.search(body):
        return last.sub(f"{line}\nCloses #{epic}", body, count=1)
    return f"{body.rstrip()}\n{line}\n"


def with_changes(body: str, changes: list[str]) -> str:
    """#380 AC3: new lines go into the section, which stands above the `Closes` lines."""
    if not changes:
        return body
    text = "\n".join(changes)
    if CHANGED_TESTS in body:
        return body.replace(f"{CHANGED_TESTS}\n\n", f"{CHANGED_TESTS}\n\n{text}\n", 1)
    block = f"\n{CHANGED_TESTS}\n\n{text}\n\nCloses #"
    if FIRST_CLOSES.search(body):
        return FIRST_CLOSES.sub(lambda _: block, body, count=1)
    return f"{body.rstrip()}\n{block.removesuffix('Closes #')}"


def changed_files(tick: Any, root: Path, base: str, head: str) -> str | None:
    """`git diff --name-status` of head against base on origin, or None when it fails."""
    tick.host.run(["git", "-C", str(root), "fetch", "-q", "origin", base, head])
    span = f"origin/{base}...origin/{head}"
    code, out = tick.host.run(["git", "-C", str(root), "diff", "--name-status", span])
    return str(out) if code == 0 else None


class EpicPullRequests:
    """One tick's work on the epic pull requests; `tick` is the agent_tick.Tick."""

    def __init__(
        self,
        tick: Any,
        repo: str,
        repo_root: Path,
        marker: str,
        protected_test_dirs: Sequence[str] = (),
    ) -> None:
        self.tick = tick
        self.repo = repo
        self.root = repo_root
        self.marker = marker
        self.test_dirs = tuple(protected_test_dirs)

    def self_fixes(self, tasks: list[int]) -> list[str]:
        """fail-fix AC12: one line per self-fix comment of a task, read from GitHub."""
        lines: list[str] = []
        for task in tasks:
            found = self.tick.gh_json("issue", "view", str(task), "--json", "comments")
            comments = found.get("comments") if isinstance(found, dict) else None
            lines += [f"- #{task}: {url}" for url in self_fix_urls(comments or [])]
        return lines

    def guards(self, branch: str) -> list[str]:
        """AC8: the guarded files of the whole epic branch against main."""
        found = changed_files(self.tick, self.root, "main", branch)
        if found is None:
            raise RuntimeError(f"guard files of {branch} not read")
        return guard_paths(found, self.test_dirs)

    def keep(self, prs: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
        """AC1, AC5: one failure is one log line and never stops the other epics."""
        for epic in sorted(issues, key=lambda i: i["number"]):
            if "epic" not in labels_of(epic):
                continue
            try:
                self.one(epic, prs, issues)
            except (RuntimeError, ValueError) as error:
                self.tick.say(f"epic #{epic['number']}: {error}; next tick")

    def one(
        self, epic: dict[str, Any], prs: list[dict[str, Any]], issues: list[dict[str, Any]]
    ) -> None:
        number = epic["number"]
        branch = epic_branch.branch_name(number, epic.get("title") or "")
        tasks = sorted(
            (i for i in issues if epic_branch.epic_number(i.get("body") or "") == number),
            key=lambda i: i["number"],
        )
        opened = next(
            (
                p
                for p in prs
                if p["state"] == "OPEN"
                and p.get("headRefName") == branch
                and p.get("baseRefName") == "main"
            ),
            None,
        )
        if opened is not None:
            in_branch = [t["number"] for t in tasks if IN_EPIC in labels_of(t)]
            self.add_lines(opened, number, branch, in_branch, prs)
            return
        if not tasks or any(IN_EPIC not in labels_of(t) for t in tasks):
            return
        if self.open_on_github(branch):
            return
        if not self.has_main(branch):
            self.tick.say(f"epic #{number}: pull request waits, {branch} does not have main")
            return
        self.open(epic, branch, [t["number"] for t in tasks], prs)

    def open_on_github(self, branch: str) -> bool:
        """An open pull request the loop's list does not show, the owner's own for example."""
        found = self.tick.gh_json(
            "pr", "list", "--head", branch, "--base", "main", "--state", "open", "--json", "number"
        )
        return bool(found)

    def has_main(self, branch: str) -> bool:
        ancestor = ["merge-base", "--is-ancestor", "origin/main", f"origin/{branch}"]
        code, _ = self.tick.host.run(["git", "-C", str(self.root), *ancestor])
        return bool(code == 0)

    def write_body(self, number: int, body: str) -> Path:
        path = self.tick.home / f"epic-pr-{number}.md"
        path.write_text(body)
        return Path(path)

    def open(
        self, epic: dict[str, Any], branch: str, tasks: list[int], prs: list[dict[str, Any]]
    ) -> None:
        number = epic["number"]
        changes = self.changed_tests(tasks, branch, prs)
        guards = self.guards(branch)
        fixes = self.self_fixes(tasks)
        body = body_for(self.marker, number, branch, tasks, prs, changes, guards, fixes)
        path = self.write_body(number, body)
        code, out = self.tick.gh(
            "pr", "create", "--base", "main", "--head", branch,
            "--title", title_for(epic), "--body-file", str(path),
        )  # fmt: skip
        if code != 0:
            first = epic_branch.first_line(out)
            self.tick.say(f"epic #{number}: pull request not opened ({first}); next tick")
            return
        match = PULL_URL.search(out)
        new = match.group(1) if match else "?"
        self.tick.say(f"epic #{number}: opened PR #{new} into main")
        flag = " (changes guard files)" if guards else ""
        self.tick.notify(f"Epic #{number} is ready for your review: PR #{new}{flag}")

    def changed_tests(self, tasks: list[int], branch: str, prs: list[dict[str, Any]]) -> list[str]:
        """#380 AC2, AC4: read from GitHub, because these merges had no human review."""
        lines: list[str] = []
        for task in tasks:
            merged = merged_pr(task, branch, prs)
            if merged is not None:
                lines += self.changed_by(task, merged["number"])
        return lines

    def changed_by(self, task: int, number: int) -> list[str]:
        files = f"repos/{self.repo}/pulls/{number}/files?per_page=100"
        code, out = self.tick.host.run(["gh", "api", files])
        if code != 0:
            raise RuntimeError(f"files of PR #{number} not read ({epic_branch.first_line(out)})")
        try:
            found = json.loads(out)
        except ValueError as error:
            raise RuntimeError(f"files of PR #{number} not read (not JSON)") from error
        return [
            f"- `{item['filename']}`: "
            f"{'removed' if item['status'] == 'removed' else 'changed'} by #{task} in PR #{number}"
            for item in found
            if item["status"] != "added" and is_test(item["filename"])
        ]

    def add_lines(
        self,
        pr: dict[str, Any],
        epic: int,
        branch: str,
        tasks: list[int],
        prs: list[dict[str, Any]],
    ) -> None:
        """AC5: a task that reached the epic branch after the pull request was opened."""
        body = str(pr.get("body") or "")
        have = {int(n) for n in CLOSES.findall(body)}
        missing = [task for task in tasks if task not in have]
        if not missing:
            return
        body = with_changes(body, self.changed_tests(missing, branch, prs))
        for task in missing:
            body = with_line(body, epic, task)
        everyone = sorted(have | set(missing))
        body = with_self_fixes(body, self.self_fixes([t for t in everyone if t != epic]))
        body = with_guard_section(body, self.guards(branch))
        path = self.write_body(epic, body)
        code, out = self.tick.gh("pr", "edit", str(pr["number"]), "--body-file", str(path))
        if code != 0:
            first = epic_branch.first_line(out)
            self.tick.say(f"pr-{pr['number']}: Closes lines not added ({first}); next tick")
            return
        pr["body"] = body
        listed = ", ".join(f"#{task}" for task in missing)
        self.tick.say(f"pr-{pr['number']}: Closes lines added for {listed}")
