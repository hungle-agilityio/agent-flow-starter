#!/usr/bin/env python3
"""Draft a pull request from the evidence, and say whether it is complete.

Usage: uv run python <this skill's folder>/draft_pr.py --title "[FEAT] ..."
       --what "..." --why "..." [--issue N] --report <report folder>
       (--compare <before-after folder> | --no-visual) [--out DIR]
       [--plan FILE] [--tests-changed FILE] [--code-review FILE]

It writes pr-body.md (What, Why, How tested with the real numbers of the verify report, Evidence,
One concern, Closes; with --plan a Plan section between What and Why, with --code-review a
"Code review" section right after How tested, with --tests-changed a "Tests changed after the
test author" section after those), copies the changed before and
after images into images/ to drag into the pull request, and writes draft.json. Nothing is created
on GitHub: that waits for the user's approval (create-pull-request).

Exit code: 0 complete (ready to create when there is an issue number), 1 incomplete.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TITLE = re.compile(r"^\[(BUG|FEAT|TASK|EPIC)\] \S")
VISIBLE_LABELS = ("changed", "did not exist before")


def cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def tested_section(report: dict[str, Any] | None, folder: Path | None) -> tuple[str, list[str]]:
    if report is None:
        return "NOT CONFIGURED: no verify report was given.", [
            "how tested: no verify report was given (use --report)"
        ]
    problems: list[str] = []
    verdict = report.get("verdict", "unknown")
    if verdict != "PASS":
        problems.append(f"how tested: the verdict of the report is {verdict}, not PASS")
    rows = "\n".join(
        f"| {cell(a['name'])} | {cell(a['status'])} | {cell(a['evidence'])} |"
        for a in report.get("axes", [])
    )
    text = f"Verdict: **{verdict}**\n\n| Axis | Result | Evidence |\n|---|---|---|\n{rows}"
    return text, problems


def report_link(report: dict[str, Any] | None, folder: Path | None) -> str:
    if report is None:
        return ""
    share = report.get("share") or {}
    if share.get("url"):
        return f"Report (private link): {share['url']}"
    where = f"{folder}/report.html" if folder else "the report folder"
    return f"Report: not shared (local file: {where})"


def evidence_section(
    compare: dict[str, Any] | None, compare_dir: Path | None, no_visual: bool, out: Path
) -> tuple[str, list[str], list[str]]:
    """The evidence text, the problems, and the images copied for the pull request."""
    if no_visual:
        return "Nothing visible to users.", [], []
    if compare is None or compare_dir is None:
        return (
            "NOT CONFIGURED: no before and after images.",
            ["evidence: give --compare (before and after) or --no-visual"],
            [],
        )
    status = (compare.get("masking") or {}).get("status")
    if status != "clean":
        return (
            "NOT CONFIGURED: the images are not masked.",
            [f"evidence: the masking of the images is not clean (status: {status or 'missing'})"],
            [],
        )
    pairs = [p for p in compare.get("pairs", []) if p.get("label") in VISIBLE_LABELS]
    if not pairs:
        return (
            "No page changed in the captured steps.",
            [
                "evidence: no page changed in the captured steps; use --no-visual if the change "
                "is not visible"
            ],
            [],
        )
    folder = out / "images"
    folder.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    lines: list[str] = []
    for number, pair in enumerate(pairs, 1):
        names = []
        for side in ("before", "after"):
            source = pair.get(side)
            if source and Path(source).is_file():
                target = f"{number:02d}-{pair['name']}-{side}.png"
                shutil.copyfile(source, folder / target)
                copied.append(target)
                names.append(target)
        lines.append(
            f"- {pair['name']} ({pair.get('url', '')}), {pair['label']}: {' / '.join(names)}"
        )
    skipped = len(compare.get("pairs", [])) - len(pairs)
    note = f" ({skipped} unchanged page(s) left out)" if skipped else ""
    text = (
        f"Before and after images{note}. Drag these files from `{folder}` into this section:\n\n"
        + "\n".join(lines)
    )
    return text, [], copied


def build_draft(
    title: str,
    what: str,
    why: str,
    issue: int | None,
    report: Path | None,
    compare: Path | None,
    no_visual: bool,
    out: Path,
    plan: Path | None = None,
    tests_changed: Path | None = None,
    code_review: Path | None = None,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    if not TITLE.match(title):
        problems.append("title: it must start with [BUG], [FEAT], [TASK] or [EPIC] and a title")
    for name, value in (("what", what), ("why", why)):
        if not value.strip():
            problems.append(f"{name}: it is empty")
    report_data = json.loads((report / "report.json").read_text()) if report else None
    compare_data = json.loads((compare / "compare.json").read_text()) if compare else None
    tested, found = tested_section(report_data, report)
    problems += found
    evidence, found, images = evidence_section(compare_data, compare, no_visual, out)
    problems += found
    link = report_link(report_data, report)
    ending = (
        f"Closes #{issue}"
        if issue is not None
        else ("_No issue number yet: create the issue first, then add the Closes line._")
    )
    link_block = f"{link}\n\n" if link else ""
    plan_block = f"## Plan\n\n{plan.read_text().strip()}\n\n" if plan else ""
    changed_block = (
        f"## Tests changed after the test author\n\n{tests_changed.read_text().strip()}\n\n"
        if tests_changed
        else ""
    )
    review_block = f"## Code review\n\n{code_review.read_text().strip()}\n\n" if code_review else ""
    body = (
        f"## What\n\n{what.strip()}\n\n{plan_block}## Why\n\n{why.strip()}\n\n"
        f"## How tested\n\n{tested}\n\n{review_block}{changed_block}"
        f"## Evidence\n\n{link_block}{evidence}\n\n"
        f"## One concern\n\n- [ ] This pull request does one thing only\n\n{ending}\n"
    )
    complete = not problems
    result: dict[str, Any] = {
        "title": title,
        "complete": complete,
        "ready_to_create": complete and issue is not None,
        "problems": problems,
        "images": images,
        "issue": issue,
    }
    (out / "pr-body.md").write_text(body)
    (out / "draft.json").write_text(json.dumps(result, indent=2))
    return result


def branch_slug() -> str:
    done = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True, check=False
    )
    return (done.stdout.strip() or "draft").replace("/", "-")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Draft a pull request from the evidence.")
    parser.add_argument("--title", required=True, help="[TYPE] title, the same as the issue")
    parser.add_argument("--what", required=True)
    parser.add_argument("--why", required=True)
    parser.add_argument("--issue", type=int, help="the GitHub issue number, when it exists")
    parser.add_argument("--report", type=Path, help="a folder made by build-verify-report")
    parser.add_argument("--compare", type=Path, help="a folder made by capture-before-after")
    parser.add_argument(
        "--no-visual", action="store_true", help="the change is not visible to users"
    )
    parser.add_argument("--out", type=Path, help="folder (default: out/pr-draft/<branch>)")
    parser.add_argument("--plan", type=Path, help="a file with the plan: a Plan section")
    parser.add_argument(
        "--tests-changed", type=Path, help="a file with the tests changed after the test author"
    )
    parser.add_argument(
        "--code-review", type=Path, help="a file with the code review result: a Code review section"
    )
    args = parser.parse_args(argv)
    out = args.out or Path("out") / "pr-draft" / branch_slug()
    result = build_draft(
        args.title,
        args.what,
        args.why,
        args.issue,
        args.report,
        args.compare,
        args.no_visual,
        out,
        args.plan,
        args.tests_changed,
        args.code_review,
    )
    for problem in result["problems"]:
        print(f"- {problem}")
    if not result["complete"]:
        print(f"INCOMPLETE: {len(result['problems'])} problem(s). Draft: {out / 'pr-body.md'}")
        return 1
    state = (
        "READY TO CREATE" if result["ready_to_create"] else "COMPLETE, but it needs an issue number"
    )
    print(f"{state}. Draft: {out / 'pr-body.md'}; images to drag in: {out / 'images'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
