---
name: draft-pull-request
description: Draft a pull request from the evidence (verify report, before and after images, issue number) and say whether it is complete. Writes the description and a local folder of masked images to drag in. Use before create-pull-request, or when the user asks for a pull request draft.
---

# Draft a pull request

The draft is built from real evidence, not from memory. Nothing is created on GitHub here; `create-pull-request` does that after the user approves the preview.

## Run it

```
uv run python <this skill's folder>/draft_pr.py --title "[FEAT] ..." --what "..." --why "..." \
  [--issue N] --report out/verify/<folder> (--compare out/before-after/<folder> | --no-visual) [--out DIR]
```

`<this skill's folder>` is the base directory Claude Code gives when this skill loads: an absolute path in the installed plugin. Run the script from there as one plain command, with no pipe, redirection or `2>&1`, and never from `.flow/plugin/` in the repository: only that plain call runs without a prompt, so any other form stops a loop build.

Output (default `out/pr-draft/<branch>/`, git-ignored): `pr-body.md`, `images/` and `draft.json`.

## What it checks

| Check | Result when it fails |
|---|---|
| Title starts with `[BUG]`, `[FEAT]`, `[TASK]` or `[EPIC]` | incomplete |
| What and Why are not empty | incomplete |
| A verify report is given, and its verdict is PASS | incomplete (a FAIL is still written honestly in the body) |
| Before and after images are given and their masking is `clean`, or `--no-visual` | incomplete; unmasked images are never copied |
| An issue number | complete but `ready_to_create: false`; the body says "no issue number yet" and has no `Closes` line |

## Rules

- Only pages labelled `changed` or `did not exist before` are copied to `images/`; "no visible difference" is left out.
- The report link is the private artifact link when the report was shared. In loop mode it must be the artifact link: run `share-report` first, and with no link the loop opens no pull request (`work-queue` step 8; the hook refuses a loop body without it). "Not shared" with the local path stays allowed only in an interactive session.
- Never invent an issue number. Create the issue first (`create-issue`), then run the draft again with `--issue`.
- Images are dragged into the pull request by the user from `images/`; the description names the files.
