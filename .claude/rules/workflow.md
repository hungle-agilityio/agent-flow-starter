# Workflow: difficulty and gates

`agent-flow:analyst` rates every issue after the reporter's questions are answered. The rating decides the steps.

| Difficulty | Typical issue | Plan | Reviewer sub-agent | Learn |
|---|---|---|---|---|
| Easy | One layer, clear rule, a few lines | skip | no | skip |
| Medium | Several layers or one new rule | `/agent-flow:plan` | only if a trigger below applies | optional |
| Hard | New feature, migration, cross-cutting rule, unclear scope | `/agent-flow:plan`, detailed, maybe split | yes | yes |

Every loop build also runs `/code-review` on its diff before the pull request, whatever the difficulty: level medium, or level high plus the reviewer sub-agent when the branch changed a sensitive path (`paths.review_sensitive` of the flow config, `.flow/flow.toml`). It fixes or dismisses each finding in at most two rounds and reports them under `## Code review` in the pull request (ADR-029).

## Triggers (a Medium issue gets the reviewer when it touches)

- Rounding, averages or any number the business reads
- Pagination, ordering or filters
- Time zone or dates
- Queries on a list or dashboard (N+1 risk)
- Migrations or data changes
- Anything that handles secrets, input from users or external services
- A sensitive path (`paths.review_sensitive`): then the reviewer runs at any difficulty, with `/code-review` at level high

## Gates

- **Gate 1 (human check, after `/agent-flow:plan`):** Claude shows the plan and stops. The user reads it and says OK or asks for changes. Do not implement before that answer.
- **Gate 2 (human check, after `/agent-flow:verify`):** Claude reports the evidence (lint, types, tests, issue checks, review findings) and stops. The user checks the result, in the running app when the issue is visible, and says OK or asks for changes. Claude does not commit, `/agent-flow:learn` or move on before that answer (loop mode is the exception, see Modes). Tests that belong to open bug issues are expected to fail; say so.
- **Gate 3 (before push, issue or pull request):** the user approves that exact item.

Gates 1 and 2 are always a human decision, never assumed (in loop mode the label and the report are that decision). Gate 2 applies to every difficulty. Easy issues also stop for the human check after `/agent-flow:test`.

## Team principles

These apply to every helper and to the main assistant.

1. The AI never changes the requirement. What an issue asks for is changed only by the user, in the issue. Exception: the technical self-fix of a loop build, within its limits (`knowledge/decisions/ADR-024-loop-self-fix.md`).
2. The AI never widens the scope. An idea beyond the approved plan is raised and written down, not built.
3. The reviewer does not rely on the implementer's reasoning. It works out what is correct from the issue, the rules and the code, then compares with the diff.
4. No endless loops: at most two rounds of AI fix and review. If a finding is still open after the second round, the work stops and a human decides.

## Guardrails

These hold in every mode.

- **Archive, do not delete:** move to an archive or rely on git history. Never delete a file or data that the user did not ask to delete.
- **Verify, then close:** an issue is closed only after the build and the tests pass and a human checked the result. An issue that cannot be finished is released back, never closed.
- **Write down why:** a removal or a reversal is recorded, with its reason and date, in "Removed, and why" in `.claude/CLAUDE.md` or in a decision record.
- Never force-push, never skip the checks (`--no-verify`), never reset hard. Commit messages are written from the real diff.

## Modes

- **Loop mode** (`agent-flow:work-queue`, ADR-008, ADR-009): the label `agent:ready` is Gate 1; the report is Gate 2, read after the work; the loop has already pushed and opened the pull request. A `risk:high` issue stops after the plan with the label `agent:plan-review`; the owner's approval of that plan, given in the Project, is Gate 1 of the build (ADR-027). The loop skips an issue assigned to a team member (any login other than the owner), directly or through its epic (ADR-028). Each epic → main pull request gets one epic review before it is marked ready for the owner: the tick starts a run that reviews the whole epic with `/code-review` at level high, fixes in one round and leaves the rest in one `## Epic review` comment (ADR-029). The owner may run ultrareview by hand on any pull request; the loop never starts it. Open points are decided and reported once, never asked mid-run. Claude builds never merge; the tick merges on the owner's approval comment (ADR-016), or the owner clicks Merge on GitHub.
- **Member work** (ADR-028): a member builds the issue by hand with the same branch, test-first and pull request rules; for a task of an epic the pull request goes into the epic branch with `Closes #<n>`; the owner clicks Merge.
- Whatever the mode, the guardrails above hold. Gate 3 holds too, except in loop mode for the loop's own issue branch and pull request (ADR-009).

## Rules of the flow

- Tests first: write or update the test that shows the problem, then the code.
- The implementer builds only what the approved plan says. A change of scope goes back to `/agent-flow:plan`.
- **grill-me before the plan (proposed, never automatic):** after `/agent-flow:understand`, if the issue is Medium or Hard, or any decision is still open, Claude says how many decisions are open and asks whether to run `agent-flow:grill-me` before `/agent-flow:plan`, then waits. Only the user can skip it. Easy issues do not get the question.
- One branch and one issue at a time.
- Review happens locally before the pull request; on GitHub the checks run and a human reviews and merges.
