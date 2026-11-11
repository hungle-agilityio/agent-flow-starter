#!/usr/bin/env python3
"""Decide whether a verify report may be shared as a private link.

Usage: share_gate.py <report folder>. Prints ALLOWED or BLOCKED with the reason and exits with
0 or 1. The rules are in rules.md next to this file.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RULES = Path(__file__).with_name("rules.md")


def read_rules(path: Path) -> tuple[str, float] | None:
    try:
        text = path.read_text()
    except OSError:
        return None
    approval = re.search(r"^- standing-approval:\s*(on|off)\s*$", text, re.M)
    size = re.search(r"^- max-size-mb:\s*([0-9.]+)\s*$", text, re.M)
    if approval is None or size is None:
        return None
    return approval.group(1), float(size.group(1))


def decide(folder: Path, rules: Path = RULES) -> tuple[bool, str]:
    """Return (allowed, reason) for the report in this folder."""
    settings = read_rules(rules)
    if settings is None:
        return False, "BLOCKED: the sharing rules could not be read"
    page, data = folder / "report.html", folder / "report.json"
    if not page.is_file() or not data.is_file():
        return False, "BLOCKED: the folder has no report.html and report.json"
    try:
        report = json.loads(data.read_text())
    except ValueError:
        return False, "BLOCKED: report.json is not valid"
    status = (report.get("masking") or {}).get("status") if isinstance(report, dict) else None
    if status != "clean":
        return False, f"BLOCKED: the masking check is not clean (status: {status or 'missing'})"
    approval, limit = settings
    if approval != "on":
        return False, "BLOCKED: the standing approval is off, ask the user"
    for candidate in (page, folder / "report-share.html"):
        if candidate.is_file() and candidate.stat().st_size > limit * 1024 * 1024:
            return False, f"BLOCKED: the page is too big (more than {limit} MB)"
    return True, "ALLOWED: masking is clean, the standing approval is on, the size is fine"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: share_gate.py <report folder>")
        return 2
    allowed, reason = decide(Path(argv[1]))
    print(reason)
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
