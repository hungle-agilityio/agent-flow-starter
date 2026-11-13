"""One uptime probe of the live site, run by the loop after each tick.

Usage: uv run python ops/uptime.py

Spec: specs/post-release/spec.md (AC16 to AC18). It sends one GET to `/healthz/` of `live.url`.
After two failures in a row it sends one message that the site is down, and one more when the
site answers again. The state is in `uptime.json` in the loop's state folder. It always exits 0,
so the loop goes on. Standard library only.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from ops import flow_config, live_check
except ImportError:  # run as a script: python3 ops/uptime.py
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]
    import live_check  # type: ignore[import-not-found,no-redef,unused-ignore]

STATE_NAME = "uptime.json"
HEALTH_PATH = "/healthz/"
REQUEST_TIMEOUT = 60.0
ALERT_AFTER = 2
UP_BODY = "ok"
TIMED_OUT = "timeout after 60s"
NO_CONNECTION = "no connection"
VIETNAM_ZONE = "Asia/Ho_Chi_Minh"
TOPIC_VAR = "NTFY_TOPIC"
SLACK_VAR = "SLACK_WEBHOOK_URL"


@dataclass(frozen=True)
class Reply:
    """One answer of the health page; `problem` is set when there was no answer."""

    status: int | None
    body: str
    problem: str = ""


@dataclass(frozen=True)
class State:
    """What the last probes found; `down_since` is the ISO time of the first failure."""

    failures: int = 0
    down_since: str | None = None
    alerted: bool = False


Fetch = Callable[[str, float], Reply]
Now = Callable[[], datetime]
Send = Callable[[str, str], None]


def fetch(url: str, timeout: float) -> Reply:
    """One GET; a timeout and a failed connection are told apart."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return Reply(response.status, response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        return Reply(error.code, "")
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, TimeoutError | socket.timeout)
        return Reply(None, "", TIMED_OUT if timed_out else NO_CONNECTION)
    except TimeoutError:
        return Reply(None, "", TIMED_OUT)
    except (OSError, ValueError):
        return Reply(None, "", NO_CONNECTION)


def utc_now() -> datetime:
    return datetime.now(UTC)


def failure_reason(reply: Reply) -> str | None:
    """None when the site is up: a 200 answer with the body `ok`."""
    if reply.status is None:
        return reply.problem or NO_CONNECTION
    if reply.status == 200 and reply.body == UP_BODY:
        return None
    return f"HTTP {reply.status}"


def read_state(path: Path) -> State:
    """A missing or unreadable file counts as no failure so far."""
    try:
        data = json.loads(path.read_text())
        since = data["down_since"]
        if since is not None:
            datetime.fromisoformat(since)
        return State(int(data["failures"]), since, bool(data["alerted"]))
    except (OSError, ValueError, KeyError, TypeError):
        return State()


def write_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "failures": state.failures,
        "down_since": state.down_since,
        "alerted": state.alerted,
    }
    path.write_text(json.dumps(data) + "\n")


def zone_label(zone: str) -> str:
    return "Vietnam time" if zone == VIETNAM_ZONE else zone


def down_message(config: flow_config.FlowConfig, since: datetime, reason: str) -> str:
    zone = config.release_timezone
    clock = since.astimezone(ZoneInfo(zone)).strftime("%H:%M")
    name = config.project_display_name
    return f"{name} site is down since {clock} ({zone_label(zone)}): {reason}"


def back_message(config: flow_config.FlowConfig, since: datetime, now: datetime) -> str:
    """Whole minutes since the first failure, rounded down, at least 1."""
    minutes = max(1, int((now - since).total_seconds() // 60))
    return f"{config.project_display_name} site is back after {minutes} minutes"


def next_state(
    config: flow_config.FlowConfig, state: State, reason: str | None, now: datetime
) -> tuple[State, tuple[str, str] | None]:
    """The state after this probe, and the message to send with its priority, if any."""
    if reason is None:
        if state.alerted and state.down_since is not None:
            since = datetime.fromisoformat(state.down_since)
            return State(), (back_message(config, since, now), "low")
        return State(), None
    failures = state.failures + 1
    since_text = state.down_since or now.isoformat()
    if failures >= ALERT_AFTER and not state.alerted:
        message = down_message(config, datetime.fromisoformat(since_text), reason)
        return State(failures, since_text, True), (message, "high")
    return State(failures, since_text, state.alerted), None


def settings_sender(config: flow_config.FlowConfig, environ: Mapping[str, str]) -> Send:
    """ntfy when NTFY_TOPIC is set, Slack when SLACK_WEBHOOK_URL is set, with the tick's senders."""
    settings = live_check.load_settings(config, environ)
    topic, slack = settings.get(TOPIC_VAR, ""), settings.get(SLACK_VAR, "")

    def send(message: str, priority: str) -> None:
        if not topic and not slack:
            return
        try:
            from ops import agent_tick
        except ImportError:  # run as a script
            import agent_tick  # type: ignore[import-not-found,no-redef,unused-ignore]
        host: Any = agent_tick.RealHost()
        if topic:
            host.notify_priority(topic, message, priority)
        if slack:
            host.slack(slack, message)

    return send


def probe(
    config: flow_config.FlowConfig,
    environ: Mapping[str, str],
    fetch: Fetch,
    now: Now,
    send: Send,
) -> None:
    """One probe: read the state, ask the site, send at most one message, write the state."""
    if config.live is None:
        return
    path = live_check.state_folder(config, environ) / STATE_NAME
    reason = failure_reason(fetch(config.live.url + HEALTH_PATH, REQUEST_TIMEOUT))
    state, message = next_state(config, read_state(path), reason, now())
    if message is not None:
        try:
            send(*message)
        except Exception:  # a message that cannot be sent never stops the loop
            pass
    write_state(path, state)


def main(
    argv: list[str] | None = None,
    *,
    fetch: Fetch = fetch,
    now: Now = utc_now,
    send: Send | None = None,
    environ: Mapping[str, str] = os.environ,
    config_path: Path | None = None,
) -> int:
    try:
        config = flow_config.load(config_path)
        sender = send if send is not None else settings_sender(config, environ)
        probe(config, environ, fetch, now, sender)
    except Exception as error:  # the loop line must go on whatever happens here
        print(f"uptime: {type(error).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
