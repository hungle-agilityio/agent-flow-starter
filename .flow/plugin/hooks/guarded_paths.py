"""The guarded-files rule, once: read by before-edit-check.py and by ops/epic_pull_request.py.

Standard library only and no project import, so the hook can load it by file path.
"""

from __future__ import annotations

PROTECTED_DIRS = {".github", ".claude"}
PROTECTED_FILES = {".mcp.json", "flow.toml"}
PLUGIN_DIRS = {"plugins", ".claude-plugin", ".flow"}
GATE_FILES = {
    "pyproject.toml",
    "uv.lock",
    "conftest.py",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "setup.cfg",
    "pytest.ini",
    "tox.ini",
    ".coveragerc",
}


def guarded_kind(parts: tuple[str, ...]) -> str | None:
    """The kind of casefolded path parts: rule, then plugin, then gate; None when not guarded."""
    if not parts:
        return None
    if PROTECTED_DIRS & set(parts) or parts[-1] in PROTECTED_FILES:
        return "rule"
    if parts[0] in PLUGIN_DIRS:
        return "plugin"
    if parts[-1] in GATE_FILES:
        return "gate"
    return None
