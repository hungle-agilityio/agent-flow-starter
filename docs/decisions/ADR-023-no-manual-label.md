# ADR-023: No agent:manual; a loop build edits the files its issue lists

- Status: Accepted (supersedes in part ADR-012, ADR-019 and ADR-020)
- Date: 2026-11-10

## Context

In loop mode `before-edit-check` refused every guarded file: anything in a `.claude` or `.github` folder, `.mcp.json`, the plugin source (`plugins/`, `.claude-plugin/` at the git root), the gate files and an existing test under `checks.protected_test_dirs`. `route_issue.py` labelled an issue that touched one of them `agent:manual`, or `agent:needs-permission` when a path had no `Edit(...)` allow rule. The loop skipped both, so flow work was built by hand in an interactive session. The owner wants every issue to be `agent:ready`, so the loop builds everything. Spec `docs/specs/no-manual-label/spec.md`; issues #386 (hook and routing), #387 (tick) and #388 (this record and the rules).

## Decision

1. **Every issue is `agent:ready`.** `route_issue.py` prints the area label and `agent:ready` for every issue whose paths stay inside the repository; a path outside it is not routed. `agent:manual` and `agent:needs-permission` are no longer given or read. Labels already on GitHub stay.
2. **The build edits what its issue lists.** For each build the tick writes `allowed-edits` in the run folder (every path of `## Files likely touched` and of `## Existing tests that change`) and starts `claude -p` with `FLOW_ALLOWED_EDITS`. `before-edit-check` allows a listed path even when it is guarded and answers allow, so no `Edit(...)` rule is needed. A guarded path that is not listed is refused as before.
3. **Some things stay refused, even when listed:** a path inside `.git/`, and an edit of `settings.json` or `settings.local.json` in a `.claude` folder that changes `disableAllHooks`, `enabledPlugins`, `extraKnownMarketplaces`, `hooks` or `permissions.deny`. When the hook cannot work out the result, it refuses.
4. **The owner sees what touches the flow.** When the tick first labels a loop pull request `pr:ready-for-review`, it adds `## Guard files changed` above `Closes #`; the epic pull request gets the same for its branch against `main`. A non-empty list adds ` (changes guard files)` to the ntfy message.
5. **An issue lists every file it will change, guarded ones included**, because the build may edit only those.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 Scope | The loop builds everything, but edits only the files the issue lists; other guarded files stay refused | Open everything (hook guards nothing); only existing tests | Drops the label and keeps the safety net |
| Q2 Settings that turn guards off | Always refused, even when listed | Allowed, caught in review | A build could switch off its own hooks mid-run |
| Q3 `agent:needs-permission` | Removed too; the hook allows the listed files | Keep it | Same cause, same fix |
| Q4 Review | `## Guard files changed` in task and epic pull requests | Nothing extra | The owner sees at once what touches the flow |
| Q5 First build | By hand once on the Mac mini (owner clicks Merge), with a probe of pushing a workflow file | Split for the loop | The loop cannot unlock its own guards |
| Loop and .claude/ | Hand build, no agent label | Probe hook allow further | Built-in safety check; probing needs the owner to type commands |

## Exception: .claude/ (2026-11-10)

Claude Code's built-in safetyCheck treats every file under a `.claude` folder as a sensitive file. In `claude -p` nobody can approve it, so the edit is denied even with an allow rule and with the hook's allow (issue #392, `decision_reason_type` `safetyCheck`). An issue that changes a file under `.claude/` is built by hand through the Mac mini (interactive session, the owner clicks Merge) and gets no `agent:*` label. `route_issue.py` warns about such a path. The rest of this record (`.github/`, the plugin, the gate files, existing tests) stands.

## Workflow push probe

On 2026-11-10 the Mac mini pushed a throw-away branch `task/probe-workflow-push` that added one comment line to `.github/workflows/checks.yml`, with the remote and credentials the loop uses (`origin`, `git@github.com:hungle-agilityio/agent-flow-starter.git`, SSH). GitHub accepted it (`* [new branch]`), and the branch was deleted at once with `git push origin --delete` (`- [deleted]`); no pull request was opened. A loop build can push a workflow change; the token needs no Workflows permission for `git push` over SSH.

## Consequences

- Flow work goes through the loop like app work, with the same verify report and review. #386 to #388 were the last tasks built by hand.
- A build can change its own rules, hooks and tests when its issue lists them. The safety net is the list itself, the keys of point 3, the Guard files section and the owner's review.
- The guard rules live once, in `.flow/plugin/hooks/guarded_paths.py`; the hook and `.flow/loop/epic_pull_request.py` read it, and `flow.toml` is guarded (#486, 2026-11-12).
