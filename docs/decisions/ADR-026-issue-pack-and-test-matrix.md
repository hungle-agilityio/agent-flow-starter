# ADR-026: Every spec and issue carries a user story, Given/When/Then and a test matrix; an issue passes a zero-questions test

- Status: Accepted
- Date: 2026-11-11

## Context

Day 12 of the training ("Kickoff and planning") asks for a ticket pack (story, Given/When/Then, open questions), a QA test matrix drafted from the criteria, and a zero-questions test that makes the quality of an issue measurable. The check of 2026-11-11 found the intake in place (analysis, grill-me, spec pull request, issues; "Open questions" empty at Gate 1) but three gaps: no user story, user-visible ACs not written as Given/When/Then, no test plan before the build (the verify report shows the ACs only after it), and nothing that measures the `write-issue` rule "anyone can follow it without asking questions". Spec `docs/specs/issue-pack/spec.md`; issues #463 (templates and `write-issue`, pull request #465) and #464 (this record and the Project rules).

## Decision

1. **User story.** `spec.md` has a `## User story` section (`As a <user>, I want <ability>, so that <goal>.`); each issue Summary ends with that line. Work no user of the app sees names the person who gains (the owner, QA, the loop).
2. **Given/When/Then for what people see.** An AC that describes what a person sees or does is written `Given <the starting data, with real names and numbers>, when <the action>, then <the exact result>.` An AC about a function, a query, a file or a setting keeps the plain form.
3. **Test matrix before the build.** Full lane: `docs/specs/<feature>/test-matrix.md` (template `docs/templates/spec/test-matrix.md`) is written at step 3 from the ACs and is part of the spec pull request: one row per check with its AC, case, check, level, test file and task; every AC has a row, every user-visible AC a "normal" and an "empty" row (or `n/a: <why>`). Each task in `tasks.md` and each issue (`## Test matrix rows`) names its rows. Fast lane: the small table goes in the issue.
4. **Zero-questions test.** Before `agent:ready`, a new sub-agent with no conversation context reads only the issue body and the repository and lists every question it would have to ask before it could build and test the issue. Each question is fixed in the issue (a decision goes to the owner first) and a new sub-agent runs again. The issue is ready only at 0 questions; the `Decisions` comment records `Zero-questions test: 0 questions after <n> rounds (<k> in round 1).`
5. **Scope.** New requests in this repository only. Existing specs, issues and tests do not change; the CLI issue route (`docs/templates/feature.md`, `check_issue.py`) and the template repository stay as they are for now.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Where the story and Given/When/Then apply | The story line, plus Given/When/Then for user-visible ACs, in the spec template and the issue body | Given/When/Then for every AC; also the CLI route | Given/When/Then fits behaviour a person sees; for a function it only makes the line longer, and the CLI route would change an existing test |
| How zero-questions is measured | A fresh sub-agent must return 0 questions; rounds recorded in Decisions | A `claude -p` script on the Mac mini; a self-ticked checkbox | Measurable in the Project thread with no new code; a checkbox measures nothing |
| Where the QA test matrix lives | Its own file in the spec pull request; issues list their rows | Inside `tasks.md`; the verify report ticking each row | One place QA reads for the whole epic; the loop does not change |
| How far it applies | New requests in starter | Also `agent-flow-starter` now | Try it here first, then copy it to the template |

## Consequences

- The Definition of Ready in `.claude/project-instructions.md` gains two lines; the owner pastes the updated text into Project settings.
- A spec pull request now has four files (five with a design link); the owner can check the planned tests at Gate 1.
- The zero-questions result is only as good as the sub-agent run; the Decisions comment shows the rounds so a reader can see it was done.
