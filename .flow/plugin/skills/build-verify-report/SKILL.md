---
name: build-verify-report
description: Run every verify axis (lint, types, tests, coverage, the issue's criteria, query counts, security, browser) and write one report page with the real numbers and screenshots, then open it. Use for /verify, or when the user asks for the verification report of a change.
---

# Build the verify report

One command runs every axis, reads the numbers from the real output (nothing is retyped), writes a single page and opens it, so the user only has to look. The report is written also when something fails.

## Run it

```
uv run python <this skill's folder>/build_report.py --title "<issue title>" \
  --criteria <criteria file> [--review <review file>] (--browser --spec <file> | --no-ui) [--design <file>] [--no-open]
```

`<this skill's folder>` is the base directory Claude Code gives when this skill loads: an absolute path in the installed plugin. Run the script from there as one plain command, with no pipe, redirection or `2>&1`, and never from `.flow/plugin/` in the repository: only that plain call runs without a prompt, so any other form stops a loop build.

Input files: write the criteria file to `out/verify-input/criteria.json` and the screens file to `out/verify-input/spec.json` with the Write tool, and run `build_report.py` with those relative paths as one plain command.

- **A task that changes a screen:** `--browser --spec <file>`, where the file is the issue's `## Screens to capture` block copied unchanged. It runs the `check-in-browser` skill on those steps only, and the report shows each step's full page next to its close-up (`<name> (close-up)`) when the step gives `capture`. There are no default pages any more: `--browser` without `--spec` makes the Browser axis `FAIL` with `no screens given: pass --spec from the issue's "Screens to capture"`. A step whose `capture` matched nothing visible makes the Browser axis `FAIL` and names the step. In the report a click on a screenshot opens it full size; click again or press Escape to close it.
- **Design vs build:** for each step of the spec that names a state of the app prototype in `"design"`, the report shows, after the screenshots, the prototype's picture of that state (`Design: <state id>`) next to the built screen (`Build: <step name>`), taken at the same window size; a state the prototype does not have reads `Design not found: <id>`, and nothing fails because of this section. `--design <file>` sets the prototype file; without it the file is `docs/design/prototype.html` under the project's folder.
- **A task that changes no screen:** `--no-ui`. No browser runs, the Browser axis reads `NOT APPLICABLE` (`the task changes no screen`) and the report has no screenshots. `NOT APPLICABLE` does not make the verdict `INCOMPLETE`. The masking status is then `clean` when no report text holds personal data, so the report can still be shared.
- `--browser` and `--no-ui` together are refused (exit code 2). With neither, the Browser axis is `NOT CONFIGURED`.
- The report is `out/verify/<time>/report.html` (one self-contained page, git-ignored) and `report.json`. It opens by itself unless `--no-open` is given.
- It takes about half a minute: it runs the same checks as the automatic checks on GitHub.

## The criteria file (you write it)

The program cannot judge an issue's own criteria; you check each one (in the running app or with a test) and record the result:

```
{"criteria": [
   {"text": "<a Done when or acceptance criterion>", "status": "PASS", "evidence": "<what you saw or ran>"}
 ],
 "check_yourself": ["<a step the user can try in the app>", "<another step>"]}
```

`status` is `PASS`, `FAIL` or `NOT CONFIGURED` (when it cannot be checked, say why in `evidence`). `check_yourself` comes from the issue's "Steps to check the result" or "How to check it when built".

### The test matrix (optional)

When the issue has a "Test matrix rows" table, add a top-level list `"matrix"` next to `"criteria"` and `"check_yourself"`, one entry per row of that table:

```
 "matrix": [
   {"row": "M1", "ac": "AC1", "test": "<path>::<test_name>", "status": "PASS", "evidence": "<what you ran>"}
 ]
```

`"row"` and `"ac"` come from the issue's table. `"test"` is the `path::test_name` that checks the row, or the person's steps for a manual row. `"status"` is one of three:

- `PASS`: the named test ran and passed;
- `FAIL`: no test checks the row, or its test fails;
- `MANUAL`: a person checks the row by the steps in `"test"`.

The report gets an axis `Test matrix` right after `Issue`, and a table with one line per entry (Row, AC, Test, Status, Evidence) right after the axis table:

| The criteria file has | Axis | Evidence |
|---|---|---|
| no `"matrix"` key (or there is no criteria file) | `NOT APPLICABLE` | `the issue has no test matrix rows` |
| an entry with `FAIL`, with a status other than the three, or with `PASS` and a missing or blank `"test"` | `FAIL` | `<f> of <n> rows fail: M2, M5` (an entry with no `"row"` is named `?`) |
| `"matrix": []`, or a value that is not a list | `FAIL` | `the matrix list is empty` |
| only `PASS` and `MANUAL` entries | `PASS` | `<p> of <n> rows pass, <m> manual` |

A `FAIL` on this axis makes the verdict `FAIL`; `NOT APPLICABLE` leaves the verdict as it was. Leave the key out when the issue has no matrix: never write an empty list.

## The review file (optional)

When the review step ran, save its summary as a text file whose **first line** is `Status: PASS` or `Status: FAIL`; it is shown in the report.

## Read the result

| Exit code | Verdict | Meaning |
|---|---|---|
| 0 | PASS | every axis passed |
| 1 | FAIL | at least one axis failed: show which, with its evidence |
| 2 | INCOMPLETE | no axis failed, but some are NOT CONFIGURED (for example no criteria, or no browser): say which and why |

Give the user the verdict, the path of the report and the failed axes, then stop at Gate 2. Never write PASS for an axis the report does not show as PASS.

## Masking

The report carries a `masking` status (`clean`, `findings` or `not run`) in `report.json`: clean only when the browser run was clean (or `--no-ui` was given) and no text of the report (title, criteria, review) holds personal data. Findings make the Browser axis FAIL and block sharing. `--plant "<text>"` is for testing the scan only.

## Rules

- The screenshots show demo data only. Do not publish or share the report here: sharing is a separate step with its own checks.
- Do not edit the report by hand; rerun the program.
