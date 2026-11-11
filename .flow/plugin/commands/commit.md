---
description: Draft a commit message from the diff and commit it in the project format
---

Confirm Gate 2 (the user checked the verified result and said OK). If not, stop and ask.

Use the `create-commit` skill to commit the current changes. It holds the format, the branch rules and the safety rules (see also `.claude/rules/git.md`).

Show me the message and the files first if the split is not obvious. Do not push.
