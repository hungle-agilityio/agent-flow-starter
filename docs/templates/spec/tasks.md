# Tasks: <feature>

<!-- Copy to docs/specs/<feature>/tasks.md. One task becomes one issue. Tasks meant to run in parallel never share a file. Keep each task under about 400 lines of diff.
     Every issue body gets a `## Files likely touched` section with one backticked path per bullet line, for example:
       ## Files likely touched
       - `src/services.py`
       - `tests/unit/test_<name>.py` (NEW)
     The tick reads it: an issue waits while a running or in-review issue lists the same file, and an issue with no paths runs alone (ADR-015).
     In an epic, a task that changes a number or behaviour set by an earlier task names it in its ACs; it may change that task's tests, and the epic pull request lists them (ADR-022).
     A task with needs-ui: yes also gets a `## Screens to capture` section in its issue body: one fenced `json` block, a check-in-browser spec in which every step has `goto` and `capture`, for example:
       ## Screens to capture
       ```json
       {"steps": [{"name": "reviews-filters", "goto": "/src/", "capture": "#filter-rating"}]}
       ```
     The build copies the block unchanged into `build_report.py --browser --spec`. A needs-ui issue without a valid block, or with "steps": [], opens no pull request (agent:failed). A task with needs-ui: no has no section and its report runs with --no-ui. -->

<!-- Epic only: keep a query budget so later tasks list the query-cap tests earlier tasks add (ADR-024). -->

## Query budget

| Page | Queries on main | After T1 | After T2 |
|---|---|---|---|
| <url> | <n> | <n> | <n> |

## T1: <short title>

- **ACs:** AC1, AC2
- **Files likely touched:** `src/services.py`, `tests/unit/test_<name>.py`
- **Depends on:** none
- **Risk:** low | medium | high
- **needs-ui:** yes | no
- **Screens to capture:** (needs-ui only) each page and the selector of the part that changes, for example `/src/` → `#filter-rating`
- **Label:** `agent:ready` (every task; list every file it will change, guarded ones included, ADR-023). A task that changes a file under `.claude/`: no `agent:*` label, built by hand (ADR-023, "Exception: .claude/")

## T2: <short title>

- **ACs:** AC3
- **Files likely touched:** <paths>
- **Depends on:** T1
- **Risk:** low | medium | high
- **needs-ui:** yes | no
- **Screens to capture:** (needs-ui only) <page> → <selector>
- **Label:** `agent:ready`
