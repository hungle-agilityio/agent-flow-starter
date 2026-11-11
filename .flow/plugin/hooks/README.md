# Hooks: guards that run before shell commands, and one formatter after edits

A `before-` hook runs before a tool call. Exit code 2 blocks it and Claude gets the reason. An `after-` hook runs once the tool is done; it cannot block, its exit code 2 only sends a line back to Claude. Anything that must always hold is a hook or a permission rule, not a sentence Claude reads.

| Hook | Refuses |
|---|---|
| `before-github-command-check` | `gh`, `git`, `curl` and `ssh` commands that reach a GitHub repository other than `project.repo` of the project's `.flow/flow.toml`; commands that manage repositories, accounts or secrets; reading or printing the token (`GH_TOKEN`, `printenv`, `env`); a force, delete, all-branches or `main` push in any mode; `gh api` writes that merge or move a ref; and, outside loop mode, a push, a pull request or a merge without asking you. A merge must be exactly `gh pr merge <n> --merge --match-head-commit <sha>`, alone in the call, for an open same-repository issue branch into main whose head is that commit. In loop mode every merge is refused. `gh api` asks outside loop mode; in loop mode only the review marks of ADR-016 are answered `allow` (a POST of an `eyes`, `rocket` or `confused` reaction on a comment of this repository, a reply to a line comment, the `reviewThreads` read and the `resolveReviewThread` mutation), and any other call to those endpoints is refused. When a command cannot be split into words (an apostrophe or several lines in a body), it scans the raw text for repository names and `-R` values instead: `gh issue` and `gh label` may then run, `gh api`, `gh pr create`, `gh pr merge`, a push and the other `gh` and `git` network commands are refused |
| `before-commit-check` | Staging the database file, secrets files and caches (also with `--force`); a commit with those staged, with a secret-like string in the staged lines, with an attribution line in the message (Co-Authored-By, Generated with), on `main`, or while lint or types fail |
| `before-artifact-publish` | Publishing a file under `out/verify/` with the Artifact tool unless the sharing gate allows it (masking `clean`, standing approval `on`, size under the limit) |
| `before-edit-check` | Loop mode only (`FLOW_LOOP=1`), letter case ignored: editing `.github/`, `.claude/` (a new file in `knowledge/` is allowed), the plugin source (`plugins/` and `.claude-plugin/` at the git root), `.mcp.json`, `pyproject.toml`, `uv.lock`, `conftest.py`, and tests already on main (unless `ALLOW_TEST_EDIT=1`, or the file is one of the `## Existing tests that change` of the issue, passed by the tick in `FLOW_TEST_EDITS`); fails closed |
| `before-finish-check` | Loop mode only: stopping while lint, types or tests fail, or a pull request round that added commits without republishing a report built at HEAD (with screenshots when the issue has `needs-ui`) (a second stop is allowed) |
| `before-skill-script-allow` | Nothing (it allows): answers `allow` for one plain `python3 [-I]` or `uv run python` call of a `.py` file at `skills/<skill>/` of this plugin, after resolving its real path, so the loop runs the flow's scripts without a prompt. In loop mode, a command that names such a script in any other form (a variable, `;`, a pipe, `2>&1`) is denied with the plain form as the reason, since nobody can answer a prompt; any other command is left to the permission rules. No rule can name these scripts safely, since the plugin's path holds its version (README, "Probe") |
| `after-edit-format` | Nothing (it fixes): after Edit or Write on a `.py` file of the project, runs `ruff check --fix` then `ruff format` on that file only, with the settings of `pyproject.toml` (migrations excluded). An unused import is kept (F401 is not fixed), since it is often used only in the next edit. On a syntax error or a missing ruff the file stays as written and Claude gets one line; the edit is never undone. A file that was not formatted before is formatted whole the first time it is edited |

All `before-` hooks fail closed: if a hook cannot check a command that looks relevant (or, in loop mode, an edit), it is blocked. Their tests are in `tests/` and run in the automatic checks.

## Where they run

The hooks belong to the `agent-flow` plugin and are registered in `hooks.json`; a project turns them on with `enabledPlugins` in its `.claude/settings.json`. They read the project, not their own folder: `.flow/flow.toml` and `.flow/loop/flow_config.py` under `$CLAUDE_PROJECT_DIR` (falling back to the `cwd` of the call), and the allowed repository is `project.repo` of that file. Run their tests from the project folder (`uv run pytest .flow/plugin/hooks/tests --no-cov` in Agent flow starter); `tests/conftest.py` stops with a clear message elsewhere.

## What is NOT a hook

Enforced by `permissions` in `settings.json`: file edits only under `src/`, `starter/` and `out/` (the verify report) without asking, so a loop build is refused anywhere else; force-push, `--no-verify`, `reset --hard`, approving or commenting on a pull request, deleting an issue or a repository, reading `.env` files and `*DO-NOT-OPEN*` files, a rebase (asks). The narrow `gh api` allow rules for the review marks only spare the prompt; the hook decides. Text and review only (judgement, not a command): deleting data nobody asked to delete, inventing facts, widening the scope, changing the requirement.

## Limits

- `before-artifact-publish` was seen allowing a real publish (`out/artifact-publish.log`); a live `blocked` case was never triggered on purpose.
- A hook sees only the shell commands that Claude runs. It does not see what a script run by Claude does inside, and it does not see commands the user types.
- A change of settings or hooks needs a new session to take effect.
- The secret scan knows a few token shapes (GitHub, AWS, Slack, `sk-`, private keys). It is a net, not a proof.
- The regex hooks do not see every way of writing a command (`bash -c '...'`, `command git ...`); the permission list covers most of it because those forms match no allow rule. Never run the loop in a mode that skips permission prompts.
