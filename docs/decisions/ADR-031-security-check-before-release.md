# ADR-031: Every release passes three automatic security checks and a Claude security review before it reaches end users

- Status: Accepted
- Date: 2026-11-12

## Context

On 2026-11-12 the owner asked for a step that checks the app's security before a release reaches end users. The analysis (`docs/specs/security-check/intent.md`) found: CI ran lint, types and tests but nothing about security; `manage.py check --deploy` with the production settings gave three warnings (no X-Frame-Options, no HSTS, no redirect to HTTPS); `pip-audit` on the locked runtime dependencies was clean but nothing ran it; the sign-in page let anyone guess passwords without limit; `.flow/loop/release.py` released whatever passed Checks.

Spec `docs/specs/security-check/spec.md` (pull request #494); epic #504 (pull request #534): #505 production settings, #506 sign-in lock, #507 security checks in the release script; #508 is this record and the Project rules.

## Decision

1. **Production settings.** Every response carries `X-Frame-Options: DENY`. With `DJANGO_DEBUG=0` the app redirects to HTTPS (`/healthz/` exempt, Render calls it over plain HTTP) and sends HSTS for one year, without subdomains or preload. `SILENCED_SYSTEM_CHECKS` holds exactly `security.W005` and `security.W021` (the subdomains and preload warnings), so `check --deploy --fail-level WARNING` passes and prints `(2 silenced)` (owner's choice during the issue checks; it replaces the `0 silenced` of spec AC3).
2. **Sign-in lock.** 5 wrong passwords for one username within 15 minutes lock that username for 15 minutes with `Too many failed sign-in attempts. Try again in 15 minutes.` Own code in `src/login_limit.py`, counts in Django's default cache, no model, no dependency; unknown usernames are counted the same way; a restart clears the locks.
3. **Three automatic checks block a release.** `.flow/loop/release.py` runs `.flow/loop/security_check.py` on the release commit in a temporary worktree: deploy settings (`check --deploy`), dependencies (`pip-audit@2.10.1` on `uv export`), secrets (the added lines of the release diff, or every tracked file on the first release; reported as `<path>:<line>`, never the text). A failed check, or one that could not run, refuses the release and `--dry-run` alike with `security check failed: <names>`. The block prints after the Tag line, then `Security review diff: <range>`.
4. **One Claude security review per release.** After the dry-run passes, the release thread on the Mac mini reviews `git diff <Security review diff>` with the method of Claude Code's `/security-review` (only high or medium severity with high confidence). The release card shows the findings; with none it is A "Phát hành (đề xuất)", B "Huỷ"; with any it is A "Huỷ (đề xuất)", B "Phát hành vẫn". A refused dry-run gets a card with "Huỷ" only. The review never blocks by itself: the owner decides.
5. **The live site is checked after the deploy** by `.flow/loop/live_check.py` (ADR-032), which takes the live part of this check: HTTP to HTTPS, X-Frame-Options, HSTS, a page without a session goes to `/login/`, `/healthz/` over HTTPS.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 What blocks a release? | The three automatic checks block; the Claude review is shown on the card and the owner decides | Everything blocks; nothing blocks (report only) | Automatic checks give a sure answer; an AI review can be wrong, so a person decides |
| Q2 Where does the Claude security review run? | Once per release, on the diff since the last release, by the release thread | In every loop build; not at all | One run per release, right before end users see it |
| Q3 How are the three deploy warnings fixed? | All three now: X-Frame-Options DENY, HTTPS redirect (`/healthz/` exempt), HSTS one year without subdomains or preload | HSTS for one hour first; only allow the warnings | Render serves only HTTPS, so one year is safe; without subdomains and preload it can still be undone |
| Q4 How is password guessing stopped? | Own code: 5 failures in 15 minutes per username lock it for 15 minutes | `django-axes`; later | Sign-in is open on the internet; a cache counter needs no migration and no dependency |
| Q5 Is the live site checked after a deploy? | Yes, after every release, by the post-release epic (ADR-032) | No | Some settings only show on the live site behind Render's proxy |
| HSTS warnings W005, W021 | Silence exactly these two | Turn on subdomains and preload | Q3 chose no subdomains and no preload; preload cannot be undone quickly |

## Consequences

- A release can be refused by a tool that cannot run (no network for `pip-audit`); the fix is to run it again, not to skip the check.
- Anyone can lock a username for 15 minutes by guessing; the lock ends by itself.
- Files git treats as binary and non-UTF-8 files are not scanned for secrets (`docs/specs/security-check/decisions/T3.md`).
