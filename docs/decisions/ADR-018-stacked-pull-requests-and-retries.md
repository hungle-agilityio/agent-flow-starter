# ADR-018: Stacked pull requests, retries, no pull request limit

- Status: Accepted (supersedes the pull request cap of ADR-009, ADR-012 and ADR-014)
- Date: 2026-11-04

## Context

Overnight the loop stopped for three reasons. A task that depends on another waited until the owner merged the other pull request. One failed build (`agent:failed`) stopped its task until the owner woke up. With 10 open pull requests the tick started nothing more. Spec `docs/specs/overnight-loop/spec.md`; issues #149 (retries), #164 (no limit), #163 (this record and the skills) and #165 (stacked starts in the tick).

## Decision

1. **Stacked pull requests.** An issue whose dependencies are all met except exactly one, #P, starts when #P has an open, non-draft loop pull request #Q that is `pr:ready-for-review` with every check green. The build branches from #Q's branch and opens its pull request into that branch, with the line `Stacked on #<Q> (merge that one first).` above `Closes #N`. Chains are allowed. The tick never merges a pull request whose base is not `main`; after the parent merges, the child's base becomes `main` and it is a normal loop pull request. A parent closed without merge sets its children `pr:blocked`. A change to the parent after the child started does nothing to the child until the parent merges.
2. **Retries.** A failed issue is retried up to 3 times, each from a fresh branch. A transient end (timeout, no exit code, an error code, no `Artifact` tool) is retried at the next free slot; a build that stopped itself only after `main` or the parent pull request moved. After the third retry one message tells the owner. The plan limit is not a failure.
3. **No pull request limit.** Only `AGENT_CONCURRENCY` and the other start rules limit the builds.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Retry of `agent:failed` | Up to 3 retries from a fresh branch: transient ends at once, a self-stopped build only when `main` or the parent moved; then notify | 3 retries whatever changed; once only (#149) | Real failures so far were deterministic (#132, #149); a retry with nothing changed repeats them and spends the 5-hour plan |
| Q2. When a dependent task starts early | Exactly one unmerged dependency whose loop pull request is `pr:ready-for-review` with green CI; chains allowed | Several unmerged parents; as soon as the parent has a pull request | The child builds on checked code and never merges two branches |
| Q3. Base of the child pull request | The parent's branch; never merged while its base is not `main` | Base `main` | One task, one small diff to review; the base guards the merge order |
| Q4. Parent changed in review, or closed | No extra sync; after the parent merges the update from `main` takes over; parent closed -> child `pr:blocked` | Sync the child on every parent commit | Reuses existing steps and permissions (`git merge origin/main` only) |
| Q5. Pull request limit of 10 | Removed in code | `AGENT_WAITING_CAP` in `agent.env` | The owner's request; builds stay limited by `AGENT_CONCURRENCY` |

## Consequences

- Many pull requests can wait at once; the owner reviews them in order, parent first.
- `work-queue` and `create-pull-request` accept a base other than `main` only for a stacked build.
- No new git permission: the child branches from the detached parent commit with `git switch -c`.
