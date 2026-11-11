---
description: Execute an approved plan, test first
argument-hint: <issue number or folder>
---

Implement the approved plan for: $ARGUMENTS

1. Confirm Gate 1 was passed. If there is no approved plan (and the issue is not Easy), stop and ask.
2. Use the `implementer` sub-agent. It follows the plan step by step, test first, and builds only what the plan says. A change of scope goes back to `/plan`.
3. Work on the issue's branch (`.claude/rules/git.md`), never on `main`.
4. Finish with `/test` and report what changed.
5. If `/review` finds something, fix it and review again, at most **two rounds** of fix and review. If a finding is still open after the second review, stop and ask me to decide.
6. Never change the requirement of the issue; a different requirement goes back to the user.
