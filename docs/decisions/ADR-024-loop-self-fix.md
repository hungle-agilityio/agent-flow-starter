# ADR-024: A loop build fixes technical stops itself

- Status: Accepted (an exception to team principle 1 of `rules/workflow.md`)
- Date: 2026-11-10

## Context

#375 and #397 stopped with `needs-decision`: an existing query-cap test was not listed in the issue, so no reading met every AC, and the tick never restarts that kind of stop. Epic #394 waited for a human until the owner edited #397 by hand; #399 was fixed by hand before its build for the same reason. `.flow/loop/pinned_tests.py` missed those tests (it did not know `django_assert_max_num_queries` or `CaptureQueriesContext`) and nothing ran it. The owner wants such problems caught before a build starts, and a loop that fixes the remaining technical stops itself. Spec `docs/specs/fail-fix/spec.md`; issues #406 (planning check), #408 (tick), #407 (build self-fix) and #409 (this record and the planning rule).

## Decision

1. **Catch it at planning.** Before an issue gets `agent:ready`, the Project thread runs `uv run python .flow/loop/pinned_tests.py --unlisted <body file>` and settles every hit: the test goes under `## Existing tests that change`, or an AC is reworded so the test stays unchanged. An epic's `tasks.md` keeps a `## Query budget` table.
2. **The tick warns the build.** Before an issue build it runs the same check and adds the unlisted tests to the prompt (#408).
3. **The build fixes technical stops itself** (`work-queue` step 4, Self-fix, #407). Technical means only:
   - an existing test pins a fixed number or a literal that an AC changes;
   - an unguarded file the plan needs is missing from the issue's files;
   - an AC can be met at no extra cost by a narrower technical reading;
   - a decision the issue leaves open has a recommended option in the spec.
4. **Limits.** A self-fix never deletes, skips or weakens a test beyond the new number the AC needs, never accepts a query count that grows with the data, never changes a text, page, business rule, permission, migration or data, and never adds a guarded file. One self-fix per issue; a second stop is a `needs-decision` stop for the owner.
5. **Everything is visible.** The self-fix edits the issue and posts a comment starting `<!-- work-queue -->` / `<!-- self-fix -->` with a `## Decisions` table. The tick starts that issue before every other ready issue. The epic pull request (and a loop pull request outside an epic) lists every self-decided fix under `## Self-decided fixes`.
6. **Exception to team principle 1.** "The AI never changes the requirement" holds, except for the technical cases of point 3 within the limits of point 4. Everything else is still changed only by the owner, in the issue.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| What the loop may decide alone | Technical fixes only (point 3) | Also ACs, texts or business rules | The owner chose "technical fixes only" on 2026-11-10 |
| How many self-fix rounds | One per issue, then the owner | Several rounds | No endless loops (team principle 4) |
| Where the owner sees them | The self-fix comment and `## Self-decided fixes` in the pull request | Only the issue | One place in the review that already happens |
| Catch earlier | `pinned_tests.py --unlisted` at planning and at each tick, a query budget per epic | Only the build's self-fix | Cheaper to fix before the build starts |

## Consequences

- An issue body may change without the owner: always from the loop's comment marked `<!-- self-fix -->`, and only in the technical cases.
- The self-fix rules live in the `work-queue` skill text; the owner checks them in review through the Decisions comment and the pull request section.
- `.claude/` files stay a hand-built exception (ADR-023); a self-fix never adds one.
