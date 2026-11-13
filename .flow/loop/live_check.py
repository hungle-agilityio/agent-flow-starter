"""Check the live site after a release: the released commit, the main screens, the headers.

Usage: uv run python ops/live_check.py [--commit <commit>]

Spec: specs/post-release/spec.md (AC3 to AC10). It waits until `/healthz/` of `live.url` reports
the commit (default: origin/deploy), signs in as `live.username` with LIVE_CHECK_PASSWORD, opens
every step of ops/regression_screens.json in headless Chromium with its load time, then checks
the security headers and redirects. One line per check; the last line is `result: pass` (exit 0)
or `result: fail` (exit 1). Exit 2: the check could not run. Standard library plus Playwright.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from ops import flow_config
except ImportError:  # run as a script: python3 ops/live_check.py
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]

LOOP_DIR = Path(__file__).resolve().parent
REPO_ENV = LOOP_DIR / "agent.env"
SPEC_PATH = LOOP_DIR / "regression_screens.json"
HOME_VAR = "FLOW_HOME"
PASSWORD_VAR = "LIVE_CHECK_PASSWORD"
REQUEST_TIMEOUT = 60.0
POLL_PAUSE = 20.0
LOGIN_PATH = "/login/"
GOTO_MS = 15000
ACTION_MS = 5000
NAVIGATION_MS = 8000
TENTH = Decimal("0.1")
HSTS = "max-age=31536000"


@dataclass(frozen=True)
class Answer:
    """One HTTP answer; status is None on a timeout or a connection error."""

    status: int | None
    headers: dict[str, str]


Fetch = Callable[[str, float], Answer]
Clock = Callable[[], float]


class CheckError(Exception):
    """The check cannot start; the message is its one line on stderr."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url: str, timeout: float) -> Answer:
    """One GET that follows no redirect; a timeout or a connection error has no status."""
    try:
        with _OPENER.open(url, timeout=timeout) as response:
            return Answer(response.status, _lower(response.headers.items()))
    except urllib.error.HTTPError as error:
        return Answer(error.code, _lower(error.headers.items()))
    except (OSError, ValueError, http.client.HTTPException):
        return Answer(None, {})


def _lower(items: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in items}


def state_folder(config: flow_config.FlowConfig, environ: Mapping[str, str]) -> Path:
    """FLOW_HOME when it is set and not empty, else `loop.state_dir` of the flow config."""
    named = environ.get(HOME_VAR, "")
    return Path(named).expanduser() if named else config.loop_state_dir


def load_settings(config: flow_config.FlowConfig, environ: Mapping[str, str]) -> dict[str, str]:
    """The tick's settings file, then every non-empty variable of the environment over it."""
    path = REPO_ENV if REPO_ENV.is_file() else state_folder(config, environ) / "agent.env"
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
    values.update({key: value for key, value in environ.items() if value})
    return values


def wait_until_live(
    live: flow_config.LiveConfig,
    commit: str,
    fetch: Fetch,
    clock: Clock,
    sleep: Callable[[float], None],
) -> tuple[bool, list[str]]:
    """Poll /healthz/ until it answers 200 with X-Commit equal to the commit, or time runs out."""
    start = clock()
    last_seen = ""
    first = True
    while first or clock() - start < live.wait_minutes * 60:
        first = False
        answer = fetch(f"{live.url}/healthz/", REQUEST_TIMEOUT)
        seen = answer.headers.get("x-commit", "")
        last_seen = seen or last_seen
        if answer.status == 200 and seen == commit:
            minutes, seconds = divmod(int(clock() - start), 60)
            return True, [f"live: {commit[:7]} after {minutes}m{seconds:02d}s"]
        sleep(POLL_PAUSE)
    shown = last_seen[:7] or "none"
    return False, [
        f"FAIL wait: {commit[:7]} is not live after {live.wait_minutes} minutes (live: {shown})"
    ]


def _path_of(url: str) -> str:
    return urlsplit(url).path


def sign_in(page: Any, live: flow_config.LiveConfig, password: str) -> str | None:
    """Sign in through the real sign-in page; the FAIL line, or None when signed in."""
    failure = f"FAIL sign-in: could not sign in as {live.username}"
    try:
        page.goto(live.url + LOGIN_PATH, wait_until="load", timeout=GOTO_MS)
        page.fill("#id_username", live.username, timeout=ACTION_MS)
        page.fill("#id_password", password, timeout=ACTION_MS)
        with page.expect_navigation(wait_until="load", timeout=NAVIGATION_MS):
            page.click("button[type=submit]", timeout=ACTION_MS)
        if _path_of(page.url).startswith(LOGIN_PATH):
            return failure
    except Exception:  # any Playwright error or timeout is a failed sign-in
        return failure
    return None


def load_steps(path: Path) -> list[dict[str, Any]]:
    """The steps of a spec: a list, or an object with "steps"; each step has a name."""
    data = json.loads(path.read_text())
    steps = data["steps"] if isinstance(data, dict) else data
    if not isinstance(steps, list) or not all(
        isinstance(step, dict) and "name" in step for step in steps
    ):
        raise ValueError(f"{path}: the spec must be a list of steps, each with a name")
    return list(steps)


def seconds_shown(elapsed: float) -> Decimal:
    """A load time to one decimal, rounded half up (never round())."""
    return Decimal(str(elapsed)).quantize(TENTH, rounding=ROUND_HALF_UP)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _first_line(error: BaseException) -> str:
    lines = str(error).strip().splitlines()
    return lines[0] if lines else type(error).__name__


def _is_favicon(url: str) -> bool:
    return url.endswith("favicon.ico")


class _Watch:
    """Console errors and failed requests of the current step, counted as browser_check does."""

    def __init__(self, page: Any) -> None:
        self.errors = 0
        self.failures = 0
        page.on("console", self._console)
        page.on("pageerror", self._page_error)
        page.on("response", self._response)
        page.on("requestfailed", self._request_failed)

    def reset(self) -> None:
        self.errors = 0
        self.failures = 0

    def _console(self, message: Any) -> None:
        location = getattr(message, "location", None) or {}
        if message.type == "error" and not _is_favicon(str(location.get("url", ""))):
            self.errors += 1

    def _page_error(self, _error: Any) -> None:
        self.errors += 1

    def _response(self, response: Any) -> None:
        if response.status >= 400 and not _is_favicon(response.url):
            self.failures += 1

    def _request_failed(self, _request: Any) -> None:
        self.failures += 1


def _run_actions(page: Any, step: dict[str, Any]) -> None:
    for action in step.get("actions", []):
        if "select" in action:
            for selector, value in action["select"].items():
                page.select_option(selector, value, timeout=ACTION_MS)
        if "fill" in action:
            for selector, value in action["fill"].items():
                page.fill(selector, value, timeout=ACTION_MS)
        if "click" in action:
            with page.expect_navigation(wait_until="load", timeout=NAVIGATION_MS):
                page.click(action["click"], timeout=ACTION_MS)


def _open_step(page: Any, live: flow_config.LiveConfig, step: dict[str, Any]) -> str | None:
    """Goto and actions of one step; the first reason it failed, or None."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    try:
        if "goto" in step:
            response = page.goto(live.url + step["goto"], wait_until="load", timeout=GOTO_MS)
            if response is None:
                return "error: no response"
            if not 200 <= response.status < 300:
                return f"HTTP {response.status}"
        _run_actions(page, step)
    except PlaywrightTimeout:
        return "timeout"
    except Exception as error:  # a failed step is reported, never a crash of the run
        return f"error: {_first_line(error)}"
    return None


def _missing_text(page: Any, step: dict[str, Any]) -> str | None:
    try:
        text = page.inner_text("body")
    except Exception as error:
        return f"error: {_first_line(error)}"
    for expected in step.get("expect", []):
        if expected not in text:
            return f'missing text "{expected}"'
    return None


def check_steps(
    page: Any, live: flow_config.LiveConfig, steps: list[dict[str, Any]], clock: Clock
) -> list[str]:
    """One line per step: PASS or SLOW with its load time, or FAIL with the first reason."""
    watch = _Watch(page)
    lines: list[str] = []
    for step in steps:
        name = step["name"]
        watch.reset()
        start = clock()
        reason = _open_step(page, live, step)
        elapsed = clock() - start
        reason = reason or _missing_text(page, step)
        if reason is None and watch.errors:
            reason = _plural(watch.errors, "console error")
        if reason is None and watch.failures:
            reason = _plural(watch.failures, "failed request")
        shown = seconds_shown(elapsed)
        if reason is not None:
            lines.append(f"FAIL {name}: {reason}")
        elif shown > live.load_warn_seconds:
            lines.append(f"SLOW {name} {shown}s (over {live.load_warn_seconds}s)")
        else:
            lines.append(f"PASS {name} {shown}s")
    return lines


def _redirect_reason(answer: Answer, status: int, prefix: str) -> str | None:
    if answer.status is None:
        return "got no answer"
    if answer.status != status:
        return f"got {answer.status}"
    location = answer.headers.get("location")
    if location is None:
        return "Location none"
    if not location.startswith(prefix):
        return f"Location {location}"
    return None


def _header_reason(answer: Answer, name: str, expected: str) -> str | None:
    if answer.status is None:
        return "got no answer"
    value = answer.headers.get(name)
    return None if value == expected else f"got {value if value is not None else 'none'}"


def check_security(live: flow_config.LiveConfig, fetch: Fetch) -> list[str]:
    """The five checks of the security-check epic, with plain requests that follow no redirect."""
    plain = f"http://{urlsplit(live.url).netloc}/dashboard/"
    login = fetch(f"{live.url}{LOGIN_PATH}", REQUEST_TIMEOUT)
    redirect = fetch(plain, REQUEST_TIMEOUT)
    dashboard = fetch(f"{live.url}/dashboard/", REQUEST_TIMEOUT)
    health = fetch(f"{live.url}/healthz/", REQUEST_TIMEOUT)
    if health.status is None:
        health_reason: str | None = "got no answer"
    else:
        health_reason = None if health.status == 200 else f"got {health.status}"
    results = [
        ("https-redirect", _redirect_reason(redirect, 301, "https://")),
        ("frame-options", _header_reason(login, "x-frame-options", "DENY")),
        ("hsts", _header_reason(login, "strict-transport-security", HSTS)),
        ("login-required", _redirect_reason(dashboard, 302, LOGIN_PATH)),
        ("healthz", health_reason),
    ]
    return [
        f"PASS {name}" if reason is None else f"FAIL {name}: {reason}" for name, reason in results
    ]


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments],
        cwd=flow_config.PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        lines = done.stderr.strip().splitlines()
        raise CheckError(f"git {' '.join(arguments)} failed: {lines[0] if lines else ''}")
    return done.stdout.strip()


def resolve_commit(commit: str | None) -> str:
    """The full commit of --commit (no fetch), else of origin/deploy after `git fetch origin`."""
    if commit is not None:
        try:
            return _git("rev-parse", "--verify", f"{commit}^{{commit}}")
        except CheckError:
            raise CheckError(f"unknown commit {commit}") from None
    _git("fetch", "origin")
    return _git("rev-parse", "origin/deploy")


def _prepare(
    commit: str | None, environ: Mapping[str, str], config_path: Path | None
) -> tuple[flow_config.LiveConfig, str, str]:
    """The live config, the password and the full commit; CheckError when one is missing."""
    try:
        config = flow_config.load(config_path)
    except flow_config.FlowConfigError as error:
        raise CheckError(str(error)) from error
    if config.live is None:
        raise CheckError("no [live] table in flow.toml")
    password = load_settings(config, environ).get(PASSWORD_VAR, "")
    if not password:
        raise CheckError(f"{PASSWORD_VAR} is not set in agent.env")
    return config.live, password, resolve_commit(commit)


def _browse(
    live: flow_config.LiveConfig, password: str, steps: list[dict[str, Any]], clock: Clock
) -> tuple[bool, list[str]]:
    """Signed in or not, and the lines; CheckError when Chromium cannot start."""
    from playwright.sync_api import sync_playwright

    try:
        playwright = sync_playwright().start()
    except Exception as error:
        raise CheckError(f"could not run: {_first_line(error)}") from error
    try:
        try:
            browser = playwright.chromium.launch()
            page = browser.new_page()
        except Exception as error:
            raise CheckError(f"could not run: {_first_line(error)}") from error
        try:
            failure = sign_in(page, live, password)
            if failure:
                return False, [failure]
            return True, check_steps(page, live, steps, clock)
        finally:
            browser.close()
    finally:
        playwright.stop()


def _read_steps(path: Path) -> list[dict[str, Any]]:
    """The steps, read before any request so a broken spec never waits for the deploy first."""
    try:
        return load_steps(path)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CheckError(f"could not read {path}: {_first_line(error)}") from error


def _result(lines: list[str]) -> tuple[str, int]:
    if any(line.startswith("FAIL") for line in lines):
        return "result: fail", 1
    slow = sum(line.startswith("SLOW") for line in lines)
    return ("result: pass" if not slow else f"result: pass, {slow} slow"), 0


def main(
    argv: list[str] | None = None,
    *,
    fetch: Fetch = fetch,
    clock: Clock = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    environ: Mapping[str, str] = os.environ,
    spec_path: Path = SPEC_PATH,
    config_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Check the live site after a release.")
    parser.add_argument("--commit", help="the released commit (default: origin/deploy)")
    args = parser.parse_args(argv)
    try:
        live, password, commit = _prepare(args.commit, environ, config_path)
        steps = _read_steps(spec_path)
    except CheckError as error:
        print(error, file=sys.stderr)
        return 2
    is_live, lines = wait_until_live(live, commit, fetch, clock, sleep)
    for line in lines:
        print(line)
    if not is_live:
        print("result: fail")
        return 1
    try:
        signed_in, screens = _browse(live, password, steps, clock)
    except CheckError as error:
        print(error, file=sys.stderr)
        return 2
    lines += screens
    for line in screens:
        print(line)
    if signed_in:
        security = check_security(live, fetch)
        lines += security
        for line in security:
            print(line)
    result, code = _result(lines)
    print(result)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
