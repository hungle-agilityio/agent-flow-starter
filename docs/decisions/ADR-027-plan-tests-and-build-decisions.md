# ADR-027: A loop build shows its plan, gets its tests from a separate test author, checks the test matrix and records its decisions next to the spec

- Status: Accepted
- Date: 2026-11-12

## Context

Day 13 of the training ("Build") asks for plan mode first (approve the plan before any code), QA authoring the automated suite alongside the build, and the BA updating the spec as questions resolve. The check of 2026-11-11 found parallel isolated builds and one pull request per issue in place (ADR-014, ADR-015, ADR-023), but three gaps:

- The plan the `planner` writes inside a build was never shown or approved: no pull request had it, Easy issues skipped it, and nobody approved a plan before code, even on a `risk:high` issue.
- The ADR-026 test matrix was planned before the build and never checked after it: `work-queue` did not read `## Test matrix rows`, the verify report checked only the ACs, and the agent that wrote the code also wrote its tests.
- Decisions taken during a build (an open point taken from the spec, a self-fix, the owner's answer to a needs-decision stop, a change request) stayed in the issue or the pull request; no spec folder changed after its build.

Spec `docs/specs/build-trust/spec.md` (pull request #467); epic #468 with #469 (verify report axis, pull request #476), #470 (build steps, pull request #480), #471 (tick label, pull request #474), #472 (spec templates, pull request #475), merged to `main` by the epic pull request #481; #473 is this record and the Project rules.

## Decision

1. **Plan in every pull request.** The loop runs the `planner` for every difficulty (Easy gets three lines) and passes the plan to `draft_pr.py --plan`, which puts a `## Plan` section between What and Why.
2. **Plan stop for `risk:high`.** After planning, a `risk:high` build posts the plan as an issue comment (`<!-- work-queue -->`, `<!-- plan -->`), sets `agent:plan-review`, removes `agent:running` and ends with nothing pushed. The tick never starts an issue with `agent:plan-review` and notifies the owner once. The owner approves in the Project: a thread posts `lgtm` and moves the label back to `agent:ready`; the next run builds that plan. Any other owner comment after the plan makes the build plan again and stop again. This approval is Gate 1 of the build.
3. **A separate test author.** When the issue has `## Test matrix rows`, the `test-author` sub-agent reads only the issue, the rules and the code, and writes one failing test per `unit` or `integration` row before the `implementer` writes code. The implementer makes them pass and never deletes, skips or weakens them; a test that contradicts an AC may change only to match it. The test author's files are kept as a copy in `out/test-author/`, and the pull request lists every test that differs from that copy under `## Tests changed after the test author` (`draft_pr.py --tests-changed`), or `None.`
4. **The verify report checks the matrix.** The criteria file carries a `"matrix"` list, one entry per row. The report's `Test matrix` axis is `FAIL` when a row fails or has no test, which makes the verdict `FAIL` and opens no pull request; no matrix is `NOT APPLICABLE`.
5. **Build decisions next to the spec.** Each full-lane task lists `docs/specs/<feature>/decisions/T<k>.md` (NEW) in its files; its build writes there every decision it took (`From`: owner or build), or `No decision beyond the issue.`, and a change request that changes behaviour adds a line. `spec.md` links the folder under `## Decisions during build`. `spec.md` itself is not edited after Gate 1.
6. **Scope.** Issues created after this change. Existing specs, issues and pull requests stay as they are.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| How a `risk:high` build waits for plan approval | Plan as an issue comment, label `agent:plan-review`; the owner approves in the Project; the next build uses that plan | No stop (plan only in the pull request); a stop for every Medium and Hard issue | Approval before code where the risk is, without slowing the rest of the loop |
| Which pull requests show the plan | Every loop pull request; Easy gets three lines | Medium and Hard only | The owner always sees what the build meant to do |
| A matrix row with no passing test | Axis `FAIL`, verdict `FAIL`, no pull request | A warning only | The matrix is only worth something when it is checked |
| Who writes the tests from the matrix | A separate `test-author` sub-agent, before the code | The implementer, as before | Tests written from the requirement, not from the code |
| Where build decisions go | `docs/specs/<feature>/decisions/T<k>.md`, one file per task, in the build's pull request | Editing `spec.md` (tasks of an epic would share a file); a spec pull request per decision (self-fixes missed) | The spec folder stays current and parallel tasks never share a file |
| How the test author's tests are kept | A copy in `out/test-author/`, compared before the pull request | A separate commit "Add the failing tests" | The commit hook runs the type check, which fails on tests of code not written yet |

## Consequences

- A `risk:high` issue now needs the owner twice: once for the plan, once at review. The tick sends one notification when a plan waits.
- Every build runs one more sub-agent when the issue has matrix rows, so builds take a little longer.
- The rule that the implementer never weakens the test author's tests is checked by the reviewer and the `## Tests changed after the test author` section, not by a hook.
- `.claude/project-instructions.md` gains the decisions file in step 5, `agent:plan-review` in Status, and "Approve a plan"; the owner pastes the updated text into Project settings.
