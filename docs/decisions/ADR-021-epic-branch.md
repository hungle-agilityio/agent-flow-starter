# ADR-021: One shared branch per epic

- Status: Accepted (amends ADR-018 point 1 for tasks of an epic)
- Status: Superseded in part by ADR-022 (points 2 and 4, for epics)
- Date: 2026-11-06

## Context

ADR-018 starts a dependent task early only when exactly one of its dependencies is unmerged. A task that waits for two or more unreviewed pull requests stops until the owner reviews them. On 2026-11-06 #242 of the epic "reply to reviews" (#236) waited for PR #251 and PR #252, both green and ready. The owner asked that tasks go on while reviews wait. Spec `docs/specs/epic-branch/spec.md`; issues #262 (this record and the skills), #263 (the branch in the tick) and #264 (starting tasks on it).

## Decision

1. **One branch per epic.** A task belongs to an epic when its issue body has `Part of the epic #<N>` and #N is an open issue labelled `epic`. The tick keeps `epic/<N>-<slug>`, made from `main`, and merges into it (merge commits, never a rebase) every loop pull request of the epic that is open, not a draft, `pr:ready-for-review` and green; again after each review fix. It also merges `main` into it each tick.
2. **Tasks build on it.** A ready task of an epic whose unmet dependencies all have their pull request in the epic branch starts at once from `origin/epic/<N>-<slug>`. Its pull request goes into the epic branch, so the diff shows only the task's own changes, with `Stacked on #<P1>, #<P2> through epic/<N>-<slug> (merge those first).` above `Closes #<n>`. The tick never merges a pull request whose base is an epic branch; once those pull requests are merged into `main` it moves the base to `main`.
3. **Conflicts.** A pull request that does not merge cleanly into the epic branch gets `/redo merge origin/epic/<N>-<slug> into this branch and fix the conflict`; the loop fixes it as for `main` (ADR-015).
4. **Only `main` ships.** The epic branch is never merged into `main`; work reaches `main` only through each task's own reviewed pull request. The tick deletes the epic branch once the epic is closed and no pull request is based on it.
5. Tasks without an epic keep ADR-018 point 1 unchanged.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Base of a dependent task's pull request | The epic branch, then `main` once the dependencies are merged | `main` from the start | The diff shows only the task's own changes; the base guards the merge order |
| Q2. Which pull requests go into the epic branch | Only green and `pr:ready-for-review`, merged again after each review fix | Every pull request as soon as it opens | Tasks build on checked code |
| Q3. Conflict when merging into the epic branch | The loop merges the epic branch into the task branch and fixes it (`/redo`, ADR-015) | Leave it out, `pr:blocked`, tell the owner | The owner does not fix conflicts by hand |
| Q4. Which tasks use it | Tasks of an epic (`Part of the epic #N`) | Every dependent task | An epic is the unit of related work |
| Q5. Tasks without an epic and one open dependency | Keep the one-parent stacking of ADR-018 | Drop it and wait | It works and needs no shared branch |

## Consequences

- The tick pushes and deletes `epic/*` branches; builds never push to them.
- A review fix on a parent reaches its children only through the epic branch, at the next tick.
- An epic's tasks can pile up in review while builds go on; the owner reviews parents first.
- Added 2026-11-09 after PR #320 (#317) was merged into the epic branch with the Merge button: a stacked pull request stays a draft until the tick moves its base to `main` (GitHub disables Merge on drafts), and a pull request merged into an epic branch anyway gets a new pull request into `main` from the tick (spec `docs/specs/epic-close/spec.md`, #327, #329).
