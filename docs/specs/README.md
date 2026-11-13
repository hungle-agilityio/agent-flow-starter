# Specs

One folder per feature, `docs/specs/<feature>/`, written by the Project at step 3 (full lane) from `docs/templates/spec/`:

- `intent.md`: the problem, the goal, the users, what is out of scope.
- `spec.md`: the user story, numbered ACs (the contract), edge cases, the decisions settled in grill-me, the design link, and an "Open questions" section that is empty before Gate 1.
- `test-matrix.md`: the tests planned per AC: case, level, test file and task, written before any build.
- `tasks.md`: one entry per issue, with its ACs, the files likely touched, `Depends on`, the risk and `needs-ui`.
- `decisions/`: one file per task, T<k>.md, written by its build in its own pull request: the decisions taken while building (ADR-027).

A spec pull request changes only `docs/intent/`, `docs/specs/` and `docs/design/`. The owner approves it by saying "Merge PR spec" in the Project (Gate 1, ADR-012). Easy work takes the fast lane and has no folder here; its short spec lives in the issue.
