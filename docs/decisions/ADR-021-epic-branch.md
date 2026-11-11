# ADR-021: One shared branch per epic

- Status: Accepted
- Superseded in part by ADR-022 (points 2 and 4)

## Context

A task that waits for two or more unreviewed pull requests would stop until the owner reviews them. Tasks of one epic should go on while reviews wait.

## Decision

1. **One branch per epic.** A task belongs to an epic when its issue body has `Part of the epic #<N>` and #N is an open issue labelled `epic`. The tick keeps `epic/<N>-<slug>`, made from `main`, merges `main` into it each tick, and merges the epic's task pull requests into it (merge commits, never a rebase).
2. **Tasks build on it.** A ready task of an epic starts from `origin/epic/<N>-<slug>` (see ADR-022 for the pull request it opens).
3. **Conflicts.** A pull request that does not merge cleanly into the epic branch gets `/redo merge origin/epic/<N>-<slug> into this branch and fix the conflict`; the loop fixes it as for `main`.
4. **Clean up.** The tick deletes the epic branch once the epic is closed and no pull request is based on it.
5. A task without an epic and with one open dependency is stacked on that dependency's branch, as before.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Base of an epic task | The epic branch | `main` from the start | Tasks build on each other's checked code |
| What goes into the epic branch | Green, `pr:ready-for-review` pull requests, again after each fix | Every pull request as soon as it opens | Tasks build on checked code |
| Conflict with the epic branch | The loop merges the epic branch into the task branch and fixes it | The owner fixes it | The owner does not fix conflicts by hand |

## Consequences

- The tick pushes and deletes `epic/*` branches; builds push to them only for a review fix on the epic pull request (ADR-022).
- A review fix on a parent reaches its children through the epic branch at the next tick.
