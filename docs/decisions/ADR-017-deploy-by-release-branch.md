# ADR-017: Deploys go out only by release

- Status: Accepted (replaces decision Q3 of `docs/specs/auto-deploy/spec.md`)
- Item 5 replaced by ADR-032 (2026-11-12).
- Date: 2026-10-30

## Context

`docs/specs/auto-deploy/spec.md` Q3 had Render deploy every green merge to `main`. The owner wants the live site to change once per sprint or epic, not on every merge, and to keep each sprint as its own branch. Spec `docs/specs/release-deploy/spec.md`; the script is #103, the Render branch #105, this record and the Project command #104.

## Decision

1. **Only a release deploys.** Render follows one branch, `deploy` (`render.yaml`, `branch: deploy`, `autoDeployTrigger: checksPass`). A merge to `main` changes nothing online.
2. **Names.** Each release creates the branch `release/sprint-N` (N one more than the highest on `origin`, 1 for the first) and an annotated tag `vYYYY.MM.DD` in Vietnam time (`.2`, `.3` for more on the same day; the tag message is the branch name), and moves `deploy` to the same commit.
3. **Only `.flow/loop/release.py` pushes them.** It takes the newest `main` commit whose `Checks` run succeeded, and pushes the branch, the tag and `deploy` in one `git push --atomic`: fast-forward only, never `--force`, `+` refspecs or `--delete`, never `main`, never an existing `release/sprint-*` branch or tag. It refuses when `Checks` is missing, running or red, when there is nothing new, or when `deploy` is not an ancestor of the commit.
4. **Who runs it.** The owner asks in the Project ("phát hành"); a thread on the Mac mini runs `--dry-run`, shows the plan on a choice card and runs the release after the owner's A. The loop and Claude builds never run the script and never push `release/*`, `deploy` or `v*` tags.
5. **Rollback.** A bad release is undone with Render's Rollback button, then fixed on `main` and released again. `deploy` is never moved back, because that needs a force push.
6. **Protection** is this written rule; no GitHub ruleset for now.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1. Release branch | One branch per sprint, `release/sprint-N` | One fixed `release` branch | The owner wants each sprint kept as its own branch |
| Q2. How a release is cut | Card in the Project, Mac mini runs `.flow/loop/release.py` | Pull request from `main` into a release branch; owner pushes by hand | No typing; the released commit is the one `main` already checked, so no `.github/` change |
| Q3. Tag | Date tag `vYYYY.MM.DD`, `.2` for a second one that day | Semver; no tag | No version number to choose; easy to read |
| Q4. Protection | Written rule in this ADR | GitHub ruleset | No extra manual step for the owner now |
| Q5. Rollback | Render Rollback, then fix on `main` and release again | Move the branch back to an old tag | Moving back needs a force push, which the project never does |
| Q6. Pull request #101 | Changed by a plain comment | Close and re-issue; merge then fix | Three lines change; the verify report and branch stay (it was merged first, so #105 made the change) |
| Q7. What Render follows | A fixed branch `deploy`, fast-forwarded by the script | Script changes the branch with the Render API; owner changes it by hand | Render follows one branch; no secret and no manual step. Git cannot hold both `release` and `release/…`, so the name is `deploy` |
| Q8. Sprint name | `sprint-N`, counted up by the script | Date; a name typed each time | Matches "one per sprint" and needs no input |

## Consequences

- The live site moves only when the owner presses the card; between releases `main` can take any number of merges.
- The first release must exist before the Blueprint is created, because Render needs the `deploy` branch.
- Release refs are protected only by this rule and the script's checks; a hand-made push could still move them.
