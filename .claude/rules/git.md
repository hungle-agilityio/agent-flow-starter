# Git and GitHub rules

The step-by-step procedure is in the skills `agent-flow:create-commit`, `agent-flow:create-issue` and `agent-flow:create-pull-request`. This file is only the format.

## Hard rules

- Never commit directly to `main`. One branch per issue.
- Nothing is pushed, published or created on GitHub without the user's approval for that item. Exception, loop mode only (ADR-009): the loop pushes its own issue branch and opens its pull request.
- Claude never approves a pull request. Claude builds never merge; the tick merges on the owner's approval comment (ADR-016). A spec pull request is merged in an interactive session after the owner's "Merge PR spec".
- No `Co-Authored-By` or "Generated with" line in commits.

## Branches

- Format: `<kind>/<id>-<short-description>`, the issue number and a short lowercase description separated by dashes.
  - Bug: `bug/1-dashboard-wrong-score`
  - Feature: `feat/4-filter-reviews`
  - Task: `task/6-cleanup-demo-data`
- The branch needs the issue number, so publish the issue first.

## Commits

Three parts separated by a blank line:

```
<title>

<detail>

Part of <id>
```

- **title:** short, imperative, says what changed (no issue ID).
- **detail:** what changed and why, lines wrapped at about 72 characters.
- **Part of `<id>`:** the issue number, for example `Part of #1`; one line per issue if a commit touches several. **Left out entirely when there is no issue number yet**; never invent one.

Example:

```
Fix average score rounding on dashboard

The average was calculated with whole-number division, so 11 / 3
showed as 3. It now keeps the decimals (3.67).

Part of #1
```

## GitHub and pull requests

- Remote: `origin` is the GitHub repository named in `project.repo` of `.flow/flow.toml`; Claude can reach no other repository (the guard hook blocks it). Issues and pull requests are created with the `gh` command through the skills `agent-flow:create-issue` and `agent-flow:create-pull-request`.
- An issue is drafted and reviewed locally, and published on GitHub only after the user approves it (type, labels, assignee `hungle-agilityio`). The skill reports `title | link`.
- Pull request: into `main`, title `[type] title` (for example `[BUG] dashboard show wrong score number`), description with What, Why, How tested, Evidence and One concern (built by `agent-flow:draft-pull-request`), ending with `Closes #<number>`. Created only after the user approves the preview.
