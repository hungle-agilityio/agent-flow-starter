"""setup_project.py turns a copy of the template into one project, for each stack."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".flow" / "loop" / "setup_project.py"
TEMPLATE_VALUES = re.compile(r"agent-flow-starter|Agent flow starter|CHANGE-ME|agent-flow@starter")
STACKS = ("python", "node", "other")

if 'repo = "hungle-agilityio/agent-flow-starter"' not in (ROOT / ".flow" / "flow.toml").read_text():
    pytest.skip("this project is already set up from the template", allow_module_level=True)


def load_setup():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("setup_project", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_project"] = module
    spec.loader.exec_module(module)
    return module


SETUP = load_setup()


@pytest.fixture
def copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh copy of the template whose origin is the new repository."""
    target = tmp_path / "garden"
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:acme/garden.git"], cwd=target, check=True
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return target


def setup(target: Path, stack: str, *extra: str) -> int:
    argv = [
        "--repo", "acme/garden", "--owner", "acme-owner", "--name", "Garden", "--slug", "garden",
        "--ntfy-topic", "garden-loop-x7k2", "--stack", stack, "--no-labels", *extra,
    ]  # fmt: skip
    try:
        return int(SETUP.run(SETUP.parse(argv), target))
    except SETUP.SetupError as error:
        print(error, file=sys.stderr)
        return 2


def files(root: Path) -> list[Path]:
    skip = {".git", "stacks", "tests"}
    return [
        p for p in root.rglob("*")
        if p.is_file() and not skip & set(p.relative_to(root).parts)
        and p.name not in ("setup_project.py", "setup-project.sh")
    ]  # fmt: skip


@pytest.mark.parametrize("stack", STACKS)
def test_no_template_value_is_left(copy: Path, stack: str) -> None:
    assert setup(copy, stack) == 0
    hits = [str(p.relative_to(copy)) for p in files(copy) if TEMPLATE_VALUES.search(p.read_text())]
    assert hits == []


@pytest.mark.parametrize(
    ("stack", "setup_command", "check_word"),
    [
        ("python", ["uv", "sync", "--frozen"], "uv run pytest -q"),
        ("node", ["npm", "ci"], "npm test"),
        ("other", ["bash", "scripts/setup.sh"], "TODO: add the checks of this stack"),
    ],
)
def test_stack_values_are_written(
    copy: Path, stack: str, setup_command: list[str], check_word: str
) -> None:
    setup(copy, stack)
    flow = (copy / ".flow" / "flow.toml").read_text()
    assert 'repo = "acme/garden"' in flow and 'slug = "garden"' in flow
    assert f"setup_command = {json.dumps(setup_command)}" in flow
    assert 'id = "agent-flow@garden"' in flow and 'tmux_session = "garden-loop"' in flow
    assert check_word in (copy / "scripts" / "check.sh").read_text()
    settings = json.loads((copy / ".claude" / "settings.json").read_text())
    assert settings["enabledPlugins"] == {"agent-flow@garden": True}
    market = json.loads((copy / ".claude-plugin" / "marketplace.json").read_text())
    assert market["name"] == "garden"


def test_python_gets_its_ci_gitignore_and_project_file(copy: Path) -> None:
    setup(copy, "python")
    ci = (copy / ".github" / "workflows" / "checks.yml").read_text()
    assert "run: uv sync --frozen" in ci and "bash scripts/setup.sh" not in ci
    assert ".venv/" in (copy / ".gitignore").read_text().splitlines()
    assert 'name = "garden"' in (copy / "pyproject.toml").read_text()


def test_node_gets_its_ci_and_gitignore(copy: Path) -> None:
    setup(copy, "node")
    ci = (copy / ".github" / "workflows" / "checks.yml").read_text()
    assert "actions/setup-node@v4" in ci and "run: npm ci" in ci
    assert "node_modules/" in (copy / ".gitignore").read_text().splitlines()
    assert not (copy / "pyproject.toml").exists()


def test_agent_env_is_written_and_kept(copy: Path, tmp_path: Path) -> None:
    setup(copy, "other")
    env = tmp_path / "home" / ".garden" / "agent.env"
    text = env.read_text()
    assert "NTFY_TOPIC=garden-loop-x7k2" in text and "AGENT_CONCURRENCY=1" in text
    env.write_text("kept\n")
    assert SETUP.write_agent_env(copy, SETUP.parse(["--repo", "acme/garden", "--owner", "o",
        "--name", "G", "--slug", "garden", "--ntfy-topic", "t", "--stack", "other"])).endswith(
        "kept as it is")  # fmt: skip
    assert env.read_text() == "kept\n"


def test_a_second_run_stops(copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert setup(copy, "node") == 0
    assert setup(copy, "node") == 2
    assert "already set up" in capsys.readouterr().err


def test_dry_run_writes_nothing(copy: Path, tmp_path: Path) -> None:
    before = {p: p.read_bytes() for p in files(copy)}
    assert setup(copy, "python", "--dry-run") == 0
    assert {p: p.read_bytes() for p in files(copy)} == before
    assert not (tmp_path / "home" / ".garden").exists()


def test_origin_must_be_the_new_repository(copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    subprocess.run(
        ["git", "remote", "set-url", "origin", "git@github.com:acme/other.git"], cwd=copy, check=True
    )
    assert setup(copy, "other") == 2
    assert "origin" in capsys.readouterr().err


def test_template_itself_is_refused() -> None:
    with pytest.raises(SETUP.SetupError):
        SETUP.parse(["--repo", "hungle-agilityio/agent-flow-starter", "--owner", "o", "--name", "n",
            "--slug", "s1", "--ntfy-topic", "t", "--stack", "other"])  # fmt: skip


def test_readme_becomes_the_projects(copy: Path) -> None:
    setup(copy, "other")
    assert (copy / "README.md").read_text().startswith("# Garden\n")
