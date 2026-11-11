# ADR-009: The loop opens pull requests; the owner merges

- Status: Accepted (parts changed by ADR-012)
- Date: 2026-10-26

## Context

ADR-008 stopped the loop at a local commit and asked the user before every push. The user wants to review several pull requests at once while the loop keeps working the rest of the queue. The first design let the loop merge a pull request after the owner commented `/merge`. Two independent reviews showed that cannot be made safe: the loop works with the owner's own token, so a `/merge` comment it (or text injected through an issue) writes is indistinguishable from the owner's, and a check made before a chained `git push && gh pr merge` merges commits nobody reviewed. On the free plan there is no branch protection to back it up.

## Decision

The user decided (2026-10-26) that the loop stops at the pull request:
- The loop pushes its own issue branch and opens the pull request with the verify report link; no preview. At most 5 wait at once; an issue with `Depends on #M` waits until #M is closed.
- **The loop never merges.** Replaced by ADR-016: Claude builds never merge; the tick merges on the owner's approval comment (ADR-016). Merging on GitHub works too.
- `/redo <what>` on a pull request sends it back. It can only cause more work, so a forged one is harmless.
- One private "Review queue" artifact lists the waiting pull requests; a push notification says when the queue is empty.

Rejected:
- **`/merge` comment as the signal:** forgeable with the shared token (above). Revisited in ADR-016: the tick, plain Python that no issue text can steer, reads it, and Claude builds still never merge.
- **A second GitHub account for the loop:** would make `/merge` a real signal, but adds an account to manage and a collaborator on a private repo. Revisit if the one-tap merge becomes a bottleneck.
- **GitHub "Approve":** the pull request is opened with the owner's token, and GitHub does not let an author approve their own pull request; `gh pr review` is also denied.

## Consequences

- Rules `git.md`, `security.md`, `workflow.md` carry one exception for loop mode: push of its own issue branch and the pull request. Merging is never an exception.
- `.claude/settings.json` allows `git push`, `gh pr create` and `gh pr merge`, because permissions cannot see the loop mode. `before-github-command-check` is what limits them: it asks outside loop mode, refuses force, delete, all-branch and `main` pushes in every mode, refuses every merge in loop mode, and requires an exact merge command with the head commit. Moving `gh pr merge` from `allow` to `ask` in the settings would make the prompt independent of the hook.
- Regex hooks cannot see every way of writing a command (`bash -c '...'`, `command git ...`), and the edit guard sees edit tools, not what a shell command writes. The permission list covers most of that because those forms match no allow rule. **Never run the loop in a mode that skips permission prompts.**
- Pushing to the issue branch after a review is still possible: the merge names the head commit the owner saw, so later commits are not merged by mistake.
