---
description: Produce the step-by-step, test-first plan for an analysed issue
argument-hint: <issue number or folder>
---

Plan the issue: $ARGUMENTS

1. Use the `planner` sub-agent on the analysed issue (Medium and Hard only; Easy issues skip this).
2. The plan follows `.claude/rules/architecture.md` and, if useful, `.claude/templates/layered-feature.md`. It checks `.claude/knowledge/BUSINESS_RULES.md` and `KNOWN_PITFALLS.md`.
3. Show me the plan and **stop at Gate 1**: wait for my approval before any code is written.
4. After my approval, when `paths.plans_dir` of the flow config (`.flow/flow.toml`, else `.flow/flow.toml`) is not empty, save the approved plan as `<plans_dir>/<issue number>-<short-description>.md`. When it is empty, save nothing.
