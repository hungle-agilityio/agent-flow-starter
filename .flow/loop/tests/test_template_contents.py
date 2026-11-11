"""The template is complete on its own: its decision records, commands and guards."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DECISIONS = ROOT / "docs" / "decisions"
HOOK = ROOT / ".flow" / "plugin" / "hooks" / "before-edit-check.py"
CITED = re.compile(r"ADR-(\d{3})")


def test_every_cited_decision_record_is_here() -> None:
    texts = [
        p.read_text()
        for p in (*(ROOT / ".claude").rglob("*.md"), *(ROOT / ".flow" / "plugin").rglob("*.md"))
    ]
    cited = {number for text in texts for number in CITED.findall(text)}
    present = {p.name[4:7] for p in DECISIONS.glob("ADR-*.md")}
    assert cited - present == set()
    assert {"020", "021", "022", "023", "024", "025"} <= present


def test_the_decisions_index_lists_exactly_the_files() -> None:
    index = (DECISIONS / "README.md").read_text().split("## Index", 1)[1]
    listed = set(re.findall(r"\((ADR-[^)]+\.md)\)", index))
    assert listed == {p.name for p in DECISIONS.glob("ADR-*.md")}


def test_commands_name_only_files_that_exist() -> None:
    text = (ROOT / ".flow" / "plugin" / "commands" / "understand.md").read_text()
    for path in ("CLAUDE.md", "docs/architecture.md", ".claude/rules/domain.md"):
        assert f"`{path}`" in text and (ROOT / path).is_file()


def test_loop_builds_may_not_edit_the_flow_folder_unless_listed(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("before_edit_check_template", HOOK)
    assert spec is not None and spec.loader is not None
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    assert ".flow" in hook.PLUGIN_DIRS
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".flow" / "loop").mkdir(parents=True)
    target = tmp_path / ".flow" / "loop" / "agent_tick.py"
    assert hook.in_plugin_source(target, hook.real_run)
    assert not hook.in_plugin_source(tmp_path / "src" / "app.py", hook.real_run)
