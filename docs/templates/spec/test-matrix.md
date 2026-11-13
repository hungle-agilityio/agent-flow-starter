# Test matrix: <feature>

<!-- Copy to docs/specs/<feature>/test-matrix.md. The tests planned per AC of spec.md, for QA and the build: one row per check. -->

| Row | AC | Case | Check | Level | Test file | Task |
|---|---|---|---|---|---|---|
| M1 | AC1 | normal | Given <the starting data, with real names and numbers>, when <the action>, then <the exact result>. | integration | `<new test file of T1>` | T1 |
| M2 | AC1 | empty | Given <no data>, when <the action>, then <the exact text shown>. | integration | `<new test file of T1>` | T1 |
| M3 | AC3 | normal | <the plain check of a technical AC> | unit | `<new test file of T2>` | T2 |

## Allowed values

- "Case" is one of "normal", "empty", "edge", "error", "permission", "narrow screen".
- "Level" is one of "unit", "integration", "browser", "manual".
- "Check" is the Given/When/Then of a user-visible AC or the plain check of a technical AC.

## Rules

- Every AC has at least one row.
- Every user-visible AC has a "normal" row and an "empty" row, or a row whose "Check" says `n/a: <why>`.
- A row's test file is the new test file named in its task.
- A check no test can make has "Level" "manual" and gives the person's steps.
- The matrix is written at step 3 from the ACs, before any build, and is part of the spec pull request.
