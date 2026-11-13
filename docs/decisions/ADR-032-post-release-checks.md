# ADR-032: Every release is checked on the live site and can be rolled back with one command; the loop watches uptime, Sentry gets errors, Checks scan accessibility

- Status: Accepted (replaces item 5 of ADR-017)
- Date: 2026-11-12

## Context

On 2026-11-12 the owner asked for four steps after a release: a check of the key screens on the live site, a rollback to the previous release that takes migrations into account, monitoring with alerts, and accessibility and speed checks of the main screens. The Day 14 and Day 15 audits had found the same gaps: after `.flow/loop/release.py` nothing looked at the live site, the only rollback was Render's button, nobody was told when the site was down or threw an error, and no check looked at contrast.

The analysis (`docs/specs/post-release/intent.md`) found: the live database is SQLite rebuilt from demo data at every start, so a rollback has nothing to reverse today; Render's Rollback button turns Auto-Deploy off, so the next release silently does not deploy, while the rollback endpoint of Render's API leaves it on; the browser check only runs a local server, and the cloud cannot reach the live site, so the live check runs on the Mac mini.

Spec `docs/specs/post-release/spec.md` (pull request #501); epic #537: #538 release commit on `/healthz/`, #539 live check, #540 rollback, #541 uptime alert, #542 Sentry, #543 accessibility; #544 is this record and the Project commands.

## Decision

1. **The live site says which commit it runs.** `/healthz/` carries the header `X-Commit` from Render's `RENDER_GIT_COMMIT`, read per request; the page stays public, `ok` and free of queries.
2. **A live check after every release.** `.flow/loop/live_check.py`, run on the Mac mini by the release thread right after `.flow/loop/release.py`, waits up to `live.wait_minutes` (15) until `/healthz/` reports the released commit, signs in as `live.username` with `LIVE_CHECK_PASSWORD` from the settings file, opens the screens of `.flow/loop/regression_screens.json` with their load times (`SLOW` above `live.load_warn_seconds`, 3; a warning, not a failure) and makes the five live security checks of ADR-031 (HTTP to HTTPS, X-Frame-Options, HSTS, a page without a session goes to `/login/`, `/healthz/` over HTTPS). It ends with `result: pass` or `result: fail`. The values are in the `[live]` table of `.flow/flow.toml`.
3. **Rollback through Render's API.** `.flow/loop/rollback.py` finds Render's deploy of the previous `v*` tag and asks Render to roll back to it (`RENDER_API_KEY`, `RENDER_SERVICE_ID`). `deploy` and the tags are never moved and Auto-Deploy stays on. `--dry-run` shows the plan; the release thread shows it on a card before the real run. The fix still goes to `main` and out with the next release.
4. **Migrations.** The rollback lists the migrations between the two releases. While `live.persistent_database` is false (the database is rebuilt at every start) it goes on; when it is true and there is a migration it refuses and asks for a reversing migration released from `main`.
5. **Uptime.** `.flow/loop/uptime.py` runs after every tick of the loop (every 5 minutes), pings `/healthz/`, and sends one phone message after two failures in a row and one when the site is back.
6. **Server errors.** With `SENTRY_DSN` set on Render the app sends server errors to Sentry, with no user, cookies, request body, query string or local variables; blank means off, so local runs, tests and CI send nothing.
7. **Accessibility.** Checks run `.flow/loop/a11y_check.py` with the vendored axe-core 4.10.3 on the sign-in page and the main screens, light and dark, and fail on a serious or critical finding. The contrast findings of 2026-11-12 are fixed in `app.css`. A new project made by the bootstrap does not get this step.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 Where and when does the live check run? | On the Mac mini, by the release thread right after `release.py`; a rollback card on a failure | The tick runs it when `deploy` moves; a GitHub Actions workflow with the demo password as a secret | The owner sees the result where the release was pressed; the password stays on the Mac mini |
| Q2 How does the check know the new release is live? | `X-Commit` on `/healthz/` from `RENDER_GIT_COMMIT` | Wait a fixed 10 minutes | Never checks the old release by mistake |
| Q3 Rollback command | `.flow/loop/rollback.py` with Render's API, dry-run on a card first | Render's Rollback button by hand; revert on `main` and release again | One press, no force push, Auto-Deploy stays on |
| Q4 Rollback across a migration | List them; go on while the database is rebuilt at every start; refuse when it is persistent | Always refuse; ignore migrations | Works today and is safe the day a real database comes |
| Q5 Alert when the site is down | The loop pings every 5 minutes; a message after two failures, one when back | Every 30 minutes; UptimeRobot | Uses the tick's ntfy and Slack, no new account |
| Q6 Server errors | Sentry free plan, `SENTRY_DSN` on Render, no personal data | Render log only; Django e-mail to ADMINS | An alert with a stack trace; a blank DSN turns it off |
| Q7 Accessibility and speed | axe-core in Checks, fails on serious or critical; load time per screen in the live check, warning above 3 s | Report only; Lighthouse | axe findings are stable; speed only means something on the real network |
| Name of the password variable | `LIVE_CHECK_PASSWORD`, and the account in `[live] username` | a password variable named after Agent flow starter and a fixed `demo` (spec AC4, AC5) | The bootstrap copies `.flow/loop/` into new projects, where a variable named after Agent flow starter is refused by its tests |

## Consequences

- One-time setup by the owner: `LIVE_CHECK_PASSWORD`, `RENDER_API_KEY` and `RENDER_SERVICE_ID` in the settings file on the Mac mini, `SENTRY_DSN` on Render, and one restart of the loop so the uptime ping starts. Without them the live check and the rollback stop with a line naming the missing value, and Sentry stays off.
- The uptime ping every 5 minutes keeps the free Render service awake while the loop runs; when the loop is stopped, nobody watches the site.
- A rollback does not change `main` or `deploy`: until the fix is released, the next release would deploy the bad commit again.
- The live check and the rollback need the Mac mini; the cloud cannot reach the live site.
