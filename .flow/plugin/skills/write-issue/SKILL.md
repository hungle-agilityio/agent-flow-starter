---
name: write-issue
description: Write one complete, standalone issue (bug, feature or task) from a description, following the project templates, and save it as docs/issues/<type>/<name>.md. Use when the user gives a bug report, a feature request ("can we add X") or a piece of work, when new information arrives for an existing issue, or when asked to analyse, reproduce, clarify or fill in a BUG, FEAT or TASK issue.
---

# Write an issue

The issue is read by QA, BA, clients and devs, so anyone must understand it and follow it without asking questions. It is posted as a standalone GitHub issue (with the `create-issue` skill, after the user approves it).

## 1. Output: one file

Write **one** file: `docs/issues/<type>/<name>.md`, the complete issue, built from the template of its type:

| Type | Use when | Template | Folder | Branch |
|---|---|---|---|---|
| `BUG` | Something that worked, or should work, is wrong: error, wrong value, slow, wrong text | `<templates>/bug.md` | `bugs/<name>` | `bug/<id>-...` |
| `FEAT` | Users get a new ability, or an existing page changes what users see | `<templates>/feature.md` | `features/<name>` | `feat/<id>-...` |
| `TASK` | Work with no new user-facing behaviour: cleanup, data update, configuration, document, investigation | `<templates>/task.md` | `tasks/<name>` | `task/<id>-...` |
| `EPIC` | A goal that needs between 3 and 10 issues | `<templates>/epic.md` | `epics/<name>` | none (each child has its own) |

- `<templates>` is the templates folder, `paths.templates_dir` of the flow config (`.flow/flow.toml`, else `.flow/flow.toml`).
- Follow the template's sections, in order, with nothing added or removed.
- If the type is unclear, decide from the table and say which you chose and why. If the user names a type, use it.
- The issue number is the GitHub issue number, assigned when the issue is published with the `create-issue` skill. A draft has no ID yet, and the file name does not contain one. Never invent a number. The file is `docs/issues/<type>/<name>.md`, where `<type>` is `bugs`, `features` or `tasks` (matching the issue type) and `<name>` is a short lowercase description with dashes, the same words used in the branch name (`bug/1-dashboard-wrong-score` goes with `docs/issues/bugs/dashboard-wrong-score.md`). Read `docs/issues/README.md`: reuse the existing file if the issue is already listed (then update it). Add a row (type, file, title) to that index for every new issue, with the GitHub column set to `draft`; the `create-issue` skill fills in the IID when the issue is published.
- Title format `[type] title`, for example `[BUG] dashboard show wrong score number`. The number is not part of the title.
- Two roots: issues of the app go to `docs/issues/`, issues about how we use Claude Code (the epic in `docs/learning/epics/`) go to `docs/learning/issues/`; same `<type>/<name>.md` layout and the same index file in each root. A draft stays a draft until it is created on GitHub; after that GitHub holds the status and the file is not edited again (changes go to GitHub comments).
- One issue is **one file**. Never create the four-file folder (`01-reported.md` to `04-final.md`): it was only a learning exercise. Older issues still have that folder; leave them unchanged, and read them as input if they exist for this issue.

## 2. Steps

1. **Gather.** The user's description, plus any existing files in the issue folder.
2. **Investigate** according to section 4 (reproduce a bug, look at the app for a feature, check what is touched for a task).
3. **Write** the issue file with everything you verified. What is still unknown is written as a `(proposal)` the reader can accept or change, never as a fact. Keep the label `needs-info` while anything is unconfirmed, and use `env: to confirm` when the environment is unknown.
4. **Report back in your answer** (not in the file): the path, what you verified, what could not be reproduced or decided, and the numbered open questions for the reporter, each with your proposal. The file itself has no questions section.
5. **When answers arrive,** update the issue file directly: fold each answer into the sections it changes, remove the `(proposal)` marks that were confirmed, and remove `needs-info` once nothing is left to ask. Never write an answer the reporter did not give.

## 3. Rules for every issue

1. **Plain language only** (one exception: the `## Screens to capture` block of section 7). No code, file names, function names, stack traces, commits, branches, test names or technical terms (say "the page shows an error", not "ZeroDivisionError"; "one extra lookup per location", not "N+1"). Developers find the code themselves. Do not add a failing test or a technical section.
2. **Never invent facts.** Anything unknown (which page, which value, which environment, who owns it, what "done" means) is a `(proposal)` or marked "to be confirmed". Do not guess the environment.
3. **Name the page.** The Summary and the steps say which page or screen, and state plainly if it does not exist yet, or whether it is an existing page or a completely new one. There is no Where line, ID line or Status line in the issue.
4. **Steps = user actions only.** No install, migrate, seed or run-server commands. If specific data must exist, say it inside the numbered steps with the real names and numbers (open this address, Riverside has 3 reviews rated 4, 5 and 2, look at this). There is no separate "Data needed" section.
5. **Exact results.** Give the real values or texts ("shows 3, should show 3.67") and the calculation if there is one.
6. **Labels (same set everywhere):** type (`bug`, `feature`, `task`); area (`dashboard`, `reviews-list`, ...); for bugs the kind (`crash`, `wrong-data`, `performance`, `ui`, `wrong-output`, optionally `intermittent`), the severity (`severity: low`, `severity: medium` or `severity: high`) and the reproduction result (`reproduced`, `partly-reproduced`, `cannot-reproduce`); `high-priority` only if urgent; `needs-info` while something is unconfirmed; `env: dev`, `env: staging`, `env: production` or `env: to confirm` (never guess; use `env: dev` for what you reproduced yourself locally, which is the dev environment); `deadline: <date>` only if one was given. Type line is just `Bug`, `New feature` or `Task`.
7. **Attachments:** list what exists and what is still to be added, never a file link.
8. **The issue stands alone.** It never refers to another file, to the learning files, or to "above" or "below". It may mention other issues by number (`#4`) when they are related.

## 4. Rules per type

- **BUG:** Reproduce before you write. Run the app locally and follow your own steps. Before changing local data, back up `db.sqlite3` to the scratchpad and restore it afterwards. Fill Steps to reproduce, Expected result, Actual result and Environment with what you saw. If you could not reproduce it, say so and use the label `cannot-reproduce`. Never open files named `*DO-NOT-OPEN*`.
- **FEAT:** Look at the app first (read it, run it) and describe what exists today as a person sees it. Turn every undefined rule (what "good" means, what a "week" is, time zone, one location or all, filters combined or not, what to show when there is nothing) into an acceptance criterion marked `(proposal)`. Write acceptance criteria as "When \<situation>, the screen must \<result>", including the empty case. Check for other issues that touch the same page and say how they relate.
- **TASK:** Say exactly what is touched, or "nothing visible to users". If users see a change, it is a FEAT; if something is broken, it is a BUG. Every "Done when" item must be checkable by a non-technical person. State what is in and out of scope.

## 5. Git naming (only when asked to create a branch or commit)

Follow `.claude/rules/git.md`: branch as in the table above, commit message `title`, blank line, `detail`, blank line, `Part of <id>`.

## 6. Before you finish

Re-read the issue as a person who has never seen the code: do they know where, what, and how to follow the steps and see the same result? Then give the user the summary described in step 4.

## 7. Handing an issue to the loop (new request from the user)

1. Propose `grill-me` and settle the decisions with the user in the session. Fold each answer into the section it changes, in plain words; number the "Done when" items `AC1`, `AC2`, ... so a report can name them.
2. If users will see a change and the user wants it, build the UI/UX as a private artifact (states: normal, empty, error, narrow screen; demo data only, `data-sensitive` kept) and get the user's OK. No visible change: skip this step.
3. After the user's OK on the issue preview, publish with `create-issue`, then post two comments as the owner: `Decisions` (the table: question, chosen, rejected, why) and, if there is a design, `Design` (the artifact link). Technical words are fine there. The issue file stays plain and standalone.
4. Add the label `agent:ready` only when the user said OK to start; never otherwise. `work-queue` takes it from there.
5. **Screens to capture.** An issue whose change users see gets the label `needs-ui` and a `## Screens to capture` section holding one fenced `json` block: a `check-in-browser` spec (`{"steps": [...]}`) in which every step has a `goto` page and a `capture` selector for the part that changes (optional `actions`, `expect`, `absent`; `"sign_in": false` for the sign-in page; `"design"` (the prototype state the build must match; every step whose page has a state names it)). Write it at spec time from the design and the real templates, and check the selectors exist (run `browser_check.py --spec` on it when the page already exists). The build copies the block unchanged into the verify report, which shows each full page next to its close-up. A `needs-ui` issue without a valid block, or with `"steps": []`, gets no pull request: the loop labels it `agent:failed`. An issue without `needs-ui` has no section; its report runs with `--no-ui` and shows no screenshots.
6. **User story.** The issue Summary ends with the user story line taken from the spec (`As a <user>, I want <ability>, so that <goal>.`). On the fast lane there is no spec, so the line is written in the issue.
7. **Given/When/Then.** A "Done when" AC that describes what a person sees or does is written `**ACn.** Given <the starting data, with real names and numbers>, when <the action>, then <the exact result>.` An AC about a function, a query, a file or a setting keeps the plain form.
8. **Test matrix rows.** The issue has a `## Test matrix rows` section that copies its rows from the spec's `test-matrix.md`, in the feature's folder under `paths.specs_dir` of the flow config. On the fast lane the section holds the small table itself, built by the same rules as that file's template: every AC has at least one row, and every user-visible AC has a "normal" row and an "empty" row, or a row that says `n/a: <why>`.
9. **Zero-questions test**, done before `agent:ready` (step 4). Start a new sub-agent with no conversation context, give it only the issue body and read access to the repository, and ask it to list every question it would have to ask before it could build and test the issue; a fact it can find in the repository is not a question. Fix each question in the issue body (a decision goes to the user first), then run a new sub-agent on the changed body. The issue is ready only when a round returns 0 questions. The `Decisions` comment gets the line `Zero-questions test: 0 questions after <n> rounds (<k> in round 1).`
10. **Decisions file.** An issue of a task of a full-lane spec lists its decisions file under `## Files likely touched`: the path of the feature's folder under `paths.specs_dir` of the flow config, followed by `decisions/T<k>.md`, marked `(NEW)`. The build writes it (`work-queue`, "Decisions file").
11. **Plan approval.** An issue labelled `risk:high` says in its Summary that the build stops after the plan until the owner approves it.
