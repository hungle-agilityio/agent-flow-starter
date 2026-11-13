# The loop on the Mac mini

`agent_tick.py` is one tick of the loop. `start-loop.sh` runs a tick every 5 minutes in a tmux window. Each tick tidies the builds that ended, then starts up to `AGENT_CONCURRENCY` builds, each one `claude -p "Use the work-queue skill for issue #N only."` (or "pull request #N") in its own worktree, stopped after 45 minutes. Inside each build the `work-queue` skill does the work, as before. Spec: `docs/specs/loop-concurrency/spec.md`; decision: ADR-014.

## Install once

1. `brew install tmux`
2. `gh auth status` shows the owner's login, and `claude` is logged in (a `claude -p "hi"` answers).
3. Make the settings file, which is not committed:

   ```bash
   cp .flow/loop/agent.env.example .flow/loop/agent.env
   ```

   `.flow/loop/agent.env` is git-ignored and never committed. When it is missing, the tick and `start-loop.sh` still read `agent.env` in the state folder (below); only one file is read, the keys are not merged. The first line of each tick and the start message say which one (`settings: .flow/loop/agent.env`), never its values.

   Here and below, `~/.starter` is the state folder from `.flow/flow.toml` (`loop.state_dir`; `FLOW_HOME` overrides it), and `starter-loop` and `com.starter.loop` are its `loop.tmux_session` and `loop.launchd_label`. The project values (repository, owner, app folder, display name, setup command, CI workflow) come from the same file; a second project has its own `.flow/flow.toml` and its own state folder. Every build gets `FLOW_LOOP=1`.

   Set `AGENT_CONCURRENCY` (1 to 3; the Mac mini uses 2) and, for phone notifications, `NTFY_TOPIC`, then subscribe to that topic in the ntfy app.

## Start, watch, stop

**First stop the old loop:** the interactive session that runs `/loop 30m use the work-queue skill` must not run next to the tick; the tick cannot see it, and both would take the same issues.

From this folder (`` of the main checkout):

```bash
.flow/loop/start-loop.sh
```

- Watch: `tmux attach -t starter-loop` (leave with Ctrl-b d).
- Stop: `tmux kill-session -t starter-loop`. A build already started runs to its end; the next start of the loop tidies it.
- One tick by hand: `uv run python .flow/loop/agent_tick.py`.

## Start at login

After a restart of the Mac mini the loop does not come back by itself. A launchd agent starts it at login.

1. On the Mac mini, in a normal terminal, run once by hand: `bash .flow/loop/install-launchd.sh` (Claude Code there blocks it). It needs no `sudo`.
2. The Mac mini must log in by itself after a restart (System Settings → Users & Groups → automatic login), or the agent does not run.
3. At each login the agent runs `.flow/loop/start-loop.sh`; when the loop already runs, that exits and sends nothing. Otherwise the phone gets "Agent flow starter loop started on <host>". Its output is in `~/.starter/launchd.log`.
4. Remove it: `bash .flow/loop/install-launchd.sh --remove` (the plist moves to `~/.starter/archive/`).

## No messages?

1. The loop runs: `tmux ls` shows `starter-loop`. If not, run `.flow/loop/start-loop.sh`.
2. `.flow/loop/start-loop.sh` prints `Phone messages: https://ntfy.sh/<topic>` when `NTFY_TOPIC` is set in the settings file (`.flow/loop/agent.env`, or `~/.starter/agent.env` when that is missing); open that link to see the messages.
3. The topic subscribed in the ntfy app is exactly the same name.
4. Notifications are allowed for ntfy in the phone settings.

## Where things are

All under `~/.starter/`:

| Path | What |
|---|---|
| `agent.env` | the settings, read only when `.flow/loop/agent.env` in the checkout is missing |
| `runs/<key>/log.txt` | the output of a running build (`<key>` is `issue-<n>` or `pr-<n>`) |
| `runs/<key>/started` | the start time (whole seconds, tick clock) next to `pid`; a build older than the 45-minute limit plus 15 minutes counts as ended even when its pid is alive (a restart can reuse the number). Nothing is signalled. Without a valid `started` the pid alone decides |
| `runs/<key>/session-<n>.jsonl` | the whole session of start `<n>`, one JSON event per line |
| `runs/done/<key>-<time>/` | the folder of an ended build, log and sessions included |
| `worktrees/<key>` | the checkout of a build; kept after a failed build; removed when its issue or pull request is closed (see "Kept worktrees") |
| `paused-until` | set for 60 minutes when the Claude plan limit is reached |
| `tick.lock` | present while a tick runs; one older than 15 minutes is left over |

## Before an issue gets `agent:ready`

The issue writer runs `uv run python .flow/loop/pinned_tests.py <issue body file>` from ``. It lists the existing tests that name something in the issue, or that count queries while the issue touches a view, a template, a service or a repository. It changes nothing. Copy each listed test that really changes, with its new value, under `## Existing tests that change` in the issue; a build may not edit any other existing test.

## One status label per issue

An open loop issue carries exactly one of these four labels, and the tick (not the build) keeps it so.

| Label | Meaning |
|---|---|
| `agent:ready` | waiting for the loop |
| `agent:running` | being built, no pull request yet |
| `agent:review` | has an open loop pull request (`Closes #N`), also while its CI still runs; the pull request's `pr:*` label shows CI |
| `agent:failed` | stopped without a pull request; the reason is in the issue comment |

- Starting a build swaps `agent:ready` for `agent:running` in one call. Each tick, an issue with an open loop pull request gets `agent:review` and loses `agent:running` and `agent:ready` (log: `issue-<n>: has PR #<p>, agent:review`).
- A build that handed over a pull request never holds its branch: when its worktree still has uncommitted changes, the tick saves them as `archive/<key>-<time>.patch` in the state folder and removes the worktree. A build with no pull request keeps its worktree.
- A build that ends without a pull request swaps `agent:running` and `agent:ready` for `agent:failed`. To rebuild, remove `agent:failed` and add `agent:ready`; an issue with only `agent:failed` is started again only by the retry rule (Self-repair), and an issue with no status label is never started. An old issue with both `agent:ready` and `agent:failed` is left alone.
- The plan limit sends the issue back to `agent:ready` alone.

## What a tick does

- First, open loop pull requests with an owner approval comment are merged when the checks of ADR-016 hold (see Review from the phone).
- The tick itself removes the `pr:*` labels of merged or closed loop pull requests and `agent:review` from the issue they close, and `agent:ready` from closed issues; it starts no build for that.
- A loop pull request with no status label, no open change request, a report link in its body and every check green gets `pr:ready-for-review` from the tick itself, so it needs no build for that (log: `pr-<n>: CI is green and the report is linked; pr:ready-for-review`). At that moment the tick adds `## Guard files changed` above `Closes #` in its body: one backticked path per bullet for every guarded file the pull request changes against its base (`git diff --name-status origin/<base>...origin/<head>`), or `None.`. Guarded means what `before-edit-check` guards in loop mode: a `.claude` or `.github` folder, `.mcp.json`, `plugins/` and `.claude-plugin/` at the git root, the gate files, and a test that is not new under `checks.protected_test_dirs`. When the list is not empty it sends `PR #<n> ready for review for #<i>`, and every message about that pull request ends with ` (changes guard files)`. A diff that cannot be read leaves the pull request for the next tick (log: `guard files not read`). The epic pull request gets the same section for the whole epic branch against `main`, refreshed when a task joins it.
- Pull requests of the loop that need a run go first (an open change request, no status label, ready but CI red), then the oldest `agent:ready` issues.
- An issue is skipped when it is `agent:running`, `agent:review` or `agent:failed` (except a retry, see Self-repair), when a `Depends on #M` is still open or #M was closed as not planned, or when `agent:ready` was added by anyone but `hungle-agilityio`. There is no limit on open pull requests; only `AGENT_CONCURRENCY` and these rules limit the builds.
- An issue labelled `risk:high`, or whose body names `migrations/` or `models.py`, runs alone.
- Before an issue build starts, the tick writes the issue body to `issue-<n>-body.md` in the state folder and runs `.flow/loop/pinned_tests.py --unlisted` on it (through its host, so tests fake it). When the script lists pinned tests the issue does not name, the build still starts and its prompt gets one more line: `Pinned tests not listed: <path::test, ...>. Settle them with the self-fix step before you write code.` (spec fail-fix, AC6).
- An `agent:ready` issue with a comment whose first lines are `<!-- work-queue -->` and `<!-- self-fix -->`, posted after its last build started, goes before every other ready issue, the oldest self-fix first. Dependencies, the file-overlap guard and `AGENT_CONCURRENCY` still apply. A `needs-decision` stop after a self-fix is a decision stop: no retry, one ntfy message (AC7, AC8).
- Every issue build gets `allowed-edits` in its run folder: every path of `## Files likely touched` and of `## Existing tests that change` (without `::test`), one per line, relative to the project folder. The tick starts `claude -p` with `FLOW_ALLOWED_EDITS` set to that text (empty when the issue lists no path), and `before-edit-check` lets the build edit exactly those files, guarded ones included (ADR-023). A pull request round uses the list of the issue it closes, as that issue reads now.
- A build that times out or fails before its pull request: the issue gets `agent:failed` and a comment with the last 20 log lines; the worktree stays. The plan limit: the issue goes back to `agent:ready` and new builds pause for 60 minutes.

## Stacked tasks

When the tick merges a pull request that another loop pull request is based on, it merges without `--delete-branch`, moves each direct child to base `main` (it stays open and is merged on a later tick under the usual rules), and only then deletes the parent's branch (`~/.starter/branch-delete` lists branches waiting; a failed delete is logged and retried). A pull request nothing is based on is merged with `--delete-branch` as before. A closed pull request does not take `agent:review` from an issue while another open loop pull request closes it (#180).

A task that depends on others starts early when exactly one dependency (#P, the parent) is unmerged and its loop pull request #Q is open, not a draft, `pr:ready-for-review`, with at least one check and all of them green. Two or more unmerged dependencies, or a parent without such a pull request, keep the task waiting. A parent closed as not planned does not count. A green stacked pull request can itself be the parent of the next task (a chain).

The build starts in a worktree detached at `origin/<branch of #Q>` and is told `Stacked on pull request #Q: branch from origin/<branch> and open the pull request into <branch>.` The start message is `Agent flow starter started #N on top of PR #Q: <title>`. `~/.starter/stacked/<N>` holds #Q, its branch and its head commit. The files of #P (and of its own parents in a chain) do not hold the child; a file shared with any other running or in-review issue still does.

The tick never merges a pull request whose base is not `main`. An approval on it gives one message, `PR #<n> not merged: it waits for its parent PR #<Q>`, per approval; the approval stays valid and the pull request merges at a later tick, after its parent, by the rules of ADR-016.

When the parent is merged, each open pull request based on its branch is given base `main` (`gh pr edit <n> --base main`, when GitHub has not done it) and is from then on a normal loop pull request: updated from `main`, and `/redo merge origin/main ...` on a conflict. When the parent is closed without merge, each open child gets `pr:blocked`, a comment and one message `Agent flow starter PR #<n> blocked: its parent PR #<Q> was closed`. A change to the parent after the child started does nothing to the child until the parent is merged.

**Draft guard (#327).** GitHub's Merge button is disabled on a draft, so a stacked pull request is kept a draft until its base is `main`. The build prompt of a task stacked on a parent branch asks for `gh pr create --draft`. Each tick, every open loop pull request whose base is neither `main` nor an `epic/` branch and that is not yet a draft is converted with `gh pr ready <n> --undo`, written to `~/.starter/stack-drafts` and logged as `pr-<n>: draft while its base is <base>`. When the tick moves a base to `main` (parent merged), it runs `gh pr ready <n>` for a number in that record and removes it; a pull request not in the record is never marked ready. A failed `gh pr ready` is one log line (`draft not set` or `not marked ready`) and is tried again at the next tick. A draft stacked pull request is otherwise unchanged: approval still waits, review fixes run, and a green one can still be the parent of a chain. Tests: `.flow/loop/tests/test_stack_draft.py`.

A failed stacked issue also records `parent`, the head commit of #Q; a `stopped` failure is retried when that head moved (`the parent pull request #<Q> moved from <old> to <new>`), stacked again if #P still qualifies, from `origin/main` once #P is closed.

**Epic rescue (#329).** This handles only a pull request with a `Stacked on ... through epic/...` line, the form builds wrote before #364; a task merged into its epic branch without that line stays there (see "The epic branch"). A loop pull request merged into an `epic/` branch never reaches `main`, so its issue stays open. Each tick (`.flow/loop/epic_rescue.py`, before `tidy_ended`) looks at every merged loop pull request whose `Closes #<n>` issue is open, whose base starts with `epic/` and whose head commit is not in `origin/main`. When every pull request on its `Stacked on ... through epic/...` line is merged and no open pull request from the same head branch into `main` exists, the tick runs `gh pr create --base main --head <branch>` with the same title and the same body without the `Stacked on` line, labels the new pull request `pr:ready-for-review` when the old one had it, labels issue #<n> `agent:review` (`tidy_ended` leaves it), logs `pr-<old>: merged into <epic branch>; opened PR #<new> into main for #<n>` and sends one ntfy message. While a listed pull request is still open the tick logs `waits for #<P>` and tries again; when one was closed without merge it opens nothing and sends one ntfy message. Each old pull request is handled once (`~/.starter/epic-rescued`); a failure is one log line and is retried at the next tick. The new pull request is merged only on the owner's approval comment with green checks (ADR-016). Tests: `.flow/loop/tests/test_epic_rescue.py`.

## The epic branch

A task belongs to an epic when its issue body has the line `Part of the epic #<N>` and #N is an open issue labelled `epic`. Each tick (`.flow/loop/epic_branch.py`, after the merge step) keeps one branch per such epic, `epic/<N>-<slug>`: the slug is the epic title without `Epic:`, lowercase, other characters than letters and digits replaced by `-`, at most 40 characters (#236 "Epic: reply to reviews" gives `epic/236-reply-to-reviews`).

- The branch is created from `origin/main` when the first `agent:ready` task of the epic is chosen, before its build starts (`epic #<N>: branch <branch> created`). Every task of the epic builds on it and opens a normal pull request into it, not a draft and with no `Stacked on` line.
- A dependency on a task of the same epic is met when that issue has `agent:in-epic`. A dependency outside the epic must be closed.
- Each tick (`merge_epic_tasks`), an open loop pull request into the branch is merged with `gh pr merge --merge --delete-branch --match-head-commit <head>`, without an owner comment, when it is not a draft, has `pr:ready-for-review`, at least one check and every check green, a `https://claude.ai/artifact/` link in its body, no open change request, no run going, and a merge state other than `DIRTY` or `BLOCKED`. At most one is merged per epic branch per tick. A pull request that is `BEHIND` is updated with `gh pr update-branch` and merged at a later tick. Nothing is merged into the branch of a closed epic.
- After the merge, by the tick or by hand, the issue gets `agent:in-epic` and loses `agent:review`, `agent:running` and `agent:ready`, and stays open until the epic pull request into `main` closes it. The tick logs `pr-<n>: merged into <branch>; #<issue> agent:in-epic` and sends one ntfy message `PR #<n> merged into <branch> (#<issue>)` (once per pull request, `~/.starter/epic-tasks-merged`).
- Only the tick pushes `epic/*` or deletes it, except that a member creates the branch of an epic they claimed before any loop task of it started (`## Team members`); a build never does. Merging `main` happens in a throw-away worktree under `~/.starter/epic-work/<N>`; the main checkout is not touched.
- When `origin/main` has commits the branch lacks, it is merged into the branch with a merge commit and pushed.
- A task pull request that conflicts with the branch (`DIRTY`, or a failed update): the tick posts once per head commit on that pull request `/redo merge origin/epic/<N>-<slug> into this branch and fix the conflict` (`~/.starter/epic-redo`). A conflict with `main`: the merge is aborted, the branch stays as it was, and one message per hour names it (`~/.starter/epic-conflict-<N>`).
- The log has one line per epic per tick: `epic #<N>: branch epic/<N>-<slug>, up to date with main`, or `..., conflict with main`.
- When the epic issue is closed and no open pull request has the branch as its base, the branch is deleted on GitHub and in the main checkout.

Tests: `.flow/loop/tests/test_epic_branch.py`, `.flow/loop/tests/test_epic_task_merge.py`.

## The epic pull request

When every open issue with `Part of the epic #<N>` has `agent:in-epic` (at least one does) and no open pull request from `epic/<N>-<slug>` into `main` exists, the tick (`.flow/loop/epic_pull_request.py`, after the step that merges `main` into the branch) opens one: title `[EPIC] <epic title without "Epic:">`, body starting with the marker, a table task → pull request → verify report link, then one `Closes #<task>` line per task and `Closes #<N>`. It sends one ntfy message `Epic #<N> is ready for your review: PR #<p>`. While the branch does not have `main` (a conflict), it waits and logs `epic #<N>: pull request waits, <branch> does not have main`.

- It starts no run while it has no `pr:*` label; `mark_green_ready` gives it `pr:ready-for-review` once its checks are green. It needs no verify report link of its own.
- The owner's approval comment merges it as any loop pull request (ADR-016, `--merge`, branch deleted); GitHub then closes the tasks and the epic.
- Any other owner comment is a change request: a loop run on this pull request, on `epic/<N>-<slug>`, pushes its fix to that branch.
- A section `## Tests changed by the tasks` lists every test file a merged task pull request changed or removed (not added), with its task and pull request, read from GitHub. Tasks reach the epic branch without a human review, so this is where the owner sees a test from an earlier task that a later task changed. If the files of a pull request cannot be read, the epic pull request waits for the next tick.
- A task that reaches the epic branch while it is open gets its `Closes #<task>` line and its lines of that section in the body at that tick.
- `main` keeps going into the branch each tick; a conflict sends one message per hour.

Tests: `.flow/loop/tests/test_epic_pull_request.py`.

## Team members

An assignee other than the owner (`hungle-agilityio`), on the issue or on its epic, makes the issue that member's work: the loop skips it (`issue-<n>: assigned to <login>; skipped`, or `assigned to <login> (epic #<N>)`), never retries it when it has `agent:failed`, and does not count it as ready. The task's own member wins over the epic's.

- Claim: `gh issue edit <n> --add-assignee @me`. An epic is claimed the same way on the epic issue.
- Give back: `gh issue edit <n> --remove-assignee @me`. The loop takes the issue at the next tick when it still has `agent:ready`.
- Hand off: `gh issue edit <n> --remove-assignee @me --add-assignee <login>`.
- A claimed issue holds the files of its `## Files likely touched` until it is closed or the member is removed, so list them before claiming: a ready loop issue that lists one of them waits (`## Guards`).
- Claiming an issue labelled `agent:running` or `agent:review` does not stop the loop's build: the tick only logs it and sends one message per issue and member (`~/.starter/member-claims`). Check the label first.
- Your branch is `<kind>/<n>-<short-description>`. The pull request for a task of an epic goes into `epic/<N>-<slug>` with `Closes #<n>` in its body, otherwise into `main`.
- When `epic/<N>-<slug>` does not exist yet (no loop task of the epic has started), create it from main with exactly the name the tick uses (`branch_name()` in `.flow/loop/epic_branch.py`): `epic/<N>-` and the epic title without `Epic:`, lowercase, every run of other characters turned into one `-`, cut at 40 characters, no `-` at either end. For example `git push origin origin/main:refs/heads/epic/<N>-<slug>`. From then on the tick keeps it up to date and opens the epic pull request as usual.
- A pull request merged by hand into an epic branch marks its task `agent:in-epic` at the next tick, so the epic's next tasks start. The tick never merges or comments on it.
- The owner clicks Merge. Only the owner's `agent:ready` hands an issue to the loop.

Tests: `.flow/loop/tests/test_tick_member_assignment.py`, `.flow/loop/tests/test_tick_member_files.py`.

## The Artifact tool check

A build needs the `Artifact` tool to publish its verify report. Each build starts `claude -p` with `--output-format stream-json`, reads the tool list of the first `init` event and starts again (three starts at most) when `Artifact` is missing.

- See the tools of a build: `grep '"subtype":"init"' ~/.starter/runs/done/<run>/session-1.jsonl`.
- `start <n>: no Artifact tool, stopped` in `log.txt`: that start had no `Artifact` tool and was stopped within seconds, before any work.
- `started 3 times without the Artifact tool`: all three starts lacked it. The issue gets `agent:failed` with the last 20 log lines; it is not the plan limit and nothing pauses.
- Every session also gets the hint to load a deferred `Artifact` tool with `ToolSearch` (`select:Artifact`), through `--append-system-prompt`.
- The 45-minute limit counts from the first start and covers all starts.

### Claude Code

The loop uses one Claude Code: the default `claude`, signed in under `~/.claude`. The tick removes `CLAUDE_CONFIG_DIR` from every `claude` it starts (each build start and the sign-in check), so another folder is never used.

It also sets `CLAUDE_CODE_ENTRYPOINT=claude-desktop` on each of them, whatever `agent.env` or the shell says: `claude -p` offers the `Artifact` tool only with that value. `agent.env` has no Claude Code keys; old `CLAUDE_CONFIG_DIR` or `CLAUDE_CODE_ENTRYPOINT` lines in it are ignored.

- **Signed out.** Before it starts a build, the tick runs `claude auth status`. When `loggedIn` is false it starts no build and changes no label, so `agent:ready` issues build in the first tick after you sign in again. It sends one urgent message, and again only after a later check found Claude Code signed in. Sign in with `claude auth login`. When the status cannot be read, the tick goes on as before.

## Review from the phone

Review a loop pull request on GitHub like any other (ADR-016):

- **Approve:** write a comment on the pull request whose whole text is one of `/merge`, `merge`, `lgtm`, `approved`, `approve`, `looks good`, `look good`, `ok`, `duyệt`, `ship it` (any case, a trailing `.!,:;` is fine). "lgtm but rename X" is a change request, not an approval. The tick merges at its next run when the approval is newer than the loop's last commit (an update from `main` does not count), the pull request has `pr:ready-for-review`, every check is green, no change request is open and no run of it is in progress. Behind `main`: it updates the branch and merges at a later tick. A conflict: it posts `/redo merge origin/main into this branch and fix the conflict` and you approve again after that round. Red CI, `DIRTY`, `BLOCKED` or a failed merge: no merge and one message "not merged: <reason>". After the project chat approves, a thread posts `/merge` and runs one tick.
- **Ask for a change:** any other comment on the pull request, a comment on a line, or a comment starting with `/redo` on the issue. Only comments made after the pull request was opened count.
- **Marks**, all made with your login: 👀 the loop is working on it; 🚀 done (a reply says `Done in <sha>: ...`), or on an approval, merged; 😕 the loop cannot do it (the reply says why), or on an approval, not merged, so approve again. Add 🚀 yourself to make the loop skip a comment.

## Guards

The tick does not start a ready issue (ADR-015):

- while any issue named on a `Depends on` line is still open (every `#number` on the line counts);
- while one of its files (the backticked paths in the bullets of `## Files likely touched`) is also a file of an open `agent:running` or `agent:review` issue, or of an issue chosen earlier in the same tick: the log says `issue-<n>: waits for #<m>, which also touches <path>`; or a file of an open issue that has a member (on the issue or its epic), with any label: the log says `issue-<n>: waits for #<m> (member <login>), which also touches <path>`, or `(member <login>, epic #<N>)` when the epic gave the member. A running or review issue keeps the first line;
- with other builds, when its body lists no file: it runs alone, like `risk:high`;
- in a tick where the latest completed `Checks` run on `main` is not green: pull request runs still start, and ntfy says `main is red at <sha>: <run url>` once per commit. An unreadable run counts as green, with a log line.

The log lines are in the tmux window and in the tick's output.

## Self-repair

- **Pull `main`.** After taking the lock, the tick fast-forwards the main checkout (`git fetch origin main`, `git merge --ff-only origin/main`) when it is on `main` with no tracked changes; the new code runs from the next tick. Another branch, tracked changes or a failed fetch or fast-forward: no pull and one ntfy per reason.
- **Only the owner's pull requests.** A pull request from a fork, or opened by another login, is never the loop's, even with the marker.
- **Plan limit.** Recognised also as `extra_usage`, `usage_limit` and "hit your ... limit", whatever the exit code, as long as the build had not handed over: the issue goes back to `agent:ready` and builds pause 60 minutes.
- **Handed over.** An open issue with `agent:ready` and `agent:review` loses `agent:ready`, so a closed pull request is not rebuilt; add `agent:ready` again to rebuild it. An old `agent:ready` + `agent:failed` issue is left alone for the owner to decide.
- **A build that needs your decision (`decision` kind, #260).** When a build ends without a pull request and a comment on the issue, posted after the run started, holds both `<!-- work-queue -->` and `<!-- needs-decision -->`, the tick records the failure with kind `decision` (checked before the tick posts its own end comment; a marker from an earlier run is ignored). It is never retried, whether `main` or a parent pull request moves; adding `agent:ready` again by hand restarts it. One message per stop: `Agent flow starter #<n> needs your decision: <issue link>`.
- **Retry of a failed issue.** When a build of #N ends with `agent:failed`, the tick writes `~/.starter/failed/<N>` (the `origin/main` commit, `kind`, `retries`). A `transient` end (timeout, no exit code, an error code, no `Artifact` tool) is retried at the next free slot after the ready issues; a `stopped` one (no pull request, or the build gave up itself) only after `origin/main` moved. Each retry starts from a fresh branch (old ones go to `archive/`), comments `Retry <k> of 3: <reason>.` and sends `Agent flow starter retrying #<N> (<k> of 3)`. After 3 retries the issue stays `agent:failed` and one message says it needs you. The plan limit changes no record; restarting the issue by hand or closing it moves the record to `~/.starter/archive/`, so the count starts again.
- **`archive/` branches.** When a kept worktree is moved aside, its branch (and, for an issue, every local `bug/<n>-`, `feat/<n>-`, `task/<n>-` branch) is renamed `archive/<branch>-<unix time>`. Nothing is deleted.

## Phone messages (ntfy and Slack)

Every message goes to ntfy when `NTFY_TOPIC` is set and to Slack when `SLACK_WEBHOOK_URL` is set (both, one or none). A failed Slack post writes the log line `Slack post failed` and does not stop the tick.

**Slack, once:** create a Slack app (api.slack.com/apps, From scratch), turn on **Incoming Webhooks**, **Add New Webhook to Workspace** and pick a channel, copy the webhook URL into `.flow/loop/agent.env` as `SLACK_WEBHOOK_URL=...` (git-ignored; `SLACK_WEBHOOK_URL` is a secret and must never be committed), then set that channel's notifications to **All new messages** in the Slack app on the phone.

Each ntfy post has the title `Agent flow starter` and a priority (#167). "Rings" is `yes` for `Priority: high` (the phone rings) and `no` for `Priority: low` (the message arrives silently in the ntfy app). A message not in this table is sent with `Priority: high`. Slack gets the plain text without a priority.

| Message | Rings | When |
|---|---|---|
| `Agent flow starter started #<n>: <issue title>` | no | the tick started an issue build |
| `Agent flow starter working on PR #<p> (<k> change requests open)`, or `(CI)` | no | the tick started a pull request run; `<k>` counts the owner's `/redo` comments newer than the last commit |
| `Agent flow starter PR #<p> needs you: <pr:blocked or pr:ci-failed>` and the link | yes | once per pull request, label and head commit |
| `Agent flow starter PR #<p> merged (#<n>); main is now <sha>`, or `...; main checkout not updated: <reason>` | no for `main is now <sha>`, yes for `main checkout not updated` | a loop pull request was merged (by anyone), announced once after the tick pulled `main`; the first run only records the merged ones |
| `Agent flow starter waiting: <k> ready issues blocked`, then one line `#<n> waits for #<m>: <reason>` per blocked issue and blocking issue (`review PR #<p>`, `building`, `no pull request yet`, `closed as not planned, remove the dependency or reopen it`; for a shared file `#<n> waits for #<m>, which also touches <path>`) | no | a ready issue is held back by a dependency or a shared file, also while builds run; again only when the text changes (`~/.starter/last-blocked`); not sent when the pull request limit is reached |
| `Agent flow starter PR #<p> opened for #<n> (<status label>)`, the pull request link, `Report: <link>` | yes | an issue build ended and an open loop pull request closes that issue (also after an error or a timeout that came after the pull request) |
| `Agent flow starter PR #<p> updated for #<n> (<status label>)`, the same two links | yes | a pull request build (a `/redo` or a CI fix) ended normally and the pull request is still open |
| `Agent flow starter build for issue #<n> failed: <reason>` | yes | an issue build ended without a pull request |
| `Agent flow starter build for pull request #<p> <reason>` | yes | a pull request build failed or timed out |
| `Agent flow starter loop paused 60 minutes: plan limit reached (<key>)` | yes | the Claude plan limit was reached |
| `main is red at <sha>: <run url>` | yes | the latest completed `Checks` run on `main` is not green; once per commit |
| `Agent flow starter main checkout not updated: <reason>` | yes | the tick could not pull `main`; the first time, and again every 6 hours while the same reason is there (`~/.starter/last-pull-problem` and `last-pull-problem-sent`); a successful pull clears both |
| `Agent flow starter build for <issue #n \| pull request #n> did not start: <step> failed` | yes | a start failed; once per key and step until that key starts |
| `Agent flow starter queue empty, <w> pull requests waiting` | no | nothing to start and nothing running; again only when the text changes |
| `Agent flow starter Claude Code is not signed in (~/.claude); builds wait. Sign in with: claude auth login` | yes (urgent) | `claude auth status` says `loggedIn` is false; no build starts; once, and again after a signed-in check |
| `Agent flow starter loop started on <host name>` | yes | `uv run python .flow/loop/agent_tick.py started`, by hand or from launchd at login; takes no lock, runs no tick; sends nothing without `NTFY_TOPIC` |
| `Agent flow starter site is down since <HH:MM> (Vietnam time): <reason>` | yes | after two failed probes in a row, once per outage |
| `Agent flow starter site is back after <m> minutes` | no | the first good probe after a down message |

The loop's open pull requests with their status labels: <https://github.com/hungle-agilityio/agent-flow-starter/pulls?q=is%3Apr+is%3Aopen+%22work-queue%22+in%3Abody>

## Release

`uv run python .flow/loop/release.py` turns the newest `main` commit into a sprint release. Run it by hand in the main checkout on the Mac mini, on the owner's request; the loop never runs it. It fetches `origin`, then in one `git push --atomic` (no force, `main` untouched) creates the branch `release/sprint-N` (one more than the highest on `origin`), an annotated tag `vYYYY.MM.DD` (Vietnam date, `.2`, `.3` for more that day) and moves `deploy`, which Render follows. It then prints the branch, the tag, the commit, the merged pull requests since the last release and `Render deploys branch deploy after Checks pass.`

`--dry-run` prints the same plan (commit, branch, tag, pull requests) and pushes nothing.

After the push it creates the GitHub Release page of the new tag: it writes `<loop.state_dir>/release-<tag>.md` (the two pull request groups, and with `--notes-url <url>` a last line `Release notes: <url>`) and runs `gh release create <tag> --title <tag> --notes-file <file> --verify-tag`. On success the first line of the output is `Release page: <url>`. If the page cannot be created (`gh` fails, is missing or takes more than 60 seconds) the release still exits 0 and stderr gets one line `warning: GitHub Release not created (<reason>); run: gh release create ...` with the command to run again. The step is skipped when `origin` is not a GitHub URL and in `--dry-run`.

When `.claude/project-instructions.md` on the release commit differs from the last release (`origin/deploy`), or on a first release when the file exists, the plan ends with `Project settings: .claude/project-instructions.md changed since the last release; paste it into Project settings.` (in `--dry-run` too; the deploy line stays after it). It reads git objects only; if that check fails the line is left out and the release goes on.

It refuses with exit 1 and one line, pushing nothing, when the newest `Checks` run of the commit is missing, still running or not successful; when `origin/deploy` already points at the commit (`nothing new to release`); or when `origin/deploy` is not an ancestor of the commit.

## Live check

`uv run python .flow/loop/live_check.py [--commit <commit>]` checks the live site after a release; the release thread runs it after `.flow/loop/release.py`. Without `--commit` it runs `git fetch origin` and checks `origin/deploy`. It waits until `<url>/healthz/` answers 200 with `X-Commit` equal to the commit (one request every 20 seconds, at most `wait_minutes`), signs in as `username` in headless Chromium, opens every step of `.flow/loop/regression_screens.json` with its load time, then checks five security headers and redirects (`https-redirect`, `frame-options`, `hsts`, `login-required`, `healthz`). It takes no screenshot, writes no file and prints no page text or setting value. Install the browser once with `uv run playwright install chromium`.

The table `[live]` of `.flow/flow.toml` holds `url`, `username`, `wait_minutes`, `load_warn_seconds` and `persistent_database`. `.flow/loop/agent.env.example` lists three variables for `agent.env`: `LIVE_CHECK_PASSWORD` (the password of `username` on the live site; the only one this check reads), `RENDER_API_KEY` and `RENDER_SERVICE_ID` (for `.flow/loop/rollback.py`). A variable set in the environment replaces the file's value.

Every line goes to stdout:

- `live: <commit> after <m>m<ss>s`: the commit is served.
- `PASS <name> <s>s` or `PASS <name>`: the step or the check passed.
- `SLOW <name> <s>s (over <n>s)`: the step passed but took more than `load_warn_seconds`.
- `FAIL <name>: <reason>`, `FAIL wait: ...`, `FAIL sign-in: ...`: what failed.
- `result: pass`, `result: pass, <k> slow` or `result: fail`: the last line.

Exit codes: 0 every check passed (SLOW counts as passed), 1 a line is FAIL, 2 the check could not run (no `[live]` table, `LIVE_CHECK_PASSWORD` not set, an unknown commit, a failing git command, an unreadable `regression_screens.json`, Chromium cannot start), with one line on stderr and no result line.

## Rollback

`uv run python .flow/loop/rollback.py [--dry-run] [--to <tag>]` returns the live site to an earlier release through Render's API; the release thread runs it on the owner's request (first `--dry-run` on a card, then the real run). It runs `git fetch origin --tags`, takes the newest release tag (`vYYYY.MM.DD` or `vYYYY.MM.DD.N`) on `origin/deploy` as the current release and, as the target, the release tag before it on another commit, or the tag given with `--to`. It finds Render's newest `live` or `deactivated` deploy of the target's commit and asks Render to roll back to it. It reads two variables from `agent.env` (a variable set in the environment replaces the file's value): `RENDER_API_KEY` (a secret; it never appears in any output) and `RENDER_SERVICE_ID` (`srv-...`).

It prints `Current: <tag> <sha7>`, `Roll back to: <tag> <sha7> <subject>`, `Render deploy: <id>`, the number of migrations since the target, and `Pull requests undone:` with the pull requests merged since the target (as `release.py` lists them) or `  (none)`. `--dry-run` stops there and changes nothing. Without it, it starts the rollback and prints `Rollback started. Check it with: uv run python .flow/loop/live_check.py --commit <sha>`.

It refuses with exit 1 and one line on stderr, before any change: no `[live]` table; `RENDER_API_KEY` or `RENDER_SERVICE_ID` not set; `origin/deploy` missing or not on a release tag; no earlier release; a `--to` tag that is not an earlier release on `origin/deploy`; migrations since the target while `[live] persistent_database = true` (write a reversing migration on `main` and release it); a failing git command; no Render deploy of the target; a Render answer other than 2xx or none within 30 seconds.

The rollback never moves `deploy` or a tag and pushes nothing, and Render's Auto-Deploy stays on (only the dashboard's Rollback button turns it off). So the next release deploys as usual: fix the problem on `main`, then release again.

## Uptime

`uv run python .flow/loop/uptime.py` makes one probe of the live site: a `GET` of `/healthz/` at `live.url` (60-second timeout). The site is up when the answer is 200 with the body `ok`. `.flow/loop/start-loop.sh` runs it after every tick, so every 5 minutes; a failed probe never stops the loop, and the script always exits 0. Without a `[live]` table it does nothing.

After two failed probes in a row it sends one message, `Agent flow starter site is down since <HH:MM> (Vietnam time): <reason>` (`HTTP <status>`, `timeout after 60s` or `no connection`); a single failure sends nothing, because the free Render service can be slow to wake. The first good probe after that message sends `Agent flow starter site is back after <m> minutes`. Messages go to ntfy and Slack like the tick's (`NTFY_TOPIC`, `SLACK_WEBHOOK_URL`).

The state is `~/.starter/uptime.json`: `{"failures": <n>, "down_since": "<ISO time>" or null, "alerted": true or false}`; a missing or unreadable file counts as no failure.

After this change reaches the Mac mini, restart the loop once (stop it, then start it) so the new loop line with the probe is used.

## Kept worktrees

Each tick removes a kept `worktrees/issue-<n>` when issue #n is closed and a kept `worktrees/pr-<n>` when pull request #n is closed or merged, never the folder of a running build or of open work. A moved-aside folder `<key>-<unix time>` is removed 3 days after that time. The checked-out branch is first renamed `archive/<branch>-<unix time>` (a detached worktree has none); no branch is deleted, so the commits stay. At most 10 folders per tick; a failed `git worktree remove` is logged and the tick goes on. The log line is `<key>: closed, worktree removed`.

## Tests

`uv run pytest .flow/loop/tests -q --no-cov` (gh, git, claude and the clock are faked; CI runs them in "Hook and skill tests").
