# ADR-024: A loop build fixes technical stops itself

- Status: Accepted (an exception to team principle 1 of `.claude/rules/workflow.md`)

## Context

A build can stop on a purely technical point the issue did not foresee, for example an existing test that pins a number an AC changes. Such stops should be caught before a build starts, and the rest fixed by the loop itself, within strict limits.

## Decision

1. **Catch it at planning.** Before an issue gets `agent:ready`, the Project thread runs `uv run python .flow/loop/pinned_tests.py --unlisted <body file>` and settles every hit: the test goes under `## Existing tests that change`, or an AC is reworded so the test stays unchanged. An epic's `tasks.md` keeps a `## Query budget` table.
2. **The tick warns the build.** Before an issue build it runs the same check and adds the unlisted tests to the prompt.
3. **The build fixes technical stops itself** (`work-queue`, Self-fix). Technical means only: an existing test pins a fixed number or a literal that an AC changes; an unguarded file the plan needs is missing from the issue's files; an AC can be met at no extra cost by a narrower technical reading; a decision the issue leaves open has a recommended option in the spec.
4. **Limits.** A self-fix never deletes, skips or weakens a test beyond the new number the AC needs, never accepts a query count that grows with the data, never changes a text, page, business rule, permission, migration or data, and never adds a guarded file. One self-fix per issue; a second stop is a `needs-decision` stop for the owner.
5. **Everything is visible.** The self-fix edits the issue and posts a comment starting `<!-- work-queue -->` / `<!-- self-fix -->` with a `## Decisions` table. The pull request lists every self-decided fix under `## Self-decided fixes`.
6. **Exception to team principle 1.** "The AI never changes the requirement" holds, except for the technical cases of point 3 within the limits of point 4.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| What the loop may decide alone | Technical fixes only | Also ACs, texts or business rules | The requirement stays the owner's |
| How many self-fix rounds | One per issue, then the owner | Several rounds | No endless loops |
| Where the owner sees them | The self-fix comment and `## Self-decided fixes` | Only the issue | One place in the review that already happens |
| Catch earlier | `pinned_tests.py --unlisted` at planning and each tick, a query budget per epic | Only the build's self-fix | Cheaper before the build starts |

## Consequences

- An issue body may change without the owner, always from the loop's comment marked `<!-- self-fix -->`, and only in the technical cases.
- `.claude/` files stay a hand-built exception (ADR-023); a self-fix never adds one.
