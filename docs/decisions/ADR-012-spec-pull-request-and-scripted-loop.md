# ADR-012: Gate 1 is a spec pull request; scripts drive the loop

- Status: Accepted (changes parts of ADR-008, ADR-009 and ADR-011)
- Superseded in part by ADR-023 (no agent:manual)
- Date: 2026-10-28

## Context

The owner wrote a target flow in a Notion page ("Từ ý tưởng đến pull request với agent") and an artifact. It is based on the Software Factory v3.0 playbook and the AI-native SDLC course. Compared with ADR-011 it changes both halves:

- **Project:** the approval before any code is a spec pull request (`intent.md`, `spec.md`, `tasks.md`) instead of an "OK" in the chat.
- **Loop:** deterministic scripts start one fresh `claude -p` per issue, with a time limit, and a separate read-only `claude -p` reviews it. Today one interactive session runs `work-queue`.

The loop's rules lived only in skill text, and several real failures came from that. A `/redo` blocked by a hook was retried on every run (PR #35). A run had no time limit. Nobody checked who labelled an issue `agent:ready`. On 2026-10-27 a parallel loop had been planned as two sessions with a `mkdir` lock (issue never posted).

## Decision

The owner decided (2026-10-28):

- **The Notion design is the target.** It replaces the two-session parallel plan of 2026-10-27. Parallel runs come from one tick script that starts several `claude -p`, so no lock between sessions is needed.
- **Change requests stay `/redo` comments for now.** The loop opens pull requests with the owner's token, and GitHub does not let the author of a pull request request changes on it, so the Request changes review of the Notion design does not work yet. A separate machine GitHub account is deferred. The later loop issue adds from the design: at most 3 rounds, `/replan`, and a blocked `/redo` tried once.
- **The Gate 2 report is a comment in the pull request** that links to the verify report (screenshots, masking check) built by `build-verify-report` and `share-report`.
- **No branch protection.** A private repository needs a paid plan for it. The hooks keep blocking merges and pushes to `main` in loop mode. (Replaced by ADR-015: the repository is public, so a ruleset on `main` is free.)
- **Fast lane for Easy work.** An Easy request (one task, `risk:low`, no new rule, no migration) skips the spec pull request. The short spec goes in the issue body and Gate 1 is the owner's "OK" in the Project. The owner wants the flow simple and easy to control.
- **The spec pull request is opened and merged from the Mac mini** through Remote Control with `gh` and the owner's login, like issues and comments (ADR-011), so it carries no Claude attribution. The Project merges only a pull request that changes nothing outside `docs/intent/`, `docs/specs/` and `docs/design/`, and only after the owner says "Merge PR spec".
- **Names.** `FLOW_LOOP=1` keeps its meaning (the hooks' loop mode). The number of parallel runs gets its own variable, `AGENT_CONCURRENCY` (default 1).

Rejected:
- **Keep `work-queue` and add a few ideas:** limits, time-outs and the labeller check stay text that a session may skip.
- **Two loop sessions with a lock (2026-10-27):** more moving parts than one script that starts runs.
- **A machine account now:** deferred by the owner; `/redo` works with the current token.
- **Branch protection with CODEOWNERS:** paid plan; the hooks already guard. (Replaced by ADR-015: the repository is public, so a ruleset on `main` is free.)

### What it replaces

- ADR-008: one loop session at a time, and "never ask" (the target allows one `needs-info` round per issue, built in a later phase).
- ADR-009: the cap of 5 waiting pull requests becomes 3, when the loop scripts are built (superseded by ADR-018: no pull request limit).
- ADR-011: "the Project opens no pull request". It may now open and merge spec pull requests, and only those.

### Phases

Each phase is one issue, built in an interactive session on the Mac mini (`agent:manual`), because the loop may not edit `.claude/` or the loop itself.

0. Probe on the Mac mini (done 2026-10-28). `claude -p` runs on the subscription with no API key, loads the repository's agents and skills, and is stopped by `before-edit-check` in loop mode. A tool that is not allowed is refused at once, without hanging. `gtimeout` and `tmux` are not installed (`brew install coreutils tmux`). The Stop hook in `claude -p` is not tested yet.
1. This ADR, the Project instructions, the spec templates, the labels `risk:*`, `needs-ui`, `agent:manual`.
2. Loop scripts: `.flow/loop/agent-env.sh`, `.flow/loop/agent-tick.sh`, `.flow/loop/agent-run.sh`, `.flow/loop/start-loop.sh`. They add the labeller check, `Depends on`, the cap of 3 (superseded by ADR-018), `gtimeout 45m` and `--max-turns 80`, the committed `plans/issue-N.md`, the separate review `claude -p` with `VERDICT`, the Gate 2 report, auto risk flags and ntfy.
3. Asking and fixing: `agent:needs-info` with `/answer`; `/redo` limits and `/replan`; `agent:rejected`; the `allow-test-edit` label in `before-edit-check`; the "When unsure", "Never decide alone" and "Cannot finish" sections.
4. Failed handling: run log, `failed:<type>`, `attempt:<n>`, "Phân tích failed #N" in the Project.
5. Trial runs, then `AGENT_CONCURRENCY=2`; retire `work-queue`.
6. Later, when needed: power-loss recovery, watchdog, healthchecks, daily report, evals.

## Consequences

- Until phase 2 is built, the current loop (`work-queue`) still builds the issues. Issues from the Project therefore keep the `Decisions` comment and the `agent:ready` label that `work-queue` reads.
- A Medium or Hard request costs one more step (the spec pull request and its merge). In return, the ACs and the task list with the files each task touches are versioned in the repository. Easy requests do not pay this cost.
- The flow still depends on the Mac mini for every GitHub write without Claude attribution.
