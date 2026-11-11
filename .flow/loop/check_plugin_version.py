"""A change under the plugin folder needs a new version in its plugin.json.

Spec: specs/flow-risks/spec.md (AC1 to AC3), specs/project-layout/spec.md (AC14). CI runs it on
pull requests: `python <loop folder>/check_plugin_version.py <base> <head>`. The plugin folder is
`paths.plugin_dir` of the flow config, read from the app folder (`plugins/agent-flow/` in
Agent flow starter). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import subprocess
import sys
from pathlib import Path

try:
    from ops import flow_config
except ImportError:  # started as a script: its own folder is the first path entry
    import flow_config  # type: ignore[import-not-found,no-redef,unused-ignore]


def plugin_dir(config: flow_config.FlowConfig) -> str:
    """The plugin folder from the git root: paths.plugin_dir joined to project.app_dir."""
    joined = posixpath.normpath(posixpath.join(config.project_app_dir, config.paths_plugin_dir))
    return joined.removeprefix("./") + "/"


PLUGIN_DIR = plugin_dir(flow_config.load())
MANIFEST = PLUGIN_DIR + ".claude-plugin/plugin.json"
REPO_ROOT = Path(__file__).resolve().parents[2]


def git(repo: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return done.returncode, done.stdout


def version_at(repo: Path, rev: str) -> str | None:
    """The plugin version at a commit; None when the manifest is missing or unreadable."""
    code, out = git(repo, "show", f"{rev}:{MANIFEST}")
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return str(version) if version is not None else None


def plugin_changed(repo: Path, base: str, head: str) -> bool:
    code, out = git(repo, "diff", "--name-only", f"{base}...{head}")
    if code != 0:
        raise SystemExit(f"git diff {base}...{head} failed")
    return any(line.startswith(PLUGIN_DIR) for line in out.splitlines())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    if not plugin_changed(args.repo, args.base, args.head):
        return 0
    new = version_at(args.repo, args.head)
    code, fork = git(args.repo, "merge-base", args.base, args.head)
    olds = {version_at(args.repo, args.base)}
    if code == 0:
        olds.add(version_at(args.repo, fork.strip()))
    if new is not None and new in olds:
        print(f"{PLUGIN_DIR} changed but .claude-plugin/plugin.json still has version {new}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
