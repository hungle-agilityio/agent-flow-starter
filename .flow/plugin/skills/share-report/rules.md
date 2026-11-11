# Rules of share-report

The gate (`share_gate.py`) and the hook (`before-artifact-publish` of the `agent-flow` plugin) read the two settings below. Change a setting by editing its line.

- standing-approval: on
- max-size-mb: 15

## What they mean

- **standing-approval:** the user decided on 2026-10-16 that a verify report may be shared as a private link without asking each time, on two conditions: the masking check of the report is `clean`, and the report shows demo data only. Set it to `off` and Claude asks the user each time instead.
- **max-size-mb:** the report page must stay under this size (an artifact page may not exceed 16 MB, screenshots included).

## The conditions, all required

1. The report folder has `report.json` and `report.html`.
2. `report.json` says `"masking": {"status": "clean"}`. Missing, `not run`, `findings` or anything else means no link.
3. The standing approval above is `on`.
4. The page is smaller than the maximum size.

If one condition fails, nothing is published and only the local file is kept; say which condition failed.
