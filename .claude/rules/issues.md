---
paths:
  - "docs/issues/**"
  - "docs/templates/**"
  - "docs/learning/issues/**"
  - ".github/**"
  - "../.github/**"
---

# Issue rules

Use the skill `write-issue` (bug, feature, task or epic) to create issues.

- **Issue number:** the GitHub issue number, assigned when the issue is published, written `#6` in text. A draft issue has no number yet. The type is shown by the title (`[BUG]`) and by the branch prefix, never by the number.
- **Title format:** `[type] title`, where type is `BUG`, `FEAT`, `TASK` or `EPIC`. Example: `[BUG] dashboard show wrong score number`. The issue number is not part of the title or the file name.
- **Files:** issues are grouped by type (`bugs/`, `features/`, `tasks/`). **One issue is one markdown file** named after it, for example `bugs/dashboard-wrong-score.md`, where the name is the short lowercase description also used in the branch name (`bug/1-dashboard-wrong-score`). Two roots: `docs/issues/` for issues of the app, `docs/learning/issues/` for work on how we use Claude Code (the epic in `docs/learning/epics/`). Epics are single files in `docs/learning/epics/`. Issues made before 2026-10-16 keep their four-file folders (learning exercise); do not copy that layout.
- **Epics:** built from `docs/templates/epic.md`; between 3 and 10 children, each child one pull request; the children are sub-issues of the epic (a checklist if sub-issues are not available); every change of scope is logged in the epic with its reason; a bigger epic is split.
- **Index:** `docs/issues/README.md` and `docs/learning/issues/README.md` list local number, GitHub issue, type, file and title; add a row for every new issue.
- **Tone:** issues are written in plain language for QA, BA and clients: no code, commits, branches or technical terms.
- **The issue file:** the only file `write-issue` creates. It is the complete standalone issue, built from `docs/templates/bug.md`, `feature.md`, `task.md` or `epic.md`, and posted as a GitHub issue, so it must not refer to any other file.
- **Old four-file folders** (`01-reported.md`, `02-analysis.md`, `03-discussion.md`, `04-final.md`) are learning material from the training: the report as received, our analysis, the conversation and the final issue. Do not create or change them.
- **Markdown placeholders:** write `\<placeholder>`, not `<placeholder>`; the preview treats bare angle brackets as HTML and hides them.
