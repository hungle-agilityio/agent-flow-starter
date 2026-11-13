# ADR-022: An epic is reviewed once

- Status: Accepted (amends ADR-021 points 2 and 4 for epics)
- Date: 2026-11-09

## Context

Under ADR-021 every task pull request of an epic goes into `main` and needs its own approval: epic #348 needed three. The owner wants the tasks of an epic to finish without a review each, to review once per epic, and then to release. Spec `docs/specs/epic-review-once/spec.md`; issues #364 (the tick merges tasks into the epic branch), #366 (one pull request per epic into `main`) and #365 (this record and the skill).

## Decision

1. **The epic branch integrates.** Every task of an epic, with or without dependencies, starts from `origin/epic/<N>-<slug>` and opens a normal pull request into it, not a draft and with no `Stacked on` line.
2. **The tick merges tasks into it.** No owner comment is needed: a task pull request goes in when it is green, `pr:ready-for-review`, has its verify report linked and has no open change request, one merge per epic branch per tick. Its issue gets `agent:in-epic` and stays open. A dependency inside the epic is met by that label.
3. **One pull request per epic into `main`.** When every open task of the epic has `agent:in-epic`, the tick opens one pull request from the epic branch into `main`, with one `Closes #` line per task and for the epic. It is the only review of the epic and merges on the owner's approval comment (ADR-016).
4. **A review fix on the epic pull request** is a loop run that commits and pushes to the epic branch. This is the one case where a build pushes to `epic/*`.
5. **Tests of an earlier task.** An existing test means a test on `main`. A later task of the epic may change a test that an earlier task of the same epic added, when its ACs need it, and says in its pull request which test changed, how, and for which AC. The tick lists every test file changed by a task in the epic pull request, read from GitHub (#380, after #375 stopped on a query limit set by #373).
6. Tasks without an epic keep ADR-018. ADR-021 point 1 (`main` goes into the epic branch each tick), point 3 (conflicts) and the deletion of the branch in point 4 stay.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Where task pull requests of an epic go | Into the epic branch, merged by the tick; one epic pull request into `main` | Each task into `main` with its own approval (ADR-021, chosen 2026-11-09 02:49Z) | The owner wants to review once per epic and let the tasks run on their own |
| Q2. When a task issue closes | When the epic pull request merges (`Closes #` lines), label `agent:in-epic` until then | Closed by the tick at the merge into the epic branch | An issue is closed only after a human checked the result (workflow guardrail) |
| Q3. Owner comments on the epic pull request | A loop run fixes them on the epic branch | A new task issue per comment | The same review route as every loop pull request |
| Q4. Who builds this flow change | By hand on the Mac mini, the owner clicks Merge (as #352 to #355) | `agent:ready` issues for the loop | The loop would build its own merge rules; the epic test waits for it |

## Consequences

- Task pull requests reach the epic branch without a human review, so the epic pull request is the only review. Its diff is the sum of the tasks.
- A red task, or one that failed three times, keeps the epic pull request from opening until the owner closes or fixes it.
