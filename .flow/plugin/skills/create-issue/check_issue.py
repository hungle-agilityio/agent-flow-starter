#!/usr/bin/env python3
"""Check that an issue file is complete before it is published.

Usage: check_issue.py <issue file>. Prints one line per problem and exits with 1 when there is
any, 0 when the issue may be published. The rules come from the issue templates and the issue
quality list (title, where, steps, expected and actual, checkable criteria, area and severity).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPE_LABEL = {"BUG": "bug", "FEAT": "feature", "TASK": "task", "EPIC": "epic"}
SECTIONS = {
    "BUG": [
        "Summary",
        "Steps to reproduce",
        "Expected result",
        "Actual result",
        "Environment",
        "Attachments",
    ],
    "FEAT": [
        "Summary",
        "Acceptance criteria",
        "What exists today",
        "How to check it when built",
        "Expected result",
        "Environment",
        "Attachments",
    ],
    "TASK": [
        "Summary",
        "Scope",
        "Done when",
        "Steps to check the result",
        "Expected result",
        "Environment",
        "Attachments",
    ],
    "EPIC": [
        "Goal",
        "Why",
        "Scope",
        "Success criteria",
        "Child issues",
        "Dependencies and risks",
        "Open questions",
        "Scope changes",
        "Environment",
        "Attachments",
    ],
}
KINDS = {"crash", "wrong-data", "performance", "ui", "wrong-output", "intermittent"}
SEVERITIES = {"severity: low", "severity: medium", "severity: high"}
REPRODUCTION = {"reproduced", "partly-reproduced", "cannot-reproduce"}
FLAGS = {"needs-info", "high-priority"}
FIXED = set(TYPE_LABEL.values()) | KINDS | SEVERITIES | REPRODUCTION | FLAGS
TITLE = re.compile(r"^# \[(BUG|FEAT|TASK|EPIC)\] \S")
LABELS_LINE = re.compile(r"^- \*\*Labels:\*\* (.+)$", re.M)
HEADING = re.compile(r"^## (.+)$", re.M)
EMPTY_CASE = re.compile(r"nothing|empty|no reviews|no results|no data", re.I)


def sections_of(text: str) -> dict[str, str]:
    matches = list(HEADING.finditer(text))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip()] = text[match.end() : end].strip()
    return result


def labels_of(text: str) -> list[str]:
    match = LABELS_LINE.search(text)
    return re.findall(r"`([^`]+)`", match.group(1)) if match else []


def check_text(text: str) -> list[str]:
    """Return the problems of an issue file; an empty list means it may be published."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    title = TITLE.match(first)
    if title is None:
        return ["title: it must start with # [BUG], [FEAT], [TASK] or [EPIC] and a title"]
    kind = title.group(1)
    problems: list[str] = []
    if "\\<" in text:
        problems.append("placeholder: a template placeholder (\\<...>) is still in the text")
    sections = sections_of(text)
    for name in SECTIONS[kind]:
        if name not in sections:
            problems.append(f"section missing: {name}")
        elif not sections[name]:
            problems.append(f"section empty: {name}")
    labels = labels_of(text)
    if any(label.startswith("<") for label in labels):
        problems.append("labels: a label placeholder is still in the Labels line")
    if TYPE_LABEL[kind] not in labels:
        problems.append(f"labels: the label {TYPE_LABEL[kind]} is missing (the title says {kind})")
    area = [
        label
        for label in labels
        if label not in FIXED and not label.startswith(("env:", "deadline:", "<"))
    ]
    if not area:
        problems.append("labels: an area label is missing (for example dashboard or hosting)")
    if kind == "BUG":
        problems.extend(check_bug(labels, sections))
    if kind == "FEAT":
        problems.extend(check_feature(sections))
    if kind == "TASK" and "- [ ]" not in sections.get("Done when", "- [ ]"):
        problems.append("Done when: it needs at least one checkbox item (- [ ])")
    if kind == "EPIC":
        problems.extend(check_epic(sections))
    return problems


def check_bug(labels: list[str], sections: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if not KINDS & set(labels):
        problems.append("labels: a kind label is missing (crash, wrong-data, performance, ui...)")
    if not SEVERITIES & set(labels):
        problems.append("labels: a severity label is missing (severity: low, medium or high)")
    if not REPRODUCTION & set(labels):
        problems.append(
            "labels: a reproduction label is missing (reproduced, partly-reproduced...)"
        )
    steps = sections.get("Steps to reproduce")
    if steps is not None and not re.search(r"^\d+\. \S", steps, re.M):
        problems.append("Steps to reproduce: write numbered steps (1. 2. 3.) of what a user does")
    return problems


def check_feature(sections: dict[str, str]) -> list[str]:
    criteria = sections.get("Acceptance criteria")
    if criteria is None:
        return []
    problems: list[str] = []
    for bullet in re.findall(r"^- .+$", criteria, re.M):
        if not re.match(r"- When .+, the screen must ", bullet):
            problems.append(
                "Acceptance criteria: 'When <situation>, the screen must <result>' "
                f"expected, got: {bullet[:60]}"
            )
    if not EMPTY_CASE.search(criteria):
        problems.append(
            "Acceptance criteria: the empty case (when there is nothing to show) is missing"
        )
    return problems


def check_epic(sections: dict[str, str]) -> list[str]:
    problems: list[str] = []
    children = len(re.findall(r"^- \[[ xX]\] ", sections.get("Child issues", ""), re.M))
    if not 3 <= children <= 10:
        problems.append(f"Child issues: an epic needs between 3 and 10 children, it has {children}")
    if "- [ ]" not in sections.get("Success criteria", "- [ ]"):
        problems.append("Success criteria: it needs at least one checkbox item (- [ ])")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: check_issue.py <issue file>")
        return 2
    problems = check_text(Path(argv[1]).read_text())
    for line in problems:
        print(line)
    print(
        "OK: the issue may be published."
        if not problems
        else f"{len(problems)} problem(s): do not publish."
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
