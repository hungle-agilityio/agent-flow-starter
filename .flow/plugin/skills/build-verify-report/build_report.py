#!/usr/bin/env python3
"""Run every verify axis and write one report that a person can open and read.

Usage: uv run python <this skill's folder>/build_report.py --title "<issue>"
       [--criteria FILE] [--review FILE] [--browser --spec FILE | --no-ui] [--no-open] [--out DIR]

The numbers in the report are read from the real output of each command by this program;
nothing is retyped. It writes report.html (one self-contained page, screenshots embedded) and
report.json to out/verify/<time>/, and opens the page unless --no-open is given.

A task that changes a screen passes --browser with the issue's "Screens to capture" as --spec;
each step shows its full page next to its close-up. A task that changes no screen passes --no-ui
and gets no screenshots.

Exit code: 0 PASS, 1 FAIL, 2 INCOMPLETE (some axis is NOT CONFIGURED, none failed).
"""

from __future__ import annotations

import argparse
import base64
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
import webbrowser
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

Runner = Callable[[list[str], Path], tuple[int, str]]
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
COVERAGE_INCLUDE = "FLOW_COVERAGE_INCLUDE"
COVERAGE_FAIL_UNDER = "FLOW_COVERAGE_FAIL_UNDER"
QUERY_ASSERTION = re.compile(r"django_assert_(?:max_)?num_queries|assert(?:Max)?NumQueries", re.I)
TOTAL_COVERAGE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", re.M)
PASSED = re.compile(r"(\d+) passed")
FAILED = re.compile(r"(\d+) failed")
MYPY_FILES = re.compile(r"no issues found in (\d+) source files?")
STATUSES = ("PASS", "FAIL", "NOT CONFIGURED", "NOT APPLICABLE")
NO_UI_EVIDENCE = "the task changes no screen"
# The plugin's own tests run as in CI: a build's loop mode must not leak into them (#243).
WITHOUT_LOOP = ["env", "-u", "FLOW_LOOP"]
NO_SCREENS = 'no screens given: pass --spec from the issue\'s "Screens to capture"'


def real_run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=900, check=False
        )
    except FileNotFoundError:
        return 127, f"{args[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(args)}: timed out"
    return done.returncode, done.stdout + done.stderr


def parse_pytest(output: str) -> dict[str, int]:
    passed = PASSED.search(output)
    failed = FAILED.search(output)
    return {
        "passed": int(passed.group(1)) if passed else 0,
        "failed": int(failed.group(1)) if failed else 0,
    }


def parse_total_coverage(output: str) -> int | None:
    match = TOTAL_COVERAGE.search(output)
    return int(match.group(1)) if match else None


def parse_mypy_files(output: str) -> int | None:
    match = MYPY_FILES.search(output)
    return int(match.group(1)) if match else None


def last_lines(output: str, count: int = 3) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-count:]) if lines else "no output"


def axis(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"name": name, "status": status, "evidence": evidence}


def run_checks(root: Path, run: Runner) -> list[dict[str, str]]:
    axes: list[dict[str, str]] = []
    code, out = run(["uv", "run", "ruff", "check", "."], root)
    axes.append(axis("Lint", "PASS" if code == 0 else "FAIL", last_lines(out, 2)))
    code, out = run(["uv", "run", "mypy", "."], root)
    files = parse_mypy_files(out)
    detail = f"no issues in {files} source files" if code == 0 and files else last_lines(out, 3)
    axes.append(axis("Types", "PASS" if code == 0 else "FAIL", detail))
    code, out = run(["uv", "run", "pytest", "-q"], root)
    counts, total = parse_pytest(out), parse_total_coverage(out)
    detail = f"{counts['passed']} passed, {counts['failed']} failed"
    detail += f", coverage {total}%" if total is not None else ""
    axes.append(axis("Tests", "PASS" if code == 0 else "FAIL", detail))
    axes.append(coverage_axis(root, run, os.environ))
    suites = [str(PLUGIN_ROOT / "hooks" / "tests"), str(PLUGIN_ROOT / "skills")]
    suites += [".claude/skills"] if (root / ".claude" / "skills").is_dir() else []
    code, out = run(
        [*WITHOUT_LOOP, "uv", "run", "pytest", *suites, "-q", "--no-cov", "-p", "no:cacheprovider"],
        root,
    )
    detail = f"{parse_pytest(out)['passed']} passed, {parse_pytest(out)['failed']} failed"
    axes.append(axis("Skill and hook tests", "PASS" if code == 0 else "FAIL", detail))
    return axes


def coverage_axis(root: Path, run: Runner, env: Mapping[str, str]) -> dict[str, str]:
    """The project's coverage gate: FLOW_COVERAGE_INCLUDE files at FLOW_COVERAGE_FAIL_UNDER %."""
    include, minimum = env.get(COVERAGE_INCLUDE, ""), env.get(COVERAGE_FAIL_UNDER, "")
    if not include or not minimum.isdigit():
        missing = f"{COVERAGE_INCLUDE} and {COVERAGE_FAIL_UNDER}"
        return axis("Coverage", "NOT CONFIGURED", f"no coverage gate set ({missing})")
    gate = ["uv", "run", "coverage", "report", f"--include={include}", f"--fail-under={minimum}"]
    code, out = run(gate, root)
    total = parse_total_coverage(out)
    detail = f"{total}% on {include}, gate {minimum}%" if total is not None else last_lines(out)
    return axis("Coverage", "PASS" if code == 0 else "FAIL", detail)


def issue_axis(data: dict[str, Any] | None) -> dict[str, str]:
    if not data or not data.get("criteria"):
        return axis("Issue", "NOT CONFIGURED", "no criteria were given (use --criteria)")
    criteria = data["criteria"]
    failed = [c for c in criteria if c.get("status") == "FAIL"]
    pending = [c for c in criteria if c.get("status") not in ("PASS", "FAIL")]
    status = "FAIL" if failed else "NOT CONFIGURED" if pending else "PASS"
    passed = len([c for c in criteria if c.get("status") == "PASS"])
    return axis("Issue", status, f"{passed} of {len(criteria)} criteria pass")


def test_dirs(root: Path) -> list[Path]:
    """The project's test folders: `checks.protected_test_dirs` of its flow.toml, else all."""
    try:
        data = tomllib.loads(config_file(root).read_text())
        dirs = data["checks"]["protected_test_dirs"]
    except (OSError, ValueError, KeyError, TypeError):
        return [root]
    return [root / str(folder) for folder in dirs if (root / str(folder)).is_dir()]


def query_axis(root: Path) -> dict[str, str]:
    files = [
        f
        for folder in test_dirs(root)
        for f in folder.rglob("test_*.py")
        if not any(part.startswith(".") for part in f.relative_to(root).parts)
    ]
    counts = [len(QUERY_ASSERTION.findall(f.read_text())) for f in files]
    total = sum(counts)
    if total == 0:
        return axis("Query count", "NOT CONFIGURED", "no test asserts a query count")
    holding = len([c for c in counts if c])
    return axis("Query count", "PASS", f"{total} query-count assertions in {holding} test files")


def secret_pattern() -> re.Pattern[str]:
    path = PLUGIN_ROOT / "hooks" / "before-commit-check.py"
    spec = importlib.util.spec_from_file_location("commit_hook", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pattern: re.Pattern[str] = module.SECRET
    return pattern


def security_axis(diff: str) -> dict[str, str]:
    pattern = secret_pattern()
    hits = [
        line
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++") and pattern.search(line)
    ]
    if hits:
        return axis("Security", "FAIL", f"{len(hits)} added line(s) look like a secret (not shown)")
    return axis("Security", "PASS", "no secret-like string in the added lines of the diff")


def browser_script(root: Path | None = None) -> Path:
    """The project's own browser check: .claude/skills/check-in-browser/browser_check.py."""
    project = root or project_root(Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()))
    return project / ".claude" / "skills" / "check-in-browser" / "browser_check.py"


def browser_module() -> Any:
    path = browser_script()
    spec = importlib.util.spec_from_file_location("browser_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def masking_status(browser_masking: dict[str, Any] | None, texts: list[str]) -> dict[str, Any]:
    """clean only when the browser run was clean and no text of the report holds personal data."""
    if browser_masking is None:
        return {"status": "not run"}
    scan = browser_module().scan_text
    kinds = sorted({kind for text in texts for kind in scan(text)})
    findings = list(browser_masking.get("findings", []))
    if kinds:
        findings.append({"step": "report text", "kinds": kinds})
    return {
        "status": "findings" if findings or browser_masking["status"] != "clean" else "clean",
        "findings": findings,
    }


def browser_axis(result_dir: Path | None, code: int | None, output: str) -> dict[str, str]:
    if result_dir is None or code is None:
        return axis("Browser", "NOT CONFIGURED", "not run (add --browser)")
    if code == 2:
        return axis("Browser", "NOT CONFIGURED", last_lines(output, 1))
    data = json.loads((result_dir / "result.json").read_text())
    shots = len([step for step in data["steps"] if step.get("screenshot")])
    detail = (
        f"{len(data['steps'])} step(s), {shots} screenshot{'s' if shots != 1 else ''}, "
        f"console {data['console_errors']} error(s), network {data['network_failures']} failure(s)"
    )
    failed_captures = [
        step["name"]
        for step in data["steps"]
        if any(str(p).startswith("capture:") for p in step.get("problems", []))
    ]
    if failed_captures:
        detail += f"; capture failed in step {', '.join(failed_captures)}"
    leaked = data.get("masking", {}).get("status") == "findings"
    if leaked:
        kinds = sorted({k for f in data["masking"]["findings"] for k in f["kinds"]})
        detail += f"; masking found: {', '.join(kinds)}"
    return axis("Browser", "PASS" if data["status"] == "clean" and not leaked else "FAIL", detail)


def review_axis(text: str | None) -> dict[str, str] | None:
    if not text:
        return None
    first = text.strip().splitlines()[0]
    match = re.match(r"Status:\s*(PASS|FAIL|NOT CONFIGURED)", first)
    status = match.group(1) if match else "NOT CONFIGURED"
    return axis("Review", status, "see the review text below")


def verdict(axes: list[dict[str, str]]) -> str:
    states = {a["status"] for a in axes}
    if "FAIL" in states:
        return "FAIL"
    return "INCOMPLETE" if "NOT CONFIGURED" in states else "PASS"


LIGHT = (
    "--bg:#fff;--fg:#1a1a1a;--muted:#5a5a5a;--line:#d9d9d9;"
    "--pass:#176a2a;--fail:#a61b1b;--warn:#8a5a00;--card:#f6f6f4"
)
DARK = (
    "--bg:#161616;--fg:#ececec;--muted:#a8a8a8;--line:#3a3a3a;"
    "--pass:#58c46f;--fail:#ff7b7b;--warn:#e0b04a;--card:#1f1f1f"
)
CSS = (
    ":root{" + LIGHT + "}"
    '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){' + DARK + "}}"
    ':root[data-theme="dark"]{' + DARK + "}"
    "body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;"
    "margin:0;padding:24px 16px}"
    "main{max-width:980px;margin:0 auto}h1{margin:.2em 0}h2{margin-top:1.6em}"
    ".meta{color:var(--muted)}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}"
    "th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}"
    ".PASS{color:var(--pass);font-weight:700}.FAIL{color:var(--fail);font-weight:700}"
    ".NOT\\ CONFIGURED,.INCOMPLETE{color:var(--warn);font-weight:700}"
    ".NOT\\ APPLICABLE{color:var(--muted);font-weight:700}"
    ".shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}"
    ".shots .pair{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:12px;"
    "align-items:start}"
    ".shots .pair figure+figure img{width:auto;max-width:100%}"
    ".shots figure{margin:0;background:var(--card);padding:8px;border-radius:8px}"
    ".shots img{width:100%;height:auto;border:1px solid var(--line);cursor:zoom-in}"
    "[hidden]{display:none!important}"
    "#lightbox{position:fixed;inset:0;z-index:20;overflow:auto;padding:16px;cursor:zoom-out;"
    "background:rgba(0,0,0,.85)}"
    "#lightbox img{display:block;margin:0 auto;max-width:none;background:var(--bg)}"
    "pre{background:var(--card);padding:12px;overflow:auto;white-space:pre-wrap}"
)


LIGHTBOX = (
    '<div id="lightbox" hidden><img alt=""></div>'
    "<script>(function(){var box=document.getElementById('lightbox');"
    "var big=box.querySelector('img');"
    "document.querySelectorAll('.shots img').forEach(function(img){"
    "img.addEventListener('click',function(){big.src=img.src;big.alt=img.alt;"
    "box.hidden=false;box.scrollTop=0;});});"
    "box.addEventListener('click',function(){box.hidden=true;});"
    "document.addEventListener('keydown',function(e){if(e.key==='Escape'){box.hidden=true;}});"
    "})();</script>"
)


def render_body(report: dict[str, Any]) -> str:
    esc = html.escape
    rows = "".join(
        f'<tr><td>{esc(a["name"])}</td><td class="{esc(a["status"])}">{esc(a["status"])}</td>'
        f"<td>{esc(a['evidence'])}</td></tr>"
        for a in report["axes"]
    )

    def figure(path: str, caption: str) -> str:
        data = base64.b64encode(Path(path).read_bytes()).decode()
        return (
            f'<figure><img alt="{esc(caption)}" src="data:image/png;base64,{data}">'
            f"<figcaption>{esc(caption)}</figcaption></figure>"
        )

    close_ups: dict[str, str] = report.get("close_ups", {})
    shots = ""
    for path in report.get("screenshots", []):
        name = Path(path).stem
        if path in close_ups:
            shots += (
                f'<div class="pair">{figure(path, name)}'
                f"{figure(close_ups[path], f'{name} (close-up)')}</div>"
            )
        else:
            shots += figure(path, name)
    check = "".join(f"<li>{esc(item)}</li>" for item in report.get("check_yourself", []))
    review = f"<h2>Review</h2><pre>{esc(report['review'])}</pre>" if report.get("review") else ""
    return (
        "<main>"
        f"<h1>Verify report: {esc(report['title'])}</h1>"
        f'<p class="meta">Branch {esc(report["branch"])} · commit {esc(report["commit"])} · '
        f"{esc(report['date'])}</p>"
        f'<h2>Result: <span class="{esc(report["verdict"])}">{esc(report["verdict"])}</span></h2>'
        '<div class="table-wrap"><table><thead><tr><th>Axis</th><th>Result</th>'
        "<th>Evidence</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        + (f'<h2>Screenshots</h2><div class="shots">{shots}</div>{LIGHTBOX}' if shots else "")
        + review
        + (f"<h2>What to check yourself</h2><ol>{check}</ol>" if check else "")
        + "</main>"
    )


def render_html(report: dict[str, Any]) -> str:
    """The report as a full page, for opening from the disk."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Verify report</title><style>{CSS}</style></head><body>"
        f"{render_body(report)}</body></html>"
    )


SHARE_GUTTER = (
    "body{padding-block:24px;padding-left:max(16px,env(safe-area-inset-left,0px));"
    "padding-right:max(16px,env(safe-area-inset-right,0px))}"
)


def render_share_html(report: dict[str, Any]) -> str:
    """The report as the content of an artifact page: no html, head or body tags (the platform
    adds them), the title and the style at the top, and the gutter the page contract asks for."""
    return (
        '<meta name="claude:viewport-fit-sides" content="cover">'
        f"<title>Verify report</title><style>{CSS}{SHARE_GUTTER}</style>"
        f"{render_body(report)}"
    )


def git_value(root: Path, run: Runner, *args: str) -> str:
    code, out = run(["git", *args], root)
    return out.strip() if code == 0 and out.strip() else "unknown"


def build(
    root: Path,
    out_dir: Path,
    run: Runner,
    title: str,
    criteria: dict[str, Any] | None,
    review: str | None,
    browser: bool,
    open_report: bool,
    plant: str | None = None,
    spec: Path | None = None,
    no_ui: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    axes = run_checks(root, run)
    axes.append(issue_axis(criteria))
    axes.append(query_axis(root))
    _, diff = run(["git", "diff", "HEAD", "-U0"], root)
    axes.append(security_axis(diff))
    shots: list[str] = []
    close_ups: dict[str, str] = {}
    masking: dict[str, Any] = {"status": "not run"}
    texts = [title, json.dumps(criteria or {}), review or ""]
    if no_ui:
        axes.append(axis("Browser", "NOT APPLICABLE", NO_UI_EVIDENCE))
        masking = masking_status({"status": "clean", "findings": []}, texts)
    elif browser and spec is None:
        axes.append(axis("Browser", "FAIL", NO_SCREENS))
    elif browser:
        script = browser_script(root)
        folder = out_dir / "browser"
        command = [sys.executable, str(script), "--out", str(folder)]
        command += ["--plant", plant] if plant else []
        command += ["--spec", str(spec)]
        code, text = run(command, root)
        axes.append(
            browser_axis(folder if (folder / "result.json").is_file() else None, code, text)
        )
        if (folder / "result.json").is_file():
            result = json.loads((folder / "result.json").read_text())
            shots = [str(folder / s["screenshot"]) for s in result["steps"] if s.get("screenshot")]
            close_ups = {
                str(folder / s["screenshot"]): str(folder / s["element_screenshot"])
                for s in result["steps"]
                if s.get("screenshot") and s.get("element_screenshot")
            }
            masking = masking_status(result["masking"], texts)
    else:
        axes.append(browser_axis(None, None, ""))
    extra = review_axis(review)
    if extra:
        axes.append(extra)
    report: dict[str, Any] = {
        "title": title,
        "verdict": verdict(axes),
        "branch": git_value(root, run, "branch", "--show-current"),
        "commit": git_value(root, run, "rev-parse", "--short", "HEAD"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "axes": axes,
        "screenshots": shots,
        "close_ups": close_ups,
        "review": review or "",
        "masking": masking,
        "share": None,
        "check_yourself": (criteria or {}).get("check_yourself", []),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    page = out_dir / "report.html"
    page.write_text(render_html(report))
    (out_dir / "report-share.html").write_text(render_share_html(report))
    if open_report:
        webbrowser.open(page.as_uri())
    return report


def config_file(root: Path) -> Path:
    """.flow/flow.toml when it exists (the new layout), else ops/flow.toml."""
    new = root / ".flow" / "flow.toml"
    return new if new.is_file() else root / "ops" / "flow.toml"


def project_root(start: Path) -> Path:
    for folder in (start, *start.parents):
        if config_file(folder).is_file():
            return folder
    return start


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the verify report.")
    parser.add_argument("--title", required=True, help="the issue, as a short title")
    parser.add_argument("--criteria", type=Path, help="JSON: criteria with status, check_yourself")
    parser.add_argument("--review", type=Path, help="text file; first line Status: PASS or FAIL")
    screens = parser.add_mutually_exclusive_group()
    screens.add_argument(
        "--browser", action="store_true", help="run the browser check on the --spec screens"
    )
    screens.add_argument(
        "--no-ui", action="store_true", help="the task changes no screen: no browser, no shots"
    )
    parser.add_argument(
        "--spec", type=Path, help='JSON steps from the issue\'s "Screens to capture"'
    )
    parser.add_argument("--no-open", action="store_true", help="do not open the report")
    parser.add_argument("--plant", help="add a review with this text, to test the scan only")
    parser.add_argument("--out", type=Path, help="folder (default: out/verify/<time>)")
    args = parser.parse_args(argv)
    root = project_root(Path.cwd())
    out_dir = args.out or root / "out" / "verify" / datetime.now().strftime("%Y%m%d-%H%M%S")
    criteria = json.loads(args.criteria.read_text()) if args.criteria else None
    review = args.review.read_text() if args.review else None
    report = build(
        root,
        out_dir,
        real_run,
        args.title,
        criteria,
        review,
        args.browser,
        not args.no_open,
        args.plant,
        args.spec,
        no_ui=args.no_ui,
    )
    for item in report["axes"]:
        print(f"{item['status']:<15} {item['name']:<22} {item['evidence']}")
    print(f"result: {report['verdict']}   report: {out_dir / 'report.html'}")
    return {"PASS": 0, "FAIL": 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
