---
description: Final verification: one report with PASS / FAIL / NOT CONFIGURED per axis, opened for you
argument-hint: <issue number or file>
---

Verify the work for: $ARGUMENTS

Use the `build-verify-report` skill. In short:

1. Write the criteria file: check each "Done when" or acceptance criterion of the issue in the running app (use the `check-in-browser` skill) or with a test, and record `PASS`, `FAIL` or `NOT CONFIGURED` with the evidence; add the issue's "Steps to check the result" as the steps the user can try.
2. If the review step ran, save its summary with `Status: PASS` or `Status: FAIL` on the first line.
3. Run the report builder. It runs every axis, writes the report and opens it. Pick the screens mode from the issue:
   - **No UI** (no `needs-ui` label, nothing users see): `--no-ui`. No browser, the Browser axis reads `NOT APPLICABLE`, no screenshots.
   - **UI** (`needs-ui`): copy the issue's `## Screens to capture` block unchanged into a file and pass `--browser --spec <file>`. The report shows each step's full page next to its close-up. There are no default pages: `--browser` without `--spec` fails the Browser axis.

| Axis | How |
|---|---|
| Lint | `uv run ruff check .` |
| Types | `uv run mypy .` |
| Tests | `uv run pytest -q` |
| Coverage | 90% on services and repositories |
| Skill and hook tests | `uv run pytest .flow/plugin/hooks/tests .claude/skills` |
| Issue | each criterion of the issue, from the criteria file |
| Query count | asserted for list and dashboard pages |
| Security | no secret-like string in the diff (`.claude/rules/security.md`) |
| Browser | the `check-in-browser` skill on the issue's "Screens to capture": full page and close-up per step, console and network clean; `NOT APPLICABLE` with `--no-ui` |

If an axis cannot be checked, the report says `NOT CONFIGURED` and why; never write PASS without evidence.

4. Run the `share-report` skill: it prints the private link of the report, or says in one line why there is no link (the masking check must be clean).

**Then stop at Gate 2.** Tell me the verdict and where the report is (it is already open), and ask me to check the result myself (the steps are in the report). Do not commit or run `/learn` until I say OK.
