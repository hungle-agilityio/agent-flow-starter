# Spec: <feature>

<!-- Copy to docs/specs/<feature>/spec.md. The ACs are the contract: the build and the review are checked against them. -->

## Summary

<the change in plain words; which page, report or data it touches, or "nothing visible to users">

## User story

<!-- One line per kind of user. Work no user of the app sees names the person who gains (the owner, QA, the loop). -->

As a <user>, I want <ability>, so that <goal>.

## Acceptance criteria

Each AC can be checked by a person or a test, with exact values, pages or texts. An AC that describes what a person sees or does is written `**ACn.** Given <the starting data, with real names and numbers>, when <the action>, then <the exact result>.`; an AC about a function, a query, a file or a setting keeps the plain form. Write the test rule as "every test on `main` passes unchanged". In an epic, a task that changes a number or behaviour set by an earlier task names it in its ACs (ADR-022).

- **AC1.** Given <the starting data, with real names and numbers>, when <the action>, then <the exact result>.
- **AC2.** <observable result of a function, a query, a file or a setting>

## Edge cases

- Empty: <what shows when there is no data>
- Large data: <what happens with many rows>
- Permissions: <who can and cannot see or do it>

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| <question settled in grill-me> | <option> | <option> | <reason> |

## Decisions during build

See [decisions/](decisions/): one file per task, written by its build.

## Design

<the prototype states this feature adds or changes, as #<state> ids of docs/design/prototype.html, approved with "Prototype ổn"; or "nothing visible to users">

## Open questions

<!-- Must be empty before Gate 1 ("Merge PR spec"). -->
