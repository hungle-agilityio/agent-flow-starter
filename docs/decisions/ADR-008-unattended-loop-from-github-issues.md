# ADR-008: An unattended loop works GitHub issues and reports once

- Status: Accepted (the stop at a local commit is replaced by ADR-009; parts changed by ADR-012)
- Date: 2026-10-26

## Context

The user wants to talk to Claude from a phone or another laptop and not type in the session on the server. Compared: the course "AI-native SDLC playbook" (6 stages), `SOFTWARE_FACTORY_PLAYBOOK_v3.0` (label-driven GitHub Actions on a self-hosted runner) and this project (commands typed one by one, Gates 1 to 3). Constraints: Claude Pro login on the Mac mini (no API key), GitHub Free (no branch protection), one repository.

## Decision

A `/loop` session on the Mac mini runs the `work-queue` skill. Issue labelled `agent:ready` is taken, analysed, decided (grill-me answered with its own recommendations), built, tested, reviewed, verified, committed locally, and reported as an artifact. Every open point is decided and listed once at the end; nothing blocks an issue. Gate 1 is the label, Gate 2 is the report, Gate 3 (push, pull request) was unchanged here; ADR-009 relaxes it for the loop's own branch.

Rejected:
- **Playbook Actions workflows** (`agent-build`, `agent-resume`, `release`, `monitor`): untested skeletons, need a runner service that reads the macOS login Keychain, and add a second trigger path. Revisit when the loop has run on 5 issues.
- **API key in secrets**: Pro login is enough; a key would be one more secret.
- **Branch protection / required reviews**: needs a paid plan. Replaced by the hooks and by Gate 3. (Replaced by ADR-015: the repository is public, so a ruleset on `main` is free.)
- **`REVIEW.md`, gitleaks, evals, Makefile**: `reviewer` and the commit hook already cover review and secrets; evals wait for real runs.

## Consequences

- Hooks `before-edit-check` and `before-finish-check` act only when `FLOW_LOOP=1`, so interactive work is unchanged. They see edit tools, not what a shell command writes.
- The loop shares the Pro usage limit with the user's own sessions; one loop at a time.
- Decisions the user settled with `grill-me` travel in the issue and a `Decisions` comment; the loop only fills what is missing.
- A decision made unattended can be wrong. The report lists the ones that could go the other way, and `/redo` reverses them on the same branch.
- Done by a person: the two hooks and the loop's git permissions are in `.claude/settings.json`. Still to do: review on pull requests, evals.
