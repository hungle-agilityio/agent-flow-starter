# ADR-029: Every build and every epic gets /code-review; the main screens are checked in a browser in CI; one living release notes page

- Status: Accepted
- Date: 2026-11-12

## Context

Day 14 of the training ("Test and harden") asks for three things: a QA regression and the automated suite in CI with `/loop` watching the build; `/code-review` by the developers, with ultrareview when sign-in or data is touched, and the findings fixed; and client-facing release notes drafted as an Artifact. The audit of 2026-11-12 found the suite and the loop in place, and three gaps. No regression of the main screens ran before a release. The loop's `reviewer` ran only on Hard work or on a Medium trigger, `/code-review` had been run once by hand (pull request #461), and the epic → main pull request, the only one the owner reads since ADR-022, had no Claude review. Release notes were out of scope of the release (`docs/specs/release-deploy/intent.md`), so clients were told nothing.

Spec `docs/specs/test-harden/spec.md` (pull request #491); epic #492 (pull request #518) with #493 (sensitive paths and the review level), #498 (`/code-review` in every build and on the epic), #495 (the tick starts the epic review), #496 (browser regression in CI) and #497 (client-facing pull requests in the release); #499 is this record and the Project rules.

## Decision

1. **Every loop build runs `/code-review`.** Before the pull request, the build runs the `code-review` skill on its diff at level medium. It fixes each finding or dismisses it with a reason, for at most two rounds, and the pull request gets a `## Code review` section. When the skill cannot run, the section starts with `/code-review did not run: <reason>; reviewer only.` and the `reviewer` sub-agent reviews alone.
2. **A sensitive path raises the level.** `paths.review_sensitive` of the flow config (`.flow/flow.toml`) lists path patterns for sign-in and data: models, migrations, repositories, management commands, the Claude client, the sign-in templates, settings, urls and the deploy file. `review_level.py` of the `work-queue` skill compares the files the branch really changed with that list. On a match the level is high and the `reviewer` sub-agent runs too, whatever the difficulty. When the script fails, the level is high.
3. **One epic review.** When an epic → main pull request is open, green and has no `pr:*` label, the tick starts one run that reviews the whole epic diff with `/code-review` at level high, fixes what it can in one round, one commit per kept fix, and leaves the rest for the owner in one `## Epic review` comment. Only then is the pull request marked ready for the owner. The tick starts it at most twice for one pull request and notifies the owner when the second run ended without the comment.
4. **Ultrareview stays a manual choice of the owner.** It is billed and interactive, so no loop run starts it. The owner may run it by hand on any pull request, for example one that changes sign-in or data.
5. **The main screens are checked in a browser in CI.** Checks runs the steps of `.flow/loop/regression_screens.json` (nine screens on the demo data) in a headless browser on every pull request and push, after the app tests. A console error, a failed request or a missing text fails the job. A release already waits for green Checks, so no release goes out with a broken main screen. A bootstrapped project does not get the file or the two steps.
6. **The release lists client-facing pull requests apart.** `.flow/loop/release.py` prints `Client-facing pull requests:` (a pull request that changed a file under `paths.code_dirs`) and then `Internal pull requests:`.
7. **One living release notes page.** After a release, the release thread updates the page https://claude.ai/artifact/9YeTDzCKwuvkYq2jDphaye at the same link: newest release on top, English, one section per release with its tag, one entry per client-facing pull request written from its issue's user story and ACs (what users can do now, and where). Internal pull requests are not listed. The page stays private; the owner shares it. This reverses "Release notes pages or GitHub Releases" in the out-of-scope list of `docs/specs/release-deploy/intent.md` for the notes page only; GitHub Releases stay out of scope.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 Where does the loop run `/code-review`? | Every build; high plus `reviewer` on a sensitive path | Only on sign-in and data; replacing `reviewer` | What Day 14 asks; a small cost per build; the independent reviewer stays for risky work |
| Q2 What counts as touching sign-in or data? | A list of path patterns in `.flow/flow.toml` (`paths.review_sensitive`) | The `risk:high` label | Decided from the files really changed, so a wrong risk label cannot hide it |
| Q3 Does Claude review the epic → main pull request? | Yes: the tick starts one `/code-review` at level high; the loop fixes in one round; the rest goes to the owner in a comment | Findings only, the owner decides; no review | Catches problems between tasks that no task review sees; the owner reads only what is left |
| Q4 Where does the QA regression run? | In Checks (CI), in a headless browser, on every pull request and push | Only before a release on the Mac mini; nightly in the tick | What Day 14 asks; catches the break in the pull request that made it; a release already waits for green Checks |
| Q5 How are the release notes kept? | One living page at one link, newest release on top, English, client-facing pull requests only | A new page per release; Vietnamese and English | Clients keep one link; the page already exists in that form |

The decisions each build made are in `docs/specs/test-harden/decisions/`.

## Consequences

- Every build costs one `/code-review` run on the owner's plan, and every epic one more at level high. The automatic review on every push stays removed (`.claude/CLAUDE.md`, "Removed, and why", 2026-11-03): this one runs once per build, before the pull request, and its findings are settled by the build.
- The epic review can commit to the epic branch after the task reviews, so the owner reads its comment together with the pull request.
- The browser step adds time to Checks; its timeout stays 10 minutes unless a run shows it needs more.
- A file is sensitive only when a pattern names it. A new place for sign-in or data code needs a new pattern in `.flow/flow.toml`.
- The release notes page is updated by a thread, not by code, so a release without a thread (the command run by hand) leaves the page behind until the next one.
