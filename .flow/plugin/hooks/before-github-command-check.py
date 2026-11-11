#!/usr/bin/env python3
"""Before every Bash call: refuse gh, git and curl commands that reach a GitHub repository
other than the allowed one, or that manage repositories, accounts or secrets.

The call arrives as JSON on stdin. Exit code 2 blocks it and sends stderr back to Claude.
The allowed repository is `project.repo` of the project's ops/flow.toml (owner/name); the
project is CLAUDE_PROJECT_DIR, else the cwd of the call.
If anything goes wrong while checking a command that looks relevant, the command is blocked.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping
from importlib import util
from pathlib import Path
from typing import Any

GH_TOP_LEVEL = {
    "issue",
    "pr",
    "label",
    "run",
    "workflow",
    "release",
    "repo",
    "api",
    "auth",
    "version",
    "help",
}
GIT_NETWORK = {"push", "pull", "fetch", "ls-remote"}

ADMIN_GH = re.compile(
    r"\bgh\s+(?:repo\s+(?:create|delete|edit|rename|archive|unarchive|fork|transfer|clone|sync"
    r"|list|deploy-key)"
    r"|auth\s+(?:login|logout|refresh|token|switch|setup-git)"
    r"|gist|ssh-key|gpg-key|org|secret|variable|codespace|extension|alias|search)\b"
)
RELEVANT = re.compile(r"\bgh\b|\bgit\b|github|\bcurl\b|\bwget\b|\bssh\b|\bscp\b|\bsftp\b|\brsync\b")
QUOTED_HEREDOC = re.compile(r"<<-?\s*'(\w+)'[^\n]*\n.*?\n\s*\1[ \t]*(?:\n|$)", re.S)
SHELL_WORD = re.compile(r"\b(?:bash|sh|zsh|dash|ksh|eval|source)\b")
CONFIG_READ_FLAGS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l"}
REMOTE_KEY = re.compile(r"\bremote\.[^\s]+\.(?:url|pushurl)\b|\burl\.")
TOKEN_USE = re.compile(
    r"\b(?:GH_TOKEN|GITHUB_TOKEN|GITHUB_PERSONAL_ACCESS_TOKEN)\b"
    r"|(?:^|[;&|\n]\s*)(?:printenv|env)\s*(?:$|[;&|\n])"
)
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
ENV_PREFIX = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
GH_SEGMENT = re.compile(rf"^{ENV_PREFIX}(?:sudo\s+)?gh\b\s*(.*)$", re.S)
GIT_SEGMENT = re.compile(rf"^{ENV_PREFIX}git\b\s*(.*)$", re.S)
FETCH_SEGMENT = re.compile(rf"^{ENV_PREFIX}(?:curl|wget)\b")
SSH_SEGMENT = re.compile(rf"^{ENV_PREFIX}(?:ssh|scp|sftp|rsync)\b")
REPO_IN_URL = re.compile(r"(?<![\w.-])github\.com[/:]+([\w.-]+)/([\w.-]+)")
REPO_IN_API = re.compile(r"(?:^|[\s'\"/])repos/([\w.-]+)/([\w.-]+)")
API_HOST_PATH = re.compile(r"api\.github\.com(/[^\s'\"]*)")
GH_REPO_ENV = re.compile(r"\bGH_REPO=['\"]?([^\s'\"]+)")
REPO_FLAG = re.compile(r"(?:^|\s)(?:-R|--repo)(?:=|\s+)['\"]?([^\s'\"]+)")
LEADING_WORDS = re.compile(r"\s*([A-Za-z][\w-]*)(?:\s+([A-Za-z][\w-]*))?")
GH_UNSPLIT_OK = {"issue", "pr", "label"}
GIT_REMOTE_SUBS = GIT_NETWORK | {"clone", "remote", "config"}


def split_segments(command: str) -> list[str]:
    """Split on &&, ||, ; and | outside quotes; several lines or an unclosed quote split on all."""
    if "\n" in command:
        return SEGMENT_SPLIT.split(command)
    parts: list[str] = []
    current = ""
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(command):
                current += command[index : index + 2]
                index += 2
                continue
            if char == quote:
                quote = ""
            current += char
        elif char == "\\" and index + 1 < len(command):
            current += command[index : index + 2]
            index += 2
            continue
        elif char in "'\"":
            quote = char
            current += char
        elif command.startswith(("&&", "||"), index):
            parts.append(current)
            current = ""
            index += 2
            continue
        elif char in ";|":
            parts.append(current)
            current = ""
        else:
            current += char
        index += 1
    if quote:
        return SEGMENT_SPLIT.split(command)
    parts.append(current)
    return parts


def normalise(owner: str, name: str) -> str:
    """Return owner/name in lower case without a .git suffix."""
    if name.endswith(".git"):
        name = name[:-4]
    return f"{owner}/{name}".lower()


def repo_from_value(value: str) -> str:
    """Turn a -R value (owner/name, host/owner/name or a URL) into owner/name."""
    parts = [part for part in value.strip("/").split("/") if part]
    if len(parts) >= 2:
        return normalise(parts[-2], parts[-1])
    return value.lower()


def url_like(token: str) -> bool:
    return "://" in token or re.match(r"^[\w.-]+@[\w.-]+:", token) is not None


def repo_of_url(token: str) -> str | None:
    match = REPO_IN_URL.search(token)
    return normalise(match.group(1), match.group(2)) if match else None


def foreign_in_text(text: str, allowed: str) -> list[str]:
    """Repositories named by URL or API path in text that are not the allowed one."""
    found = [normalise(o, n) for o, n in REPO_IN_URL.findall(text) + REPO_IN_API.findall(text)]
    return [f"it reaches {name}" for name in found if name != allowed]


def foreign_urls(urls: list[str], allowed: str) -> list[str]:
    return [f"it reaches {repo_of_url(u) or u}" for u in urls if repo_of_url(u) != allowed]


def leading_words(rest: str) -> list[str]:
    """The first one or two plain words of a command, before any option."""
    match = LEADING_WORDS.match(rest)
    return [word for word in match.groups() if word] if match else []


def check_gh_unsplit(rest: str, allowed: str) -> list[str]:
    """A body with an apostrophe or several lines cannot be split: scan the raw text instead."""
    problems = [
        f"it targets {repo_from_value(value)}"
        for value in REPO_FLAG.findall(rest)
        if repo_from_value(value) != allowed
    ]
    words = leading_words(rest)
    if not words or words[0] not in GH_UNSPLIT_OK:
        problems.append("the gh command could not be read safely")
    problems.extend(foreign_in_text(rest, allowed))
    return problems


def check_gh(rest: str, allowed: str, loop: bool = False) -> list[str]:
    try:
        tokens = shlex.split(rest)
    except ValueError:
        return check_gh_unsplit(rest, allowed)
    problems: list[str] = []
    for index, token in enumerate(tokens):
        value = ""
        if token in ("-R", "--repo") and index + 1 < len(tokens):
            value = tokens[index + 1]
        elif token.startswith("--repo="):
            value = token.split("=", 1)[1]
        if value and repo_from_value(value) != allowed:
            problems.append(f"it targets {repo_from_value(value)}")
    positional = [token for token in tokens if not token.startswith("-")]
    if not positional:
        return problems
    top = positional[0]
    if top not in GH_TOP_LEVEL:
        problems.append(f"gh {top} is not allowed here")
    elif top == "auth" and (len(positional) < 2 or positional[1] != "status"):
        problems.append("only gh auth status is allowed")
    elif top == "repo":
        if len(positional) < 2 or positional[1] != "view":
            problems.append("only gh repo view is allowed")
        elif len(positional) > 2 and repo_from_value(positional[2]) != allowed:
            problems.append(f"it targets {repo_from_value(positional[2])}")
    elif top == "api":
        problems.extend(check_api(tokens, positional, allowed, loop))
    problems.extend(foreign_in_text(rest, allowed))
    return problems


API_VALUE_FLAGS = {"-X", "--method", "-f", "-F", "--field", "--raw-field"}
API_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field"}
API_PLAIN_FLAGS = {"--silent"}
MARK_REACTIONS = {"eyes", "rocket", "confused"}
RESOLVE_THREAD = re.compile(
    r"mutation\w*(?:\([^)]*\))?\{resolveReviewThread\(input:\{threadId:"
    r"(?:\"[\w-]+\"|\$\w+)\}\)\{thread\{[\w{}]*\}\}\}"
)


def thread_query(allowed: str) -> re.Pattern[str]:
    """The one GraphQL read the loop may make: the review threads of a pull request here."""
    owner, name = (re.escape(part) for part in allowed.split("/", 1))
    return re.compile(
        rf"query\w*(?:\([^)]*\))?\{{repository\(owner:\"{owner}\",name:\"{name}\"\)"
        r"\{pullRequest\(number:(?:\d+|\$\w+)\)\{reviewThreads\(first:\d+\)"
        r"\{nodes\{[\w{}():,]*\}\}\}\}\}",
        re.I,
    )


def api_parts(tokens: list[str]) -> tuple[str, str, dict[str, str]] | None:
    """Method, path and fields of a gh api call; None when it uses any other option."""
    method = ""
    path = ""
    fields: dict[str, str] = {}
    args = tokens[tokens.index("api") + 1 :] if "api" in tokens else []
    index = 0
    while index < len(args):
        token = args[index]
        name, eq, inline = token.partition("=")
        if token.startswith("-") and name in API_VALUE_FLAGS:
            if eq:
                value = inline
            elif index + 1 < len(args):
                value = args[index + 1]
                index += 1
            else:
                return None
            if name in API_FIELD_FLAGS:
                key, sep, field = value.partition("=")
                if not sep:
                    return None
                fields[key] = field
            else:
                method = value.upper()
        elif token in API_PLAIN_FLAGS:
            pass
        elif not token.startswith("-") and not path:
            path = token.lstrip("/").lower()
        else:
            return None
        index += 1
    return (method or ("POST" if fields else "GET")), path, fields


API_FLAGS_WITH_VALUE = API_VALUE_FLAGS | {
    "-H",
    "--header",
    "-q",
    "--jq",
    "-t",
    "--template",
    "--input",
    "--hostname",
    "-p",
    "--preview",
    "--cache",
}


def api_path(tokens: list[str]) -> str:
    """The endpoint of a gh api call, skipping the values of its options (-X POST, -f a=b)."""
    args = tokens[tokens.index("api") + 1 :] if "api" in tokens else []
    index = 0
    while index < len(args):
        token = args[index]
        if token in API_FLAGS_WITH_VALUE:
            index += 2
            continue
        if not token.startswith("-"):
            return token.lstrip("/").lower()
        index += 1
    return ""


def mark_path(path: str, allowed: str) -> str:
    """'reaction', 'reply' or 'resolve' when a gh api path is one the loop's review marks use."""
    base = f"repos/{allowed}/"
    if re.fullmatch(rf"{re.escape(base)}(?:issues|pulls)/comments/\d+/reactions", path):
        return "reaction"
    if re.fullmatch(rf"{re.escape(base)}pulls/\d+/comments/\d+/replies", path):
        return "reply"
    return "resolve" if path == "graphql" else ""


def review_mark_call(tokens: list[str], allowed: str) -> str:
    """The kind of an exact review-mark call (reaction, reply, resolve, threads), or ''."""
    parts = api_parts(tokens)
    if parts is None:
        return ""
    method, path, fields = parts
    kind = mark_path(path, allowed)
    if method != "POST" or not kind:
        return ""
    if kind == "reaction":
        ok = set(fields) == {"content"} and fields["content"] in MARK_REACTIONS
    elif kind == "reply":
        ok = set(fields) == {"body"}
    else:
        query = re.sub(r"\s+", "", fields.get("query", ""))
        if thread_query(allowed).fullmatch(query) and not set(fields) - {"query", "number"}:
            return "threads"
        extra = set(fields) - {"query", "threadId"}
        ok = not extra and RESOLVE_THREAD.fullmatch(query) is not None
    return kind if ok else ""


def check_api(
    tokens: list[str], positional: list[str], allowed: str, loop: bool = False
) -> list[str]:
    problems: list[str] = []
    for index, token in enumerate(tokens):
        method = ""
        if token in ("-X", "--method") and index + 1 < len(tokens):
            method = tokens[index + 1]
        elif token.startswith("--method="):
            method = token.split("=", 1)[1]
        if method.upper() == "DELETE":
            problems.append("gh api with DELETE is not allowed")
    path = api_path(tokens)
    if not path:
        return problems
    if path == "graphql" and loop and review_mark_call(tokens, allowed) in ("resolve", "threads"):
        return problems
    if not (path.startswith(f"repos/{allowed}") or path in ("user", "rate_limit")):
        problems.append(f"gh api path {path} is outside {allowed}")
    return problems


def check_git(rest: str, allowed: str) -> list[str]:
    try:
        tokens = shlex.split(rest)
    except ValueError:
        words = leading_words(rest)
        if words and words[0] not in GIT_REMOTE_SUBS:
            return []
        if words or re.search(r"\b(push|pull|fetch|clone|ls-remote|remote)\b", rest):
            return foreign_in_text(rest, allowed) or ["the git command could not be read safely"]
        return []
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in ("-C", "-c", "--git-dir", "--work-tree") else 1
    if index >= len(tokens):
        return []
    sub, args = tokens[index], tokens[index + 1 :]
    positional = [arg for arg in args if not arg.startswith("-")]
    problems: list[str] = []
    if sub == "config":
        reading = any(arg in CONFIG_READ_FLAGS for arg in args)
        if not reading and (REMOTE_KEY.search(rest.lower()) or "insteadof" in rest.lower()):
            problems.append("changing remote URLs with git config is not allowed")
    elif sub in GIT_NETWORK:
        if positional:
            first = positional[0]
            target = repo_of_url(first) if url_like(first) else first
            if target not in ("origin", allowed):
                problems.append(f"git {sub} must use origin or {allowed}, not {first}")
    elif sub == "clone":
        urls = [arg for arg in positional if url_like(arg)]
        problems.extend(foreign_urls(urls, allowed))
    elif sub == "remote" and positional and positional[0] in ("add", "set-url"):
        urls = [arg for arg in positional[1:] if url_like(arg)]
        if not urls:
            problems.append(f"the remote URL must be a github.com URL of {allowed}")
        problems.extend(foreign_urls(urls, allowed))
    return problems


def check_ssh(text: str) -> list[str]:
    """Direct ssh, scp, sftp or rsync to github.com is only allowed as the ssh -T test."""
    if "github" not in text.lower():
        return []
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = []
    if tokens and tokens[0] == "ssh" and "-T" in tokens and tokens[-1].lower() == "git@github.com":
        return []
    return ["direct ssh to github.com is only allowed as the ssh -T connection test"]


def without_inert_heredocs(command: str) -> str:
    """Drop heredoc bodies with a quoted delimiter, unless a shell would run them."""

    def drop(match: re.Match[str]) -> str:
        line_start = command.rfind("\n", 0, match.start()) + 1
        head = command[line_start : match.start()] + match.group(0).split("\n", 1)[0]
        return match.group(0) if SHELL_WORD.search(head) else "\n"

    return QUOTED_HEREDOC.sub(drop, command)


def check_fetch_tool(segment: str, allowed: str) -> list[str]:
    problems = foreign_in_text(segment, allowed)
    for path in API_HOST_PATH.findall(segment):
        clean = path.split("?")[0].lstrip("/").lower()
        if not (clean.startswith(f"repos/{allowed}") or clean in ("user", "rate_limit")):
            problems.append(f"api.github.com path {path} is outside {allowed}")
    return problems


def check_command(command: str, allowed: str, loop: bool = False) -> list[str]:
    """Return the reasons to block a command, or an empty list when it may run."""
    command = without_inert_heredocs(command)
    problems: list[str] = []
    if TOKEN_USE.search(command):
        problems.append("the token must never be read or printed (GH_TOKEN, printenv, env)")
    if RELEVANT.search(command) is None:
        return problems
    if ADMIN_GH.search(command):
        problems.append("gh commands that manage repositories, accounts or secrets are not allowed")
    for segment in split_segments(command):
        text = segment.strip()
        for env_value in GH_REPO_ENV.findall(text):
            if repo_from_value(env_value) != allowed:
                problems.append(f"GH_REPO points to {repo_from_value(env_value)}")
        if match := GH_SEGMENT.match(text):
            problems.extend(check_gh(match.group(1), allowed, loop))
        elif match := GIT_SEGMENT.match(text):
            problems.extend(check_git(match.group(1), allowed))
        elif FETCH_SEGMENT.match(text):
            problems.extend(check_fetch_tool(text, allowed))
        elif SSH_SEGMENT.match(text):
            problems.extend(check_ssh(text))
    return list(dict.fromkeys(problems))


def config_path(app: Path, named: str | None) -> Path:
    """FLOW_CONFIG, else <project>/.flow/flow.toml when it exists, else <project>/ops/flow.toml."""
    if named:
        return Path(named)
    new = app / ".flow" / "flow.toml"
    return new if new.is_file() else app / "ops" / "flow.toml"


def new_layout_loader(config: Path) -> list[Path]:
    """`<paths.loop_dir>/flow_config.py` of a .flow/flow.toml (default .flow/loop); else none."""
    if config.parent.name != ".flow":
        return []
    folder = ".flow/loop"
    try:
        import tomllib

        named = tomllib.loads(config.read_text()).get("paths", {}).get("loop_dir")
        folder = named if isinstance(named, str) and named else folder
    except Exception:  # the loader reports a broken file with its own message
        pass
    return [config.parent.parent / folder / "flow_config.py"]


def loader_path(app: Path, named: str | None) -> Path:
    """The reader of the config's project (.flow/loop/ or ops/), else beside FLOW_CONFIG."""
    candidates = [
        *new_layout_loader(config_path(app, named)),
        app / "ops" / "flow_config.py",
        *new_layout_loader(config_path(app, None)),
    ]
    if named:
        candidates.append(Path(named).parent / "flow_config.py")
    session = os.environ.get("CLAUDE_PROJECT_DIR")
    if session:
        candidates.extend(new_layout_loader(config_path(Path(session), None)))
        candidates.append(Path(session) / "ops" / "flow_config.py")
    return next((path for path in candidates if path.is_file()), candidates[0])


def flow_config(env: Mapping[str, str], cwd: str | None = None) -> Any:
    """The project's flow.toml (CLAUDE_PROJECT_DIR, else the cwd), or FLOW_CONFIG's file."""
    session = env.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    app = Path(session or cwd or os.getcwd())
    named = env.get("FLOW_CONFIG")
    module_path = loader_path(app, named)
    spec = util.spec_from_file_location("flow_config", module_path)
    if spec is None or spec.loader is None:
        raise OSError(f"cannot load {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module.load(config_path(app, named))


def read_allowed(env: Mapping[str, str] | None = None, cwd: str | None = None) -> str:
    """The one repository that may be reached: project.repo of ops/flow.toml, lowercase."""
    repo = str(flow_config(os.environ if env is None else env, cwd).project_repo).strip()
    if not repo:
        raise ValueError("ops/flow.toml has no project.repo")
    return repo.lower()


LOOP_VARS = ("FLOW_LOOP",)


def is_loop() -> bool:
    """Loop mode is on when FLOW_LOOP=1."""
    return any(os.environ.get(name) == "1" for name in LOOP_VARS)


LOOP_BRANCH = re.compile(r"^(?:bug|feat|task)/\d+-[a-z0-9][a-z0-9-]*$")
SPEC_BRANCH = re.compile(r"^task/spec-[a-z0-9][a-z0-9-]*$")
FORCE_FLAGS = {"--mirror", "--delete", "--prune", "--all"}
MAIN_NAMES = {"main", "master"}
MERGE_FLAGS = {"--merge", "-m"}
SHA = re.compile(r"^[0-9a-f]{7,40}$")
API_MERGE = re.compile(r"(?:^|/)(?:pulls/\d+/merge|merges|git/refs)(?:/|$|\?)", re.I)
API_WRITE = {"POST", "PUT", "PATCH"}
MERGE_USAGE = "gh pr merge must be exactly: gh pr merge <number> --merge --match-head-commit <sha>"
GitRunner = Callable[[list[str]], tuple[int, str]]


def push_problems(args: list[str], run: GitRunner) -> list[str]:
    """A push may never force, delete, push everything or reach main, in any mode."""
    flags = [arg for arg in args if arg.startswith("-")]
    positional = [arg for arg in args if not arg.startswith("-")]
    problems: list[str] = []
    for flag in flags:
        short = set(flag[1:]) if not flag.startswith("--") else set()
        if flag in FORCE_FLAGS or flag.startswith("--force") or short & {"f", "d"}:
            problems.append(f"git push {flag} is not allowed (force, delete or everything)")
    refspecs = positional[1:]
    for spec in refspecs:
        target = spec.split(":", 1)[-1].removeprefix("refs/heads/")
        if spec.startswith(("+", ":")) or target in MAIN_NAMES:
            problems.append(f"git push {spec} is not allowed (force, delete or main)")
    if not refspecs or any(spec in ("HEAD", "@") for spec in refspecs):
        code, branch = run(["git", "branch", "--show-current"])
        if code != 0 or branch.strip() in MAIN_NAMES or not branch.strip():
            problems.append("git push needs a current branch that is not main")
    return problems


def merge_problems(args: list[str], run: GitRunner) -> tuple[list[str], str]:
    """A merge is exact, names the head commit the user saw, and is never the loop's own."""
    number = sha = ""
    merge = False
    index = 0
    while index < len(args):
        token = args[index]
        if token in MERGE_FLAGS:
            merge = True
        elif token == "--match-head-commit" and index + 1 < len(args):
            sha = args[index + 1].lower()
            index += 1
        elif token.startswith("--match-head-commit="):
            sha = token.split("=", 1)[1].lower()
        elif not token.startswith("-") and not number and token.isdigit():
            number = token
        else:
            return [MERGE_USAGE], ""
        index += 1
    if not (merge and number and SHA.match(sha)):
        return [MERGE_USAGE], ""
    fields = "state,headRefName,headRefOid,baseRefName,isCrossRepository"
    code, out = run(["gh", "pr", "view", number, "--json", fields])
    try:
        data = json.loads(out) if code == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return ["the pull request could not be read, so the merge cannot be checked"], ""
    problems: list[str] = []
    if data.get("state") != "OPEN":
        problems.append("the pull request is not open")
    head = str(data.get("headRefName", ""))
    if not (LOOP_BRANCH.match(head) or SPEC_BRANCH.match(head)):
        problems.append(
            "only an issue branch (kind/number-description) or a spec branch (task/spec-name) "
            "may be merged here"
        )
    if data.get("baseRefName") != "main" or data.get("isCrossRepository"):
        problems.append("only a same-repository pull request into main may be merged here")
    if not str(data.get("headRefOid", "")).lower().startswith(sha):
        problems.append("--match-head-commit is not the pull request's current head commit")
    summary = f"gh pr merge {number} ({data.get('headRefName')}, head {sha[:7]})"
    return problems, summary


def api_problems(tokens: list[str], positional: list[str]) -> list[str]:
    """gh api must not be a side door to merge or move a ref."""
    if len(positional) < 2:
        return []
    method = "GET"
    path = next((token for token in tokens if API_MERGE.search(token)), "")
    for index, token in enumerate(tokens):
        if token in ("-X", "--method") and index + 1 < len(tokens):
            method = tokens[index + 1].upper()
        elif token.startswith("--method="):
            method = token.split("=", 1)[1].upper()
        elif token in ("-f", "-F", "--field", "--raw-field", "--input") and method == "GET":
            method = "POST"
    if method in API_WRITE and path:
        return [f"gh api {method} {path} would merge or move a ref; use gh pr merge"]
    return []


def unsplit_publishes(rest: str, gh: bool) -> bool:
    """Whether a command that cannot be split may push, open a pull request, merge or call api."""
    words = leading_words(rest)
    if not words:
        return re.search(r"\b(push|merge|create|api)\b", rest) is not None
    if gh:
        return words[0] not in GH_UNSPLIT_OK or words[:2] in (["pr", "create"], ["pr", "merge"])
    return words[0] == "push"


def check_publish(
    command: str, loop: bool, run: GitRunner, allowed: str | None = None
) -> tuple[str, list[str]]:
    """Decide push, pull request, merge and gh api: ('allow' | 'ask' | 'deny', reasons)."""
    allowed = allowed or read_allowed()
    problems: list[str] = []
    ask: list[str] = []
    marks: list[str] = []
    segments = [s.strip() for s in split_segments(without_inert_heredocs(command))]
    segments = [segment for segment in segments if segment]
    moves = any(re.match(r"^(?:cd|pushd)\b", segment) for segment in segments)
    for segment in segments:
        gh = GH_SEGMENT.match(segment)
        git = None if gh else GIT_SEGMENT.match(segment)
        if not gh and not git:
            continue
        rest = (gh or git).group(1)  # type: ignore[union-attr]
        try:
            tokens = shlex.split(rest)
        except ValueError:
            if unsplit_publishes(rest, bool(gh)):
                problems.append("the command could not be read safely")
            continue
        if git:
            index = 0
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 2 if tokens[index] in ("-C", "-c", "--git-dir", "--work-tree") else 1
            if index < len(tokens) and tokens[index] == "push":
                if index > 0 or moves:
                    problems.append("git push must run in the current folder, without options")
                problems.extend(push_problems(tokens[index + 1 :], run))
                if not loop:
                    ask.append("git push needs your approval outside loop mode")
            continue
        positional = [token for token in tokens if not token.startswith("-")]
        if positional[:1] == ["api"]:
            problems.extend(api_problems(tokens, positional))
            kind = review_mark_call(tokens, allowed)
            if not loop:
                ask.append("gh api needs your approval outside loop mode")
            elif kind:
                marks.append(f"review mark: {kind}")
            elif mark_path(api_path(tokens), allowed):
                problems.append(
                    "in loop mode a review mark is exactly a POST of eyes, rocket or confused, "
                    "a reply body, or the resolveReviewThread mutation"
                )
        elif positional[:2] == ["pr", "create"] and not loop:
            ask.append("opening a pull request needs your approval outside loop mode")
        elif positional[:2] == ["pr", "merge"]:
            if loop:
                problems.append("the loop never merges; the owner merges in an interactive session")
            elif len(segments) > 1:
                problems.append("gh pr merge must be the only command in the call")
            else:
                found, summary = merge_problems(tokens[tokens.index("merge") + 1 :], run)
                problems.extend(found)
                ask.append(f"merge: {summary}")
    if problems:
        return "deny", list(dict.fromkeys(problems))
    return ("ask", ask) if ask else ("allow", marks)


REPORT_LINK = "https://claude.ai/artifact/"
PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
COMMAND_END = {";", "&", "&&", "|", "||", "(", ")"}
NO_REPORT_LINK = "a loop pull request needs the verify report link (share-report)"


def pr_create_args(command: str, start: int) -> list[str] | None:
    """The arguments of one gh pr create, up to the next shell operator; None if unreadable."""
    lexer = shlex.shlex(command[start:], posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    args: list[str] = []
    try:
        for token in lexer:
            if token in COMMAND_END:
                break
            args.append(token)
    except ValueError:
        return None
    return args


def pr_body(args: list[str], cwd: str) -> str | None:
    """The body from --body / -b and --body-file / -F; None when missing or unreadable."""
    body: str | None = None
    for index, arg in enumerate(args):
        name, _, inline = arg.partition("=")
        if name not in ("--body", "-b", "--body-file", "-F"):
            continue
        if inline or "=" in arg:
            value = inline
        elif index + 1 < len(args):
            value = args[index + 1]
        else:
            return None
        if name in ("--body", "-b"):
            body = (body or "") + value
            continue
        if value == "-":
            return None
        try:
            body = (body or "") + (Path(cwd) / value).read_text()
        except (OSError, UnicodeDecodeError):
            return None
    return body


def report_link_problems(command: str, cwd: str) -> list[str]:
    """In loop mode every gh pr create must carry the private artifact link of the verify report."""
    if PR_CREATE.search(without_inert_heredocs(command)) is None:
        return []
    problems: list[str] = []
    for match in PR_CREATE.finditer(command):
        args = pr_create_args(command, match.end())
        body = pr_body(args, cwd) if args is not None else None
        if body is None or REPORT_LINK not in body:
            problems.append(NO_REPORT_LINK)
    return list(dict.fromkeys(problems))


def publish_gate(command: str, cwd: str) -> int:
    def run(args: list[str]) -> tuple[int, str]:
        try:
            done = subprocess.run(
                args, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return 127, ""
        return done.returncode, done.stdout

    loop = is_loop()
    try:
        decision, reasons = check_publish(command, loop, run, read_allowed(os.environ, cwd))
        if loop:
            link_problems = report_link_problems(command, cwd)
            if link_problems:
                kept = reasons if decision == "deny" else []
                decision, reasons = "deny", kept + link_problems
    except Exception as error:  # fail closed
        decision, reasons = "deny", [f"the publish guard failed ({error})"]
    if decision == "deny":
        message = "; ".join(reasons)
        print(f"Blocked by before-github-command-check: {message}.", file=sys.stderr)
        return 2
    if decision == "ask" or reasons:
        reply = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": "; ".join(reasons),
            }
        }
        print(json.dumps(reply))
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    plain = without_inert_heredocs(command)
    if RELEVANT.search(command) is None and TOKEN_USE.search(plain) is None:
        return 0
    try:
        cwd = str(payload.get("cwd") or "") or None
        allowed_name = read_allowed(os.environ, cwd)
        problems = check_command(command, allowed_name, is_loop())
    except Exception as error:  # fail closed for anything that looks relevant
        problems = [f"the guard could not check this command ({error})"]
        allowed_name = "the allowed repository"
    if not problems:
        return publish_gate(command, str(payload.get("cwd") or os.getcwd()))
    print(
        f"Blocked by before-github-command-check: {'; '.join(problems)}. "
        f"Only {allowed_name} may be reached from here (see .claude/rules/security.md).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
