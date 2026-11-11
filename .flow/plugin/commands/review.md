---
description: Review the current diff before commit
---

Review the current changes (`git diff` and `git diff --cached`).

1. Use the `reviewer` sub-agent; it re-derives correctness from the issue and the code, not from the implementer's explanation.
2. Check against `.claude/rules/` and `.claude/knowledge/KNOWN_PITFALLS.md`.
3. Report one line for each of the five areas: Requirement, Business, Expected result, Regression, Code (`OK` or `FINDING`), then the findings by severity (blocker, should fix, nit) with `file:line`. Say which round it is (Round 1 of 2 or Round 2 of 2); after round 2 with findings open, stop and ask the user to decide. For a pull request document use the `review-pull-request` skill instead.

Read-only: do not change code.
