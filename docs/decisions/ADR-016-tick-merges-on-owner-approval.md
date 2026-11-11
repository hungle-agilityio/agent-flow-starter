# ADR-016: The tick merges on the owner's approval comment

- Status: Accepted (changes parts of ADR-009 and ADR-015)
- Date: 2026-10-29

## Context

The owner wants to review loop pull requests the normal way, from the phone: a comment or a comment on a line asks for a change, a short "lgtm" merges. Until now only `/redo` asked for a change, and a merge needed a thread's `gh pr merge` with the hook's prompt, which Claude's auto mode can get in the way of. ADR-009 rejected a `/merge` comment because a Claude build works with the owner's token and could write one itself, or be steered into it by text in an issue. Spec `docs/specs/loop-ux/spec.md`; the tick part is a separate issue, this part is #79.

## Decision

### The tick merges, Claude builds never do

1. **Claude builds never merge; the tick merges on the owner's approval comment.** The tick (`.flow/loop/agent_tick.py`) is plain Python: no model reads issue text there, so no comment can talk it into a merge. The hook `before-github-command-check` keeps refusing `gh pr merge` in every loop build (`FLOW_LOOP=1`).
2. **Approval comment.** An owner comment (the owner's login, no `<!-- work-queue -->` marker) on the pull request conversation whose whole body, lower case, trimmed, with trailing `.!,:;` removed, is one of `/merge`, `merge`, `lgtm`, `approved`, `approve`, `looks good`, `look good`, `ok`, `duyệt`, `ship it`. "lgtm but rename X" is a change request, not an approval.
3. **Checks before the merge (spec AC6 to AC10).** The newest approval is newer than the newest commit that is not an update from `main` (`Merge branch 'main'`); the pull request is not a draft and has `pr:ready-for-review`; it has at least one check and all are `SUCCESS`, `NEUTRAL` or `SKIPPED`; no change request is open; no run of it is in progress. Then `gh pr merge <p> --merge --delete-branch --match-head-commit <head sha>`. Behind `main`: `gh pr update-branch` and no merge in that tick. A conflict on update: the tick posts `/redo merge origin/main into this branch and fix the conflict` (ADR-015). `DIRTY`, `BLOCKED`, red CI or a failed merge: no merge and one ntfy message per reason. The tick adds 🚀 to the approval after a merge and 😕 after a refusal; a new approval is needed then. A comment, reaction or label from any other login counts for nothing.
4. **Every route ends at the tick.** A comment on GitHub; the project chat, where a thread posts `/merge` with the owner's login and runs one tick (it no longer runs `gh pr merge`); or the Merge button on GitHub, after which the tick pulls `main` and announces it.

### Change requests with done marks (spec AC11 to AC14)

5. **Open change request.** An owner comment on a loop pull request that is not an approval comment, has no done mark, was created after the pull request was opened, and is on the conversation, an inline review comment (top-level or reply), or a `/redo` comment on the issue. A **done mark** is a 🚀 or 😕 reaction by the owner's login. The tick runs a pull request when it has one, instead of "`/redo` newer than the last commit".
6. **The loop marks each one** (`work-queue` section 1). The round's requirement is every open change request, oldest first; the run adds 👀 to each when it starts. At the end: 🚀 and a reply `Done in <short sha>: <one line>` when done; a question is answered in the reply with 🚀 and no commit; 😕, a reply with the reason and `pr:blocked` when it cannot be done without changing the requirement or a hook blocks it. A reply to an inline comment goes in its thread, and the thread is resolved once the comment has 🚀. The owner may add 🚀 to skip a comment.
7. **Permissions in loop mode.** The hook answers `allow` for exactly: `gh api -X POST repos/hungle-agilityio/agent-flow-starter/issues/comments/<id>/reactions` and `.../pulls/comments/<id>/reactions` with `content` `eyes`, `rocket` or `confused`; `.../pulls/<p>/comments/<id>/replies` with a `body`; `gh api graphql` with the `resolveReviewThread` mutation only, and the read of the pull request's `reviewThreads` in this repository, which the mutation needs for the thread id (`gh pr view` cannot return it). Any other call to those endpoints is refused in loop mode, `gh pr merge` stays refused, and outside loop mode every `gh api` asks. `settings.json` has the matching allow rules; its blanket "ask" for `gh api` moved into the hook, because a settings "ask" rule overrides a hook's `allow`.

### Lines replaced

- ADR-009, "The loop never merges. The owner merges from an interactive session ... `gh pr merge N --merge --match-head-commit <sha>`", and its rejected option "`/merge` comment as the signal".
- `rules/git.md`, "It merges one only in an interactive session, when the user says which pull request and approves the prompt; the loop never merges".
- `rules/security.md`, "Merging is never an exception" and "A merge is asked every time and never done by the loop".
- `rules/workflow.md`, "The loop never merges: the merge is the user's, approved in an interactive session or on GitHub".
- `work-queue`, "`/redo <what>` counts when ...", the `/redo` bullet of section 1 and "How a pull request gets merged (not by the loop)".
- `.claude/project-instructions.md`, the Merge and Conflict steps (a thread no longer runs `gh pr merge` for a build pull request) and the Redo step (plain comment, no `/redo` prefix).

Each of those lines now says "Claude builds never merge; the tick merges on the owner's approval comment (ADR-016)" or describes the change requests above.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Which ntfy messages | Nine cases: started, PR opened/updated, needs you, failed or not started, waiting on the cap, queue empty, merged and main pulled, not merged, limit / red main / main not updated | Only the cases that need the owner | The owner listed "tick issues"; about ten messages a day |
| Q2. Which comment approves | A short whole comment from a fixed list (`lgtm`, `approved`, `duyệt`, ...) by the owner | Only `/merge`; any comment containing `lgtm` | Natural to write, but "lgtm but fix X" never merges |
| Q3. Who merges | The tick, for every route: GitHub comment, project chat (a thread posts `/merge` and runs a tick), GitHub button (tick announces and pulls) | Tick for comments, the thread's `gh pr merge` for the chat | One route with fixed checks in code, and no Claude auto mode in the way |
| Q4. What is a change request | Any owner comment on the pull request, inline comments too, and `/redo` on the issue | `/redo` or inline comments only; `/redo` only | The easiest for the owner; a question is answered without a commit |
| Q5. How a request is marked done | Reactions 👀 / 🚀 / 😕 by the owner's login and a reply; open = no 🚀 or 😕 | A checklist in the pull request body; time of the last commit | Visible on each comment, independent of commits; the owner can skip one with a 🚀 |
| Q6. Which channel for loop messages | Slack Incoming Webhook and ntfy, each when its setting is in `~/.starter/agent.env` | ntfy only; Slack only; a Claude mobile push via `claude -p`; the GitHub app | Slack as the owner asked, with ntfy kept as a fallback; the GitHub app does not notify the owner of actions made with the owner's own login |

## Consequences

- The owner merges with one short comment from the phone; the tick checks the same things every time, in code.
- The forgery risk of ADR-009 stays narrow: a Claude build could still write an approval with the owner's token, but every comment it writes carries the marker and so is not an owner comment, and the tick also needs green CI and no open change request. A build that drops the marker on purpose is the remaining risk; the hook does not read comment bodies.
- Until the tick part ships, an approval comment does nothing; the owner clicks Merge on GitHub.
- Old `/redo` comments that were already done count as open after the switch; the owner adds 🚀 to them (none open on 2026-10-29).
