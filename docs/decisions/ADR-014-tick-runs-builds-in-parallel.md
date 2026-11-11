# ADR-014: A tick runs loop builds in parallel

- Status: Accepted (changes parts of ADR-008, ADR-009 and ADR-012)
- Date: 2026-10-28

## Context

The owner hands over several `agent:ready` issues at once, but the loop was one interactive session (`/loop 30m use the work-queue skill`) that built one issue per run, with no time limit, so a stuck run held up everything behind it. ADR-012 planned scripts that start one `claude -p` per issue. This is the smallest working part of its phases 2 and 5 (spec `docs/specs/loop-concurrency/`, issues #49 and #50).

## Decision

The owner decided (spec PR #48, questions Q1 to Q7):

- **A tick, not a session.** `.flow/loop/agent_tick.py` (Python, tested with pytest and mypy) runs every 5 minutes (10 at first; 5 since #201) in a tmux session `starter-loop` under `caffeinate -i`, started by `.flow/loop/start-loop.sh`. It uses no plan usage when there is nothing to do.
- **`AGENT_CONCURRENCY`** in `~/.starter/agent.env` (not committed; `.flow/loop/agent.env.example`) sets the builds at once: 1 to 3, default 1, the Mac mini uses 2.
- **The lock.** One tick at a time, with `mkdir ~/.starter/tick.lock`; a lock older than 15 minutes is left over and taken. Because only the tick picks and claims (`agent:running`), two builds never take the same issue.
- **One build is one `claude -p`** with `FLOW_LOOP=1`, `--max-turns 80`, stopped after 45 minutes, never in a mode that skips permission prompts. Its prompt names one target, "Use the work-queue skill for issue #N only." (or "pull request #N"), and `work-queue` works on that target only; the tick did the picking, the claim, the labeller check and the cap (the cap is superseded by ADR-018).
- **Worktrees** in `~/.starter/worktrees/<key>`, outside the repository and any `.claude` folder, so the hooks of that checkout are active and builds never share a folder. Removed after a normal end; kept after a failure.
- **Order:** the loop's pull requests that need a run first, then the oldest `agent:ready` issues whose label was added by `hungle-agilityio`, honouring `Depends on`. The cap is 3: the loop's open pull requests plus `agent:running` issues (later 10; superseded by ADR-018: no pull request limit).
- **Runs alone:** an issue labelled `risk:high`, or whose body names `migrations/` or `models.py`, starts only when no build runs, and no new issue starts while it runs. Pull request runs are not limited.
- **Plan limit:** the issue goes back to `agent:ready`, new builds pause 60 minutes (`~/.starter/paused-until`), and the owner gets a message. Never `agent:failed`: the limit is not a fault of the task.
- **Failure:** a build that times out or ends with an error before its pull request gets `agent:failed`, a comment (with the marker) with the reason and the last 20 log lines, and a message.
- **ntfy** (`NTFY_TOPIC`, optional) sends: a failed build, a plan-limit pause, and "queue empty, N pull requests waiting" (again only after something changed).
- **The Review queue page is removed,** with the `PushNotification` "queue empty". Two builds would write one page at once; the `pr:*` labels (ADR-013) already show each pull request's state, and the tick notifies.
- **Update branch before a merge.** The Project's merge step runs `gh pr update-branch <n>` when the pull request is behind `main`, waits for CI on the new head and merges only when it is green. This catches clashes such as two `0004` migrations before they reach `main`; the loop itself still never merges and never merges `main` into its branches.

Rejected:
- **All of ADR-012 phase 2 at once** (review `claude -p` with `VERDICT`, `plans/issue-N.md`, the new Gate 2 report): more new parts before two builds can run.
- **Bash with `gtimeout`, `jq` and `bats`:** two more tools to install and no tests in the repository's own runner.
- **launchd, or `/loop 10m` in a `claude` session:** launchd is harder to see and stop; a session uses plan usage on every tick.
- **Keep the Review queue page, updated by a short `claude -p`:** one more run per tick for what the labels already show.
- **Only `Depends on` decides what runs together:** two issues that both add a migration would clash.
- **The owner presses "Update branch", or the loop merges `main`:** the first is easy to forget; the second changes the loop.

### What it replaces

- ADR-008: "A `/loop` session on the Mac mini runs the `work-queue` skill" and "one loop at a time" (now one tick at a time, up to `AGENT_CONCURRENCY` builds).
- ADR-009: "At most 5 wait at once" (now 3, counting running issues too, as ADR-012 planned) and "One private Review queue artifact lists the waiting pull requests; a push notification says when the queue is empty" (now the `pr:*` labels and ntfy).
- ADR-012: phase 2's `.flow/loop/agent-env.sh`, `.flow/loop/agent-tick.sh`, `.flow/loop/agent-run.sh` and `gtimeout` become one Python tick; the parts of phases 2 and 5 listed above are done. The rest of phase 2 (review `claude -p`, `plans/issue-N.md`, Gate 2 report, risk flags), phases 3, 4 and 6, and retiring `work-queue` are still to do.

## Consequences

- Two builds share the Claude plan, so the plan limit comes sooner; the pause handles it.
- The tick cannot see the old `/loop` session. The owner must stop it before starting the tick (`.flow/loop/README.md`).
- After a reboot or a closed tmux window the loop stops until the owner starts it again; a build whose process is gone is handled as a failure at the next tick.
- The Stop hook `before-finish-check` was not tested in `claude -p`; check it on the Mac mini before the first real run.
- `security.md` still names the Review queue page under the standing approval of ADR-009; it no longer applies.
