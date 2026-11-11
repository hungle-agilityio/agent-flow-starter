# ADR-010: A Claude Code Project is the main thread

- Status: Accepted, partly replaced by ADR-011 (threads no longer implement or open pull requests; the loop stays)
- Date: 2026-10-26

## Context

The user does not want to type in a CLI on a server. They want to settle decisions (`grill-me`) in a chat from a phone or another laptop, have the repository worked in the cloud, and get a pull request and a report. A Claude Code Project (public beta, Pro and Max) is that: one conversation that starts cloud threads, each on its own branch and pull request. GitHub issues stay the record of each piece of work; Trello is not used.

## Decision

The Project conversation is the main thread. It runs `grill-me` and the UI/UX confirmation with the user, and starts the threads that create the issue, implement it and open the pull request (`.claude/project-instructions.md`). The user merges with the Merge it button. A root `CLAUDE.md` imports the project files, because cloud threads read only the git root.

Kept, not extended: the CLI loop (`work-queue`, ADR-008, ADR-009), until a few real tasks have gone through the Project. Rejected: a second queue (`agent:ready` labels) next to the Project.

## Consequences

- Cloud threads load `CLAUDE.md` and `.claude/rules/` at the git root only. Skills, agents, commands, hooks and permissions in `settings.json` do not run there: the rules in `rules/` are text for them, not enforced. What still limits a thread: the Claude GitHub App installed on this repository only, the cloud environment's network access, and the user's Merge it.
- This partly reverses ADR-006 (config in the lab folder): the root `CLAUDE.md` imports it, so there is one source. Whether `@import` works in a cloud thread is to be confirmed with the first thread.
- The GitHub proxy rejects GraphQL, so `gh issue` and `gh pr` fail in a cloud thread (REST through `gh api` works), and it does not limit which branch a push updates: only the text keeps threads off `main`, since the free plan has no branch protection (replaced by ADR-015: the repository is public, so a ruleset on `main` is free).
- Threads run in auto mode and the Project uses the Pro limits faster (200 new threads a day at most).
- If the Project path works, the loop machinery (`work-queue`, `before-edit-check`, `before-finish-check`, the publish guard) can be removed; decide after a few tasks.
