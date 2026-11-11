# ADR-025: A stack-agnostic layout; the flow lives in .flow/

- Status: Accepted

## Context

A project root that mixes the agent flow, the framework's folders and documents makes it unclear what is product code and what is setup, and ties the flow to one stack. This repository uses one small root that reads the same for every stack.

## Decision

1. **Layout.**

   | Where | What |
   |---|---|
   | `src/<feature>/` | the product's code, one folder per feature, tests in `src/<feature>/tests/` |
   | `docs/` | `intent/`, `specs/`, `plans/`, `decisions/`, `templates/`, `architecture.md` |
   | `scripts/` | `check.sh` (the one check command for the loop and CI), `setup.sh` |
   | `.flow/` | `flow.toml`, `loop/` (the loop scripts), `plugin/` (agent-flow) |
   | `.claude-plugin/` | `marketplace.json`, plugin source `./.flow/plugin` |
   | `.claude/`, `.github/` | settings, rules, knowledge, project instructions; CI and templates |

2. **Paths are config.** `.flow/flow.toml` has a `[paths]` table (`loop_dir`, `plugin_dir`, `intent_file`, `specs_dir`, `spec_pr_dirs`, `plans_dir`, `decisions_dir`, `templates_dir`, `code_dirs`, `flow_dirs`). The hooks, `route_issue.py`, `build_report.py` and the loop scripts read it; the plugin texts name a folder by its key.
3. **Spec pull requests** change only `docs/intent/` and `docs/specs/` (`paths.spec_pr_dirs`).
4. **One check command.** `checks.commands` is `bash scripts/check.sh`; CI runs the same script, plus the plugin version check.
5. **A feature task never changes `.flow/`.** Flow work is an `area:flow` issue that lists the flow files it changes (ADR-023).

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Where the flow lives | Hidden `.flow/` | Visible `ops/` and `plugins/` | The flow is setup, like `.claude/` and `.github/`; the root shows the product |
| Plugin folder | `.flow/plugin` | `.claude/plugins/` | A task that changes `.claude/` cannot be built by the loop (ADR-023) |
| Tests | Beside the feature; any `tests` folder is protected | One root `tests/` | Code and its tests move together |
| Stacks | One `scripts/check.sh` per stack | Python-only checks | One entry point for the loop and CI |

## Consequences

- The root reads the same for every stack; `.gitignore` holds a common part and the stack's part.
- The plugin's own tests are not part of this repository; its version check is.
