# ADR-019: The flow reads .flow/flow.toml; a new project is bootstrapped by copy and rename

- Status: Accepted
- Superseded in part by ADR-023 (no agent:manual)
- Date: 2026-11-05

## Context

The owner wants to run the same flow (Project threads, the tick, the hooks, the skills) on new projects without hand-editing every script. The project values were constants spread over `.flow/loop/agent_tick.py`, `.flow/loop/release.py`, the shell scripts, the hooks and `route_issue.py`: the repository, the owner, the app folder, the display name, the state folder, the check commands and the protected test folders. Spec `docs/specs/flow-bootstrap/spec.md`; epic #192, issues #193 (config file), #194 (tick and scripts), #196 (hooks and `route_issue.py`, this record) and the bootstrap task.

## Decision

1. **One config file.** `.flow/flow.toml` is committed with today's Agent flow starter values and read by `.flow/loop/flow_config.py` (`load()`, standard library `tomllib`). A missing key, an unknown key or a wrong type stops with the file and the key in the message; no value has a default in code. `FLOW_CONFIG` names another file, for tests.
2. **The guards follow the config.** `before-finish-check.py` runs `checks.commands` in order. `before-edit-check.py` protects existing tests under every folder of `checks.protected_test_dirs`, with the same message and `ALLOW_TEST_EDIT=1` escape. Each hook resolves `.flow/flow.toml` from the app folder of its own file, so it works in a loop worktree. When the file cannot be read in loop mode, the hook blocks (fail closed). `route_issue.py` strips `project.app_dir` from the paths of "Files likely touched"; `.` means no prefix.
3. **Loop mode.** `FLOW_LOOP=1` is loop mode in every hook; the tick sets both, so today's hooks, tests and docs keep working.
4. **The GitHub guard keeps its own file.** `github-allowed-repo.txt` stays the source of the guard; a test fails when its repository line differs from `project.repo`.
5. **Bootstrap by copy and rename.** `.flow/loop/bootstrap.py` copies the generic flow listed in `.flow/loop/bootstrap_manifest.toml` into a clone of a new repository, writes its `.flow/flow.toml` from six values, replaces the Agent flow starter names in the copied files, writes stubs for the project-specific rules, creates the labels and `agent.env`, and prints the steps only the owner can do. It never commits, pushes or overwrites a file.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Stack of the new project | Any app stack; flow tooling stays Python with `uv`; copy only the generic flow plus stubs | Python/Django only, copy the Django parts | The Django parts are Agent flow starter's; check commands come from config |
| Q2. Config file | `.flow/flow.toml` committed with today's values; a missing key stops with its name | Defaults in code, file only overrides | One visible source; no silent Agent flow starter defaults in a new project |
| Q3. Values bootstrap asks | 6: repo, owner, app folder, display name, slug, ntfy topic; the rest defaults in `flow.toml` | Also ask stack and check commands | Short prompt; defaults are edited later in one file |
| Q4. Effect on the target | Writes files, labels and `agent.env`, prints steps; never commits or pushes; `--dry-run` | Commit and push to `main` | The first push is checked by a person; no push to `main` by a script |
| Q5. Two loops on one Mac mini | Fully separate per slug; no shared limit; the steps say keep the total at 2 to 3 | A shared limit across loops | Smaller change; a shared limit can come later |
| Q6. `.claude/` work | One `agent:manual` task (#196) | Several manual tasks | One interactive session on the Mac mini |
| Q7. After the merge | Shorten section 4 of the Notion page to "run bootstrap.py with these 6 values"; no real project in this epic | Bootstrap a sample repository end to end | Keeps the epic small; the first real project is the end-to-end test |
| Where the config lives | `.flow/flow.toml` | `flow.toml` at the app root | The loop may edit `.flow/loop/**`, so the config and tick tasks can be `agent:ready` |
| Skills naming the repository | Renamed at copy time by bootstrap | Editing every skill to use a placeholder | Fewer `.claude/` edits; the GitHub guard and allow rules keep exact repository names |
| Loop-mode variable | `FLOW_LOOP=1` | A project-specific name | One name for every project |

## Consequences

- With today's `.flow/flow.toml`, Agent flow starter behaves as before: same checks, same protected tests, same messages.
- A broken or missing `.flow/flow.toml` stops loop builds at the first edit of a test file and at the finish check; interactive sessions are not affected.
- `route_issue.py` still protects `src/tests` itself when it labels an issue; a project with other test folders gets the right labels only after that check reads the config too.
