# ADR-023: A loop build edits exactly the files its issue lists

- Status: Accepted (supersedes in part ADR-012, ADR-019 and ADR-020)

## Context

In loop mode `before-edit-check` refuses every guarded file: anything in a `.claude` or `.github` folder, `.mcp.json`, the flow (`.flow/`, `.claude-plugin/`), the gate files and an existing test under a `tests` folder (`checks.protected_test_dirs`). The loop should still build flow work, without opening its guards to everything.

## Decision

1. **Every issue is `agent:ready`.** `route_issue.py` prints the area label (`area:flow` or `area:app`) and `agent:ready` for every issue whose paths stay inside the repository; a path outside it is not routed.
2. **The build edits what its issue lists.** For each build the tick writes `allowed-edits` in the run folder (every path of `## Files likely touched` and of `## Existing tests that change`) and starts `claude -p` with `FLOW_ALLOWED_EDITS`. `before-edit-check` allows a listed path even when it is guarded. A guarded path that is not listed is refused.
3. **Some things stay refused, even when listed:** a path inside `.git/`, and an edit of `settings.json` or `settings.local.json` in a `.claude` folder that changes `disableAllHooks`, `enabledPlugins`, `extraKnownMarketplaces`, `hooks` or `permissions.deny`. When the hook cannot work out the result, it refuses.
4. **The owner sees what touches the flow.** When the tick first labels a loop pull request `pr:ready-for-review`, it adds `## Guard files changed` above `Closes #`; the epic pull request gets the same. A non-empty list adds ` (changes guard files)` to the ntfy message.
5. **An issue lists every file it will change, guarded ones included.**

## Exception: .claude/

Claude Code's built-in safety check treats every file under a `.claude` folder as sensitive; in `claude -p` nobody can approve it, so the edit is denied even with an allow. An issue that changes a file under `.claude/` is built by hand through the Mac mini (interactive session, the owner clicks Merge) and gets no `agent:*` label. `route_issue.py` warns about such a path.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Scope | The loop builds everything but edits only listed files | Open every guarded file; build flow work by hand | Keeps the safety net |
| Settings that turn guards off | Always refused | Caught in review | A build could switch off its own hooks mid-run |
| Review | `## Guard files changed` in task and epic pull requests | Nothing extra | The owner sees at once what touches the flow |

## Consequences

- Flow work goes through the loop like app work, with the same verify report and review.
- The guard rules are written twice: in `.flow/plugin/hooks/before-edit-check.py` and in `.flow/loop/epic_pull_request.py`. A change to one is copied to the other.
