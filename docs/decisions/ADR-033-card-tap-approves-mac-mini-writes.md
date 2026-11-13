# ADR-033: A card tap in a cloud thread approves the GitHub writes the thread hands to the Mac mini

- Status: Accepted
- Date: 2026-11-12

## Context

Every GitHub write goes through a Remote Control session on the Mac mini with the owner's `gh` login (ADR-011). The Mac mini session gets no card presses from the cloud thread, so for a while it asked the owner to type a letter ("A") before each write, which broke the rule "choices, never type" (retro issue #487). On 2026-11-12 the retro thread handed the Mac mini session the exact writes (issue texts as files, `gh` commands, labels) in the instructions of `start_remote_control`, and it posted #548, #549, edited #531 and opened #550 with no typed letter, after the owner had chosen on cards. The proposal in #487, a one-line approval file in `~/.starter/handoff/` that the Mac mini session trusts, was rejected: any thread, or text injected into one, could write that file, so Claude could approve for the owner.

## Decision

1. **The card tap is the approval.** A choice the owner taps on a card in a cloud thread is recorded by the platform as the owner's own message. The cloud thread then hands the Mac mini session the exact writes that choice approves (texts as quoted heredocs, every `gh` command, labels, the issue or pull request numbers), and names the card and its time. The Mac mini session runs them without asking for a letter.
2. **Only what the card asked.** The writes handed over must be the ones the card named (for example "Merge PR spec #550" approves the spec issues of #550 after its merge, not other issues). Anything else needs its own card.
3. **No approval file.** No file, comment or message written by Claude counts as the owner's approval on the Mac mini.
4. **Limits that stay.** A Mac mini session that has stopped (parked) starts again only when the owner writes in the thread; the thread says so in one line. `gh pr merge` may still be refused by auto mode; then the owner clicks Merge on GitHub.

## Consequences

- One tap is enough for a GitHub write when the Mac mini session is running.
- A parked session still needs one written message to wake it; that is a platform limit, not an approval.
