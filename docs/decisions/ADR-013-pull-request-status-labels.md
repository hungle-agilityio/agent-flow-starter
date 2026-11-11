# ADR-013: One status label on each loop pull request

- Status: Accepted
- Date: 2026-10-28

## Context

The owner reviews the loop's pull requests, often from the phone. A pull request showed no state on GitHub: the owner could not tell, without opening it, whether CI was green, whether the loop was still working on a `/redo`, or whether it was stuck. The issue labels `agent:*` say where the issue is, not where its pull request is.

## Decision

The owner decided (spec `docs/specs/pr-status-labels/`, issue #43):

- **Four labels, on the pull request only:** `pr:ready-for-review` (CI green, report passed), `pr:changes-requested` (the loop works on a `/redo`), `pr:blocked` (the loop needs the owner; the reason is a comment), `pr:ci-failed` (CI still red after two fixes). The loop creates them when missing.
- **Exactly one at a time.** Setting one removes the other three in the same `gh pr edit` call. Merged or closed pull requests lose their `pr:*` label.
- **Wait for CI in the same run,** at most 15 minutes, so the label is set early and never says something false. No checks reported counts as still running, never as green.
- **Two CI fix attempts per round** (a round starts when the pull request is opened and at each counted `/redo`), each commented; then `pr:ci-failed`.
- **A blocked pull request is not retried** until the owner sends a new `/redo`.
- **`agent:*` issue labels stay;** Status reports both.
- **`Bash(gh pr edit:*)` is allowed** in `.claude/settings.json`, so the loop never stops on a prompt when it changes a label.
- **The ADR-012 phase 2 scripts must keep these rules** when they replace `work-queue`.

Rejected:
- **Check CI only at the next run:** up to 30 minutes with no label.
- **`pr:ci-failed` at once, the owner sends `/redo`:** more work for the owner; the owner approved two attempts.
- **Drop `agent:review`:** a bigger change; Status and ADR-012 read `agent:*`.
- **Limit `gh pr edit` in the hook to `pr:*` labels:** the loop already opens pull requests; editing one adds little risk.

## Consequences

- A loop run can take up to 15 minutes longer per pushed pull request, plus the CI fix attempts.
- The rules live in the `work-queue` skill text; nothing enforces "exactly one" except the loop following it.
