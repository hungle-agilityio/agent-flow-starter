"""Turn a copy of the agent-flow starter template into one project; run it once, at the root.

`bash scripts/setup-project.sh --repo <owner/name> --owner <login> --name <display name>
--slug <slug> --ntfy-topic <topic> --stack python|node|other [--dry-run] [--no-labels]`

It renames the template values in every text file, writes the stack's part of
`scripts/check.sh`, `scripts/setup.sh`, `.gitignore`, `.flow/flow.toml` and the CI workflow,
writes `~/.<slug>/agent.env` (kept when it exists), creates the labels with
`gh label create --force` and prints the steps only the owner can do. A second run stops,
because the template values are gone. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STACKS_DIR = Path(__file__).resolve().parent / "stacks"
STACKS = ("python", "node", "other")
TEMPLATE_REPO = "hungle-agilityio/agent-flow-starter"
TEMPLATE_OWNER = "hungle-agilityio"
TEMPLATE_NAME = "Agent flow starter"
TEMPLATE_SLUG = "starter"
TEMPLATE_TOPIC = "CHANGE-ME"
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ORIGIN = re.compile(
    r"^(?:https?://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$",
)
BARE_SLUG = re.compile(rf"(?<![\w-]){TEMPLATE_SLUG}(?![\w-])")
SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", "stacks"}
# The setup script and its tests keep the template values, so a second run still stops.
SKIP_FILES = {".flow/loop/setup_project.py", "scripts/setup-project.sh"}
SKIP_DIRS = (".flow/loop/tests/",)
CI_SETUP_STEP = re.compile(r"(?ms)^(      - uses: actions/setup-python@v5\n.*?\n)(?=      - name: Lint)")
PYTHON_SETUP = '      - uses: actions/setup-python@v5\n        with:\n          python-version: "3.11"\n'


class SetupError(Exception):
    """The run cannot go on; nothing was written."""


@dataclass(frozen=True)
class Params:
    repo: str
    owner: str
    name: str
    slug: str
    ntfy_topic: str
    stack: str
    dry_run: bool
    labels: bool


def parse(argv: Sequence[str]) -> Params:
    parser = argparse.ArgumentParser(prog="setup-project.sh", description=__doc__.split("\n")[0])
    for flag in ("--repo", "--owner", "--name", "--slug", "--ntfy-topic"):
        parser.add_argument(flag, required=True)
    parser.add_argument("--stack", required=True, choices=STACKS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-labels", action="store_true")
    args = parser.parse_args(argv)
    if not SLUG.match(args.slug):
        raise SetupError(f"--slug {args.slug!r} must match {SLUG.pattern}")
    if not REPO.match(args.repo):
        raise SetupError(f"--repo {args.repo!r} must look like owner/name")
    if args.repo.lower() == TEMPLATE_REPO.lower():
        raise SetupError("--repo is the template itself; use the new repository")
    return Params(
        args.repo, args.owner, args.name, args.slug, args.ntfy_topic, args.stack,
        args.dry_run, not args.no_labels,
    )  # fmt: skip


def check_root(root: Path, params: Params) -> None:
    """The folder is a fresh copy of the template whose origin is the new repository."""
    flow = root / ".flow" / "flow.toml"
    if not flow.is_file():
        raise SetupError(f"{flow} is missing; run this at the root of a copy of the template")
    if f'repo = "{TEMPLATE_REPO}"' not in flow.read_text():
        raise SetupError("this project is already set up (.flow/flow.toml names another repo)")
    done = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    match = ORIGIN.match(done.stdout.strip())
    if done.returncode != 0 or match is None or match["repo"].lower() != params.repo.lower():
        raise SetupError(f"origin of {root} must be {params.repo} (it is {done.stdout.strip()!r})")


def rename(text: str, params: Params) -> str:
    repo_name = params.repo.split("/", 1)[1]
    text = text.replace(TEMPLATE_REPO, params.repo)
    text = text.replace(TEMPLATE_REPO.split("/", 1)[1], repo_name)
    text = text.replace(TEMPLATE_NAME, params.name)
    text = text.replace(f"{TEMPLATE_SLUG}-loop", f"{params.slug}-loop")
    text = BARE_SLUG.sub(params.slug, text)
    text = text.replace(TEMPLATE_OWNER, params.owner)
    return text.replace(TEMPLATE_TOPIC, params.ntfy_topic)


def text_files(root: Path) -> list[Path]:
    found = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        name = rel.as_posix()
        if name in SKIP_FILES or name.startswith(SKIP_DIRS):
            continue
        if path.is_file() and not SKIP_PARTS & set(rel.parts):
            found.append(path)
    return found


def stack_file(stack: str, name: str) -> str:
    return (STACKS_DIR / stack / name).read_text()


def flow_toml(text: str, stack: dict[str, object]) -> str:
    def words(items: object) -> str:
        assert isinstance(items, list)
        return "[" + ", ".join(json.dumps(item) for item in items) + "]"

    text = re.sub(r"(?m)^setup_command = .*$", f"setup_command = {words(stack['setup_command'])}", text)
    return re.sub(r"(?m)^alone_words = .*$", f"alone_words = {words(stack['alone_words'])}", text)


def checks_yml(text: str, stack: dict[str, object]) -> str:
    setup = PYTHON_SETUP + str(stack["ci_setup"])
    return CI_SETUP_STEP.sub(lambda _: setup, text, count=1)


def gitignore(text: str, stack: str) -> str:
    part = stack_file(stack, "gitignore")
    return text if not part or part in text else text.rstrip("\n") + "\n" + part


def plan(root: Path, params: Params) -> dict[Path, str]:
    """Every file that changes, with its new text."""
    stack: dict[str, object] = json.loads(stack_file(params.stack, "stack.json"))
    changed: dict[Path, str] = {}
    for path in text_files(root):
        try:
            old = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = rename(old, params)
        rel = path.relative_to(root).as_posix()
        if rel == ".flow/flow.toml":
            new = flow_toml(new, stack)
        elif rel == ".github/workflows/checks.yml":
            new = checks_yml(new, stack)
        elif rel == ".gitignore":
            new = gitignore(new, params.stack)
        if new != old:
            changed[path] = new
    for name in ("check.sh", "setup.sh"):
        changed[root / "scripts" / name] = stack_file(params.stack, name)
    readme = (STACKS_DIR / "README.project.md").read_text()
    changed[root / "README.md"] = readme.replace("{name}", params.name)
    if params.stack == "python" and not (root / "pyproject.toml").exists():
        text = stack_file("python", "pyproject.toml.stub").replace(TEMPLATE_SLUG, params.slug)
        changed[root / "pyproject.toml"] = text
    return changed


def agent_env_text(root: Path, params: Params) -> str:
    example = (root / ".flow" / "loop" / "agent.env.example").read_text()
    values = {"AGENT_CONCURRENCY": "1", "NTFY_TOPIC": params.ntfy_topic}
    lines = []
    for line in rename(example, params).splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={values[key]}" if "=" in line and key in values else line)
    lines += ["", "# Written by .flow/loop/setup_project.py", "CLAUDE_CODE_ENTRYPOINT=claude-desktop"]
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        lines.append(f"CLAUDE_CONFIG_DIR={config_dir}")
    return "\n".join(lines) + "\n"


def write_agent_env(root: Path, params: Params) -> str:
    path = Path.home() / f".{params.slug}" / "agent.env"
    if path.exists():
        return f"{path} exists, kept as it is"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent_env_text(root, params))
    path.chmod(0o600)
    return f"wrote {path}"


def create_labels(params: Params) -> list[str]:
    """Run `gh label create --force` for each label; return the names that failed."""
    failed = []
    for label in json.loads((STACKS_DIR / "labels.json").read_text()):
        command = [
            "gh", "label", "create", label["name"], "--color", label["color"],
            "--description", label["description"], "--force", "-R", params.repo,
        ]  # fmt: skip
        try:
            done = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError:
            failed.append(label["name"])
            continue
        if done.returncode != 0:
            failed.append(label["name"])
    return failed


def steps(params: Params) -> list[str]:
    return [
        f"Add {params.repo} to the Mac mini fine-grained token (Repository access).",
        f"Install the Claude GitHub App on {params.repo}.",
        "Write the app skeleton in src/<feature>/ with one test beside it, make "
        "`bash scripts/check.sh` pass, then commit on a branch and open a pull request; merge it.",
        f"Create the ruleset on main (pull request required, check `Checks`): "
        f"https://github.com/{params.repo}/settings/rules",
        f"Subscribe to the ntfy topic {params.ntfy_topic} on your phone.",
        f"Run: claude plugin marketplace add {params.repo}",
        f"Run at the repository root: claude plugin install agent-flow@{params.slug} --scope project",
        f"Run: claude plugin install agent-flow@{params.slug} --scope user, then "
        f"claude plugin disable agent-flow@{params.slug} --scope user (never enable it there).",
        "Run once: bash .flow/loop/install-launchd.sh",
        "Paste .claude/project-instructions.md into the Claude Project's instructions.",
    ]


def run(params: Params, root: Path = ROOT) -> int:
    check_root(root, params)
    changed = plan(root, params)
    for path in sorted(changed):
        rel = path.relative_to(root).as_posix()
        print(rel if params.dry_run else f"wrote {rel}")
        if not params.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(changed[path], encoding="utf-8")
            if path.suffix == ".sh":
                path.chmod(0o755)
    if params.dry_run:
        print(f"would write ~/.{params.slug}/agent.env unless it exists")
        if params.labels:
            print("would create the labels with gh label create --force")
    else:
        print(write_agent_env(root, params))
        if params.labels:
            failed = create_labels(params)
            print("labels: all created" if not failed else "labels not created: " + ", ".join(failed))
    print("\nSteps for you:")
    for number, text in enumerate(steps(params), start=1):
        print(f"{number}. {text}")
    return 0


def main(argv: Sequence[str]) -> int:
    try:
        return run(parse(argv))
    except SetupError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
