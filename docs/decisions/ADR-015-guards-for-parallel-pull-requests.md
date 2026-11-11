# ADR-015: Guards for parallel pull requests

- Status: Accepted (changes parts of ADR-008, ADR-010, ADR-012 and ADR-014)
- Date: 2026-10-29

## Context

Since ADR-014 the tick runs several builds at once. Two pull requests built in parallel can touch the same file, so the second one is behind `main` and may conflict after the first is merged. The tick read only the first `Depends on` number, a conflict always ended as `pr:blocked` for the owner to fix by hand, and GitHub let a pull request that is behind `main`, or red, be merged. Earlier ADRs assumed branch protection needs a paid plan; that is true for a private repository, but this repository is public. Spec `docs/specs/pr-parallel-guard/spec.md`, issues for the tick (AC1 to AC7) and #71 (AC8 to AC13).

## Decision

### Tick guards (`.flow/loop/`, spec AC1 to AC5)

1. **Every `Depends on` number.** Every `#<number>` on a body line that starts with `Depends on` is a dependency; the issue is not taken while any of them is open.
2. **Files of an issue.** The backticked paths in the bullet lines of its `## Files likely touched` section, compared after removing a leading `./` and ``. Every issue body has that section (`docs/templates/spec/tasks.md`, `.claude/project-instructions.md`).
3. **Wait on shared files.** A ready issue is not taken while one of its files is a file of an open `agent:running` or `agent:review` issue, or of an issue chosen earlier in the same tick. One log line names both issues and the file.
4. **No files listed.** The issue runs alone, as `risk:high` does (ADR-014).
5. **Red `main`.** When the last completed `Checks` run on `main` is not `success`, no new issue starts in that tick (pull request runs still start), and one ntfy message per red commit is sent. An unreadable run counts as green, with a log line.

### Merge order and conflicts (`.claude/`, spec AC8 to AC10)

6. **One merge at a time.** The Merge step of `.claude/project-instructions.md` merges one build pull request at a time. Before each merge it runs `gh pr update-branch <n>` when the pull request is behind `main`, waits for CI on the new head and merges only when it is green. After a clean update, green CI is enough; the verify report is not rebuilt.
7. **A conflict goes back to the loop.** When `gh pr update-branch` fails on a conflict, the merge thread does not merge. It posts `/redo merge origin/main into this branch and fix the conflict` on the pull request with the owner's login, runs one tick at once, and tells the owner. The owner's OK is needed again after the redo.
8. **The loop merges `main`, never rebases.** On that `/redo`, `work-queue` section 1 runs `git fetch origin main` and `git merge origin/main` on the pull request branch, fixes the conflict, and does the full round: tests and gates, review, the same report republished to the same link, push, wait for CI. A conflict without such a `/redo` still gets `pr:blocked`; so does one that cannot be fixed without changing the requirement, with the reason.

### Branch protection (spec AC12)

9. The repository is public, so a GitHub ruleset on `main` costs nothing. GitHub then refuses a merge that is behind `main` or red, including a Merge clicked on GitHub, which the hooks and the merge step never see.
10. **The owner switches it on once** (Claude does not change repository settings, `rules/security.md`):
    1. On GitHub, open the repository, then **Settings**, **Rules**, **Rulesets**, **New ruleset**, **New branch ruleset**.
    2. Name it `main`, set **Enforcement status** to Active, and leave the **Bypass list** empty.
    3. **Target branches:** Add target, **Include default branch**.
    4. Tick **Require a pull request before merging** (required approvals 0, since the owner merges alone).
    5. Tick **Require status checks to pass**, tick **Require branches to be up to date before merging**, and add the check `checks`.
    6. Tick **Block force pushes** and **Restrict deletions**.
    7. **Create**. To check it: try to merge a pull request that is behind `main`; GitHub refuses until it is updated.
11. **Lines replaced.** ADR-008 "Branch protection / required reviews: needs a paid plan", ADR-010 "the free plan has no branch protection", and ADR-012 "No branch protection" and "Branch protection with CODEOWNERS: paid plan". Each now points here. The hooks stay as a second layer.

## Rejected options

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Which issues the tick compares files with | `agent:running` and `agent:review`; no files listed means it runs alone | Only `agent:running` | The second build starts from the new `main`, so its report is never stale for shared files |
| A conflict when updating the branch | The merge thread posts `/redo merge origin/main …`; the loop merges `main`, fixes, retests, updates the report | Keep `pr:blocked`; rebase | A rebase needs a force-push, which the guardrails forbid; the owner does not want to fix conflicts by hand |
| Report after a clean update of the branch | Green CI on the new head is enough | Always `/redo` a full re-verify | With the file guard, pull requests in review never share a file; a re-verify costs a build of 10 to 45 minutes |
| Branch protection | The owner switches on a ruleset on `main` | Hooks only | The repository is public, so it is free; it also guards a merge clicked on GitHub |
| `main` red after a merge | No new issue starts; one ntfy per red commit | Rely on GitHub's e-mail | New builds from a red `main` would go red too |

## Consequences

- Pull requests that list the same file are built one after the other, so the queue can be slower; a missing `## Files likely touched` section makes an issue run alone.
- A conflict costs one more loop round instead of the owner's time, and the owner approves the pull request again after it.
- Until the owner switches on the ruleset, only the merge step's order and the hooks keep a stale or red pull request out of `main`.
- If the repository becomes private, the ruleset needs a paid plan; the guards above still hold.
