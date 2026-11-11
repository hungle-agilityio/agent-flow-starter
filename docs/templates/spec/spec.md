# Spec: <feature>

<!-- Copy to docs/specs/<feature>/spec.md. The ACs are the contract: the build and the review are checked against them. -->

## Summary

<the change in plain words; which page, report or data it touches, or "nothing visible to users">

## Acceptance criteria

Each AC can be checked by a person or a test, with exact values, pages or texts. Write the test rule as "every test on `main` passes unchanged". In an epic, a task that changes a number or behaviour set by an earlier task names it in its ACs (ADR-022).

- **AC1.** <observable result>
- **AC2.** <observable result>

## Edge cases

- Empty: <what shows when there is no data>
- Large data: <what happens with many rows>
- Permissions: <who can and cannot see or do it>

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| <question settled in grill-me> | <option> | <option> | <reason> |

## Design

<link to the design card in docs/specs/<feature>/design.md, or "nothing visible to users">

## Open questions

<!-- Must be empty before Gate 1 ("Merge PR spec"). -->
