"""Take a picture of each prototype state that a "Screens to capture" step names in "design".

The verify report shows these pictures next to the built screens (Design vs build). Nothing
here fails a build: a state that is missing, or a browser that does not start, becomes a note.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

STATE_IDS = "typeof SCENARIOS === 'undefined' ? [] : SCENARIOS.map(s => s[0])"
SETTLE_MS = 500
NOT_FOUND = "Design not found: {}"
NOT_CAPTURED = "Design not captured: {}"


def first_line(error: Exception) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return lines[0] if lines else type(error).__name__


def capture_designs(
    prototype: Path, steps: list[dict[str, Any]], viewport: dict[str, int], out_dir: Path
) -> list[dict[str, Any]]:
    """One entry per step that has "design", in step order; a new page per state."""
    positions: list[int] = []
    entries: list[dict[str, Any]] = []
    for position, step in enumerate(steps, 1):
        if isinstance(step, dict) and "design" in step:
            state = str(step["design"])
            positions.append(position)
            entries.append(
                {
                    "step": str(step.get("name", "")),
                    "state": state,
                    "design_screenshot": None,
                    "note": NOT_FOUND.format(state),
                }
            )
    if not entries or not prototype.is_file():
        return entries
    done = 0
    try:
        from playwright.sync_api import sync_playwright

        address = prototype.resolve().as_uri()
        out_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(
                    viewport={"width": viewport["width"], "height": viewport["height"]},
                    reduced_motion="reduce",
                )
                page = context.new_page()
                page.goto(f"{address}?bare")
                found = page.evaluate(STATE_IDS)
                page.close()
                ids = {str(item) for item in found} if isinstance(found, list) else set()
                for position, entry in zip(positions, entries, strict=True):
                    if entry["state"] in ids:
                        name = f"design-{position:02d}-{entry['step']}.png"
                        page = context.new_page()
                        page.goto(f"{address}?bare#{entry['state']}")
                        page.wait_for_timeout(SETTLE_MS)
                        page.screenshot(path=out_dir / name, full_page=True)
                        page.close()
                        entry["design_screenshot"] = name
                        entry["note"] = ""
                    done += 1
            finally:
                browser.close()
    except Exception as error:  # the report is written whatever the browser does
        for entry in entries[done:]:
            entry["note"] = NOT_CAPTURED.format(first_line(error))
    return entries
