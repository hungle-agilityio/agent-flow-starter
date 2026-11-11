"""List the existing tests an issue's ACs would change, before the issue gets agent:ready.

Spec: specs/loop-verify-failures/spec.md (AC6 to AC9), specs/fail-fix/spec.md (AC1 to AC5).
Run from the app folder: `uv run python <loop folder>/pinned_tests.py [--unlisted] <issue body>`
(`ops/` in Agent flow starter, `.flow/loop/` in a new project). `--unlisted` prints only the hits the
body does not name and exits 1 when there is one. The test roots are `checks.protected_test_dirs`,
the loop's own tests and `paths.plugin_dir`; the app folders are `paths.code_dirs` (spec:
specs/project-layout/spec.md, AC15). Standard library only; it writes no file and runs no test.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

try:
    from ops import flow_config
except ImportError:  # started as a script: its own folder is the first path entry
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]


def folder(path: str) -> str:
    return path.strip().removeprefix("./").rstrip("/")


CONFIG = flow_config.load()
PROJECT = flow_config.PROJECT_DIR
APP_PREFIX = "" if folder(CONFIG.project_app_dir) in ("", ".") else f"{CONFIG.project_app_dir}/"
TEST_ROOTS = (
    *(folder(d) for d in CONFIG.checks_protected_test_dirs),
    f"{folder(CONFIG.paths_loop_dir)}/tests",
    folder(CONFIG.paths_plugin_dir),
)
NOTHING_FOUND = "No existing test pins this task."
MIN_NAME_LENGTH = 4
COMMON_NAMES = {"main", "None", "True", "False"}
QUERY_CODE_ENDINGS = ("view", "views", "service", "services", "repository", "repositories")

BACKTICKED = re.compile(r"`([^`\n]+)`")
FILE_NAME = re.compile(r"^[\w-]+(?:\.[\w-]+)*\.[A-Za-z0-9]{1,5}$")
COUNTS_QUERIES = re.compile(
    r"\b(?:django_assert_num_queries|django_assert_max_num_queries|assertNumQueries"
    r"|CaptureQueriesContext)\b"
)
CAP_CALL = re.compile(
    r"\b(?:django_assert_num_queries|django_assert_max_num_queries|assertNumQueries)"
    r"\(\s*(\d+)\s*[,)]"
)
CAP_LEN = re.compile(r"\blen\(\s*\w+(?:\.captured_queries)?\s*\)\s*(?:==|<=|<)\s*(\d+)")
NOT_NAMES = {
    "views.py", "services.py", "repositories.py", "models.py", "urls.py", "forms.py", "app.css",
}  # fmt: skip
APP_FOLDERS = tuple(f"{folder(d)}/" for d in CONFIG.paths_code_dirs)
QUERY_CODE_DIR = APP_FOLDERS[0] if APP_FOLDERS else ""
PLUGIN_ROOT = folder(CONFIG.paths_plugin_dir)
UNLISTED = "--unlisted"
FILES_HEADING = "## files likely touched"

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def new_paths(body: str) -> set[str]:
    """Every spelling of a path marked (NEW) is out: the path and its file name."""
    found: set[str] = set()
    for line in body.splitlines():
        if "(NEW" in line:
            for token in BACKTICKED.findall(line):
                found |= {token, token.rsplit("/", 1)[-1]}
    return found


def names_in(body: str) -> list[str]:
    """The backticked identifiers and file names, in body order, without new paths."""
    excluded = new_paths(body)
    names: list[str] = []
    for token in BACKTICKED.findall(body):
        name = token.rsplit("/", 1)[-1] if "/" in token else token
        usable = name.isidentifier() or FILE_NAME.match(name)
        if not usable or token in excluded or name in excluded or name in NOT_NAMES:
            continue
        if len(name) >= MIN_NAME_LENGTH and name not in COMMON_NAMES and name not in names:
            names.append(name)
    return names


def touched_paths(body: str) -> list[str]:
    """The paths under "Files likely touched" that are not marked (NEW)."""
    paths: list[str] = []
    inside = False
    for line in body.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == FILES_HEADING
        elif inside and "(NEW" not in line:
            paths += [p.removeprefix(APP_PREFIX) for p in BACKTICKED.findall(line)]
    return paths


def listed_paths(body: str) -> list[str]:
    """Every path under "Files likely touched", new ones included."""
    paths: list[str] = []
    inside = False
    for line in body.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == FILES_HEADING
        elif inside:
            paths += [p.removeprefix(APP_PREFIX) for p in BACKTICKED.findall(line)]
    return paths


def app_only(body: str) -> bool:
    """Every listed path is in the app, so the plugin's tests cannot pin it."""
    paths = listed_paths(body)
    return bool(paths) and all(p.startswith(APP_FOLDERS) for p in paths)


def url_prefixes(body: str) -> list[str]:
    """The backticked URLs of the body, each cut before its first `<`."""
    found: list[str] = []
    for token in BACKTICKED.findall(body):
        if token.startswith("/") and not token.startswith("//"):
            prefix = token.split("<", 1)[0]
            if prefix not in found:
                found.append(prefix)
    return found


def requests_any(source: str, prefixes: list[str]) -> bool:
    return any(re.search(rf"[\"']{re.escape(prefix)}", source) for prefix in prefixes)


def cap_reason(source: str) -> str:
    """`query cap N` with the number of the test, or `query cap` when it is not a literal."""
    match = CAP_CALL.search(source) or CAP_LEN.search(source)
    return f"query cap {match.group(1)}" if match else "query cap"


def is_query_code(path: str) -> bool:
    """A view, a template, a service or a repository in the first code folder, not a test."""
    if not QUERY_CODE_DIR or not path.startswith(QUERY_CODE_DIR) or "tests" in path.split("/"):
        return False
    return path.endswith(".html") or Path(path).stem.endswith(QUERY_CODE_ENDINGS)


def test_nodes(tree: ast.Module) -> list[FunctionNode]:
    """Module-level test functions and the test methods of classes."""
    found: list[FunctionNode] = []
    for node in tree.body:
        members = node.body if isinstance(node, ast.ClassDef) else [node]
        found += [
            member
            for member in members
            if isinstance(member, FunctionNode) and member.name.startswith("test")
        ]
    return found


def segment(lines: list[str], node: ast.stmt) -> str:
    decorators = getattr(node, "decorator_list", [])
    first = decorators[0].lineno if decorators else node.lineno
    return "\n".join(lines[first - 1 : node.end_lineno])


def module_level_sources(tree: ast.Module, lines: list[str]) -> dict[str, str]:
    """Source of each module-level helper and constant, by name."""
    sources: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, FunctionNode):
            sources[node.name] = segment(lines, node)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    sources[target.id] = segment(lines, node)
    return sources


def source_of_test(node: FunctionNode, lines: list[str], module: dict[str, str]) -> str:
    """The test's own source, plus the module-level helpers and constants it uses."""
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} - {node.name}
    return "\n".join([segment(lines, node), *(module[n] for n in sorted(used) if n in module)])


def test_files(project: Path, roots: tuple[str, ...] = TEST_ROOTS) -> list[Path]:
    """Test files under each root; a one-part root also matches inside the code folders."""
    # `tests` finds src/<feature>/tests/ too, as the edit guard matches it at any depth.
    files: set[Path] = set()
    for root in roots:
        base = project / root
        files |= {p for p in base.rglob("*.py") if p.name.startswith("test_")}
        if "/" in root:
            continue
        for code in APP_FOLDERS:
            files |= {
                p
                for p in (project / code).rglob("test_*.py")
                if root in p.relative_to(project).parts[:-1]
            }
    return sorted(files)


def reason_for(
    source: str, names: list[str], counts: bool, urls: list[str] | None = None
) -> str | None:
    for name in names:
        if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", source):
            return f"names {name}"
    if not counts or not COUNTS_QUERIES.search(source):
        return None
    if urls and not requests_any(source, urls):
        return None
    return cap_reason(source)


def find_pins(body: str, project: Path) -> list[str]:
    """One line for each existing test the body would change."""
    names = names_in(body)
    counts = any(is_query_code(path) for path in touched_paths(body))
    urls = url_prefixes(body)
    roots = tuple(r for r in TEST_ROOTS if not (app_only(body) and r.startswith(PLUGIN_ROOT)))
    found: list[str] = []
    for path in test_files(project, roots):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        lines = text.splitlines()
        module = module_level_sources(tree, lines)
        relative = Path(os.path.relpath(path, project)).as_posix()
        for node in test_nodes(tree):
            reason = reason_for(source_of_test(node, lines, module), names, counts, urls)
            if reason is not None:
                found.append(f"- `{relative}::{node.name}`: {reason}")
    return found


HIT = re.compile(r"^- `(?P<path>[^`:]+)::(?P<test>[^`]+)`")


def unlisted(body: str, lines: list[str]) -> list[str]:
    """The hits whose test name or test file name the body does not already name."""
    named = set(BACKTICKED.findall(body)) | set(re.findall(r"[\w.]+", body))
    kept: list[str] = []
    for line in lines:
        match = HIT.match(line)
        if match is None:
            continue
        file_name = match["path"].rsplit("/", 1)[-1]
        whole = f"{match['path']}::{match['test']}"
        if not {match["test"], file_name, whole} & named and not any(whole in t for t in named):
            kept.append(line)
    return kept


def main() -> int:
    args = sys.argv[1:]
    only_unlisted = UNLISTED in args
    args = [a for a in args if a != UNLISTED]
    if len(args) != 1:
        print(f"Usage: pinned_tests.py [{UNLISTED}] <issue body file>")
        return 0
    try:
        body = Path(args[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"Cannot read the issue body: {error}")
        return 0
    lines = find_pins(body, PROJECT)
    if only_unlisted:
        missing = unlisted(body, lines)
        if missing:
            print("\n".join(missing))
        return 1 if missing else 0
    print("\n".join(lines) or NOTHING_FOUND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
