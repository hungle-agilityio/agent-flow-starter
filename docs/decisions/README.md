# Decisions (ADRs)

One file per decision: `ADR-001-short-title.md`, numbered in order. Write one for a non-trivial choice about architecture, tooling or a business rule.

```
# ADR-001: <title>

- Status: Proposed | Accepted | Superseded by ADR-00X
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```

## Index

- [ADR-008: An unattended loop works GitHub issues and reports once](ADR-008-unattended-loop-from-github-issues.md)
- [ADR-009: The loop opens pull requests; the owner merges](ADR-009-loop-opens-pull-requests-owner-merges.md)
- [ADR-010: A Claude Code Project is the main thread](ADR-010-claude-code-project-as-main-thread.md)
- [ADR-011: The Project takes requests to an issue; the loop builds it](ADR-011-project-takes-requests-loop-builds.md)
- [ADR-012: Gate 1 is a spec pull request; scripts drive the loop](ADR-012-spec-pull-request-and-scripted-loop.md)
- [ADR-013: One status label on each loop pull request](ADR-013-pull-request-status-labels.md)
- [ADR-014: A tick runs loop builds in parallel](ADR-014-tick-runs-builds-in-parallel.md)
- [ADR-015: Guards for parallel pull requests](ADR-015-guards-for-parallel-pull-requests.md)
- [ADR-016: The tick merges on the owner's approval comment](ADR-016-tick-merges-on-owner-approval.md)
- [ADR-017: Deploys go out only by release](ADR-017-deploy-by-release-branch.md)
- [ADR-018: Stacked pull requests, retries, no pull request limit](ADR-018-stacked-pull-requests-and-retries.md)
- [ADR-019: The flow reads .flow/flow.toml; a new project is bootstrapped by copy and rename](ADR-019-flow-config-and-bootstrap.md)
- [ADR-020: The flow is a Claude Code plugin, agent-flow](ADR-020-flow-as-a-plugin.md)
- [ADR-021: One shared branch per epic](ADR-021-epic-branch.md)
- [ADR-022: An epic is reviewed once](ADR-022-epic-reviewed-once.md)
- [ADR-023: No agent:manual; a loop build edits the files its issue lists](ADR-023-no-manual-label.md)
- [ADR-024: A loop build fixes technical stops itself](ADR-024-loop-self-fix.md)
- [ADR-025: A new project gets a stack-agnostic layout; the flow lives in .flow/](ADR-025-stack-agnostic-project-layout.md)
- [ADR-026: Every spec and issue carries a user story, Given/When/Then and a test matrix; an issue passes a zero-questions test](ADR-026-issue-pack-and-test-matrix.md)
- [ADR-027: A loop build shows its plan, gets its tests from a separate test author, checks the test matrix and records its decisions next to the spec](ADR-027-plan-tests-and-build-decisions.md)
- [ADR-028: An issue assigned to a team member is that member's work; the loop leaves it alone](ADR-028-member-assignment.md)
- [ADR-029: Every build and every epic gets /code-review; the main screens are checked in a browser in CI; one living release notes page](ADR-029-test-and-harden.md)
- [ADR-030: One clickable prototype of the whole app is the design; the work is split only after "Prototype ổn"](ADR-030-app-prototype.md)
- [ADR-031: Every release passes three automatic security checks and a Claude security review before it reaches end users](ADR-031-security-check-before-release.md)
- [ADR-032: Every release is checked on the live site and can be rolled back with one command; the loop watches uptime, Sentry gets errors, Checks scan accessibility](ADR-032-post-release-checks.md)
- [ADR-033: A card tap in a cloud thread approves the GitHub writes the thread hands to the Mac mini](ADR-033-card-tap-approves-mac-mini-writes.md)
