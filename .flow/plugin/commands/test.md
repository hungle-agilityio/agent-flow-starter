---
description: Run lint, types and tests and report the result
---

Use the `test-runner` sub-agent to run the checks and show me its report as it is.

- It runs lint, types, the app tests with coverage, the coverage gate and the hook and issue checker tests, and reports only what failed (one line when everything is green).
- Failing tests that belong to open bug issues are expected: it says which issue, it does not hide them.
- Do not change code in this step unless I ask. See the `write-tests` skill for writing tests.
