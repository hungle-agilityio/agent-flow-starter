# ADR-034: Dependencies are read anywhere; the next tick heals a failed issue

- Status: Accepted
- Date: 2026-11-17

## Context

The tick read `Depends on #N` and `Part of the epic #N` only at the start of a line. An epic task written as `Part of the epic #104. Depends on #107.` on one line looked independent, so the tick started it before its base task and the build failed. A build that stopped on a decision (`needs-decision`) or was stopped kept `agent:failed` until the owner answered, and ADR-024 allowed one technical self-fix per issue only, so one open question blocked the queue. The owner wants a task never to run before its base task and the flow never to wait for the owner. Spec: `docs/specs/depends-heal/spec.md`.

## Decision

1. **Dependencies are read anywhere.** `Depends on` and `Part of the epic` are read anywhere in a line (case-insensitive, word boundary); every `#N` after `Depends on` up to the end of that line is a dependency, and `Depends on: none` means none. `route_issue.py` prints the dependencies it read and refuses (`NOT ROUTED`, exit 1) an issue with an unreadable `Depends on` line, or an epic task with no `Depends on` line at all. An epic task has its own line `Depends on #<n>.` or `Depends on: none` under `Part of the epic #N`, and the issues of an epic are created base tasks first.
2. **A build waits for an unmet base task.** Before planning, a build checks every `Depends on #M` of its issue: met when #M is closed, or, for a task of an epic, when #M has `agent:in-epic`. When one is not met, the build writes no code, releases the issue to `agent:ready` with one comment marked `<!-- work-queue -->` and `<!-- waiting -->`, and ends without a pull request. The tick treats this as a normal end: no `agent:failed`, no failure record, no retry or heal counted, no ntfy message.
3. **The next tick heals a failed issue.** An `agent:failed` issue whose failure is a decision, a stop, or a transient failure that used its 3 retries gets a heal run at the next tick, before ready issues, at most 3 heal runs per issue. A heal run reads the issue, the stop comments, the spec and the `Decisions` comment, picks the recommended option or the narrowest reading that meets every AC, edits the issue body, posts one comment marked `<!-- work-queue -->` and `<!-- heal -->` with a `## Decisions` table, and sets `agent:ready`. It writes no code and pushes nothing. Every heal is listed under `## Self-decided fixes` in the pull request, next to the self-fixes of ADR-024.
4. **Forbidden for a heal run** (spec AC12): deleting files or data; a migration or any change to stored data; anything about security, secrets, permissions or sign-in; a setting or file that turns a guard off, or a file under `.claude/`; deleting, skipping or weakening a test beyond the new number an AC needs; a query count that grows with the data. When the only way forward is forbidden, the heal run marks the issue `<!-- needs-owner -->` and keeps `agent:failed`; the tick starts no more heal runs for it and sends one ntfy message. After the 3rd heal a new failure goes to the owner the same way. The rest of the queue goes on in both cases.
5. **Exceptions to the team principles.** This is an exception to team principle 1: a heal run may change an issue within spec AC11 and AC12. It is an exception to team principle 4: 3 heal rounds per issue, each followed by one build.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 What a heal run may decide | Everything except the forbidden list (AC12) | Everything; technical only (ADR-024 as today) | The flow is not blocked for most stops, and steps that cannot be undone still go to the owner |
| Q2 Heal rounds per issue | 3, then park with one ntfy; the rest of the queue goes on | 1; no limit | Same as `RETRIES = 3`; no endless loop and no burnt 5-hour plan |
| Q3 Task started before its base task | The build checks and releases to `agent:ready` with a waiting comment, no failure | Also read the spec's `tasks.md` from the tick | The parser fix and the posting check cover it; `tasks.md` T-numbers are not issue numbers and its folder differs per layout |
| Q4 Starter and O - Living | Both, one pull request each through the Mac mini after T1 to T5 merge | Hotfix O - Living now; only this repository and the starter | #105 and #106 were fixed by hand, so O - Living is not blocked now |

## Consequences

- A `needs-decision` stop no longer waits for the owner; the owner sees each heal in the `## Self-decided fixes` section and in the heal comment.
- An issue may change without the owner, always from a comment marked `<!-- heal -->`, and never in the forbidden cases.
- `.claude/` files stay a hand-built exception (ADR-023); a heal run never touches one.
- The owner restarts a parked issue by adding `agent:ready`; the heal count is not reset.
