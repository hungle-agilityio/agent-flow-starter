# ADR-028: An issue assigned to a team member is that member's work; the loop leaves it alone

- Status: Accepted
- Date: 2026-11-12

## Context

On 2026-11-11 the owner asked how a team shares work through the Project and GitHub, and wanted a rule for picking up work by epic or by task assigned to a member. The loop built every open `agent:ready` issue and never read its assignees, so a member and the loop could build the same issue. Every issue is assigned to the owner by default, and the loop runs with the owner's login. The tick also ignored every pull request without the `<!-- work-queue -->` marker, so a member's pull request merged by hand into an epic branch never gave its task `agent:in-epic`, and the epic's later tasks would wait for ever. The Claude Code Project is private to the owner: members work from GitHub and their own Claude Code sessions with the repository's `CLAUDE.md` and `.claude/rules/`.

Spec `docs/specs/member-assignment/spec.md` (pull request #477); #478 (the tick and `.flow/loop/README.md`, pull request #483); #479 is this record and the Project rules.

## Decision

1. **Member.** A member is an assignee login other than the owner (`OWNER`, the loop's login). An issue's member is its first member assignee; when it has none, the first member of its open epic (`Part of the epic #N`, label `epic`). The task's own member wins over the epic's.
2. **The loop skips a member's issue.** The tick never starts, retries or counts as ready an issue whose member is set, and logs `issue-<N>: assigned to <login>; skipped`. An issue assigned only to the owner, or to nobody, is the loop's, as before.
3. **Claim, give back, hand off by assignee only.** `gh issue edit <n> --add-assignee @me` claims; `--remove-assignee @me` gives back, and the loop takes the issue at the next tick when it still has `agent:ready`; changing the assignee hands off. An epic is claimed the same way on the epic issue. No label changes. Only the owner's `agent:ready` hands an issue to the loop.
4. **A running build goes on.** Claiming an issue labelled `agent:running` or `agent:review` stops nothing; the tick logs it and notifies the owner once per issue and member.
5. **A member's pull request for an epic task goes into the epic branch.** It has `Closes #<n>`; the owner clicks Merge; the tick then gives the task `agent:in-epic`, so the epic's later tasks start and the one epic pull request opens as usual (ADR-022). The tick never merges, labels or comments on a pull request that is not a loop pull request. When the epic branch does not exist yet, the member creates it from `main` with exactly the name the tick uses (`.flow/loop/README.md`, `## Team members`).
6. **Members build by hand** with the same branch, test-first and pull request rules; the owner clicks Merge.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| How the loop knows a task is a member's | An assignee other than the owner | A new label `human:claimed` | GitHub's own assignee, no new label; issues assigned to the owner keep building |
| Whether a member assigned to an epic owns its tasks | Yes, tasks inherit; a task's own member wins | Only the task's assignee counts | The owner hands out work by epic or by task in one click |
| How a member claims, gives back and hands off | Only by changing the assignee; `agent:ready` stays | Assign and remove `agent:ready` | One step, and giving back needs no label from the owner |
| A member claims an issue the loop is building | The build goes on; the tick warns once | The tick stops the build | No lost build and no half-stopped state |
| Where a member's pull request for an epic task goes | Into the epic branch; the owner clicks Merge; the tick sets `agent:in-epic` | Into `main` after the epic merges | Members and the loop share one epic; the owner still reviews one epic pull request |
| Who creates the epic branch when a member takes an epic before the loop started any of its tasks | The member, from `main`, with the exact name the tick uses | The tick creates it for an open epic with a member | No new tick behaviour; the branch is missing only when no loop task of the epic has started |

## Consequences

- A member's claimed `agent:ready` task does not hold its files the way a running build does, so the loop may start another task that lists the same file; the member and the loop pull request then meet at merge time.
- The epic pull request's table shows `—` for a member's task, and its list of changed tests leaves out tests a member changed (`.flow/loop/epic_pull_request.py` reads loop pull requests only).
