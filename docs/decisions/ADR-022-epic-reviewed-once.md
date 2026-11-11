# ADR-022: An epic is reviewed once

- Status: Accepted (amends ADR-021 points 2 and 4)

## Context

Reviewing every task pull request of an epic costs the owner one approval per task. The owner reviews once per epic, then releases.

## Decision

1. **The epic branch integrates.** Every task of an epic starts from `origin/epic/<N>-<slug>` and opens a normal pull request into it.
2. **The tick merges tasks into it** without an owner comment, when the pull request is green, `pr:ready-for-review`, has its verify report linked and no open change request; one merge per epic branch per tick. Its issue gets `agent:in-epic` and stays open. A dependency inside the epic is met by that label.
3. **One pull request per epic into `main`.** When every open task of the epic has `agent:in-epic`, the tick opens one pull request from the epic branch into `main`, with one `Closes #` line per task and for the epic. It is the only review of the epic and merges on the owner's approval comment (ADR-016).
4. **A review fix on the epic pull request** is a loop run that commits and pushes to the epic branch.
5. **Tests of an earlier task.** An existing test means a test on `main`. A later task of the epic may change a test that an earlier task of the same epic added, when its ACs need it, and says so in its pull request. The epic pull request lists every test file a task changed.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Where task pull requests of an epic go | Into the epic branch, merged by the tick; one epic pull request into `main` | Each task into `main` with its own approval | One review per epic |
| When a task issue closes | When the epic pull request merges | When it reaches the epic branch | An issue closes only after a human checked the result |
| Owner comments on the epic pull request | A loop run fixes them on the epic branch | A new issue per comment | The same review route as every loop pull request |

## Consequences

- Task pull requests reach the epic branch without a human review; the epic pull request is the review, and its diff is the sum of the tasks.
- A red task keeps the epic pull request from opening until the owner closes or fixes it.
