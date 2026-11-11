---
description: Evidence-first analysis of an issue, then classify difficulty
argument-hint: <issue number, folder or pasted report>
---

Analyse the issue: $ARGUMENTS

1. Use the `analyst` sub-agent. It reads the issue, the code and `docs/app/starter-project-context-2026-10.md`, and checks `.claude/knowledge/` for known rules and pitfalls.
2. Relay its questions to me, numbered, each with a proposal I can accept.
3. After my answers, give the difficulty (Easy, Medium or Hard) and the steps from `.claude/rules/workflow.md`.
4. If it is Medium or Hard, or decisions are still open, say how many and ask whether to run the `grill-me` skill before `/plan`. Wait for my answer; do not start it on your own.

Do not change code or issues in this step.
