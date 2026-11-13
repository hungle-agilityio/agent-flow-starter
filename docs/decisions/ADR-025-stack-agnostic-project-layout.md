# ADR-025: A new project gets a stack-agnostic layout; the flow lives in .flow/

- Status: Accepted
- Date: 2026-11-11

## Context

The first project made by `.flow/loop/bootstrap.py` (`o-living-with-nature`) had thirteen root entries. They mixed the agent flow (`.flow/loop/`, `plugins/`, `docs/specs/`), the framework's default folders and documents, with no `src/` and Python-only assumptions. The owner asked for product code in `src/`, unused folders gone, what is not pushed ignored, and a layout that works for every stack. Spec `docs/specs/project-layout/`, spec pull request #446, build pull request #453.

## Decision

1. **Layout of a new project** (`bootstrap.py --stack python|node|other`):

   | Where | What |
   |---|---|
   | `src/<feature>/` | the product's code, one folder per feature, tests in `src/<feature>/tests/` |
   | `docs/` | `intent/`, `docs/specs/`, `plans/`, `decisions/`, `templates/`, `architecture.md` |
   | `scripts/` | `check.sh` (the one check command for the loop and CI), `setup.sh` |
   | `.flow/` | `flow.toml`, `loop/` (the loop scripts), `plugin/` (agent-flow, version 1.0.0) |
   | `.claude-plugin/` | `marketplace.json`, plugin source `./.flow/plugin`, id `agent-flow@<slug>` |
   | `.claude/`, `.github/` | settings, rules, knowledge, project instructions; CI, templates |

2. **Paths are config.** `flow.toml` has an optional `[paths]` table (`loop_dir`, `plugin_dir`, `intent_file`, `specs_dir`, `spec_pr_dirs`, `plans_dir`, `decisions_dir`, `templates_dir`, `code_dirs`, `flow_dirs`). A missing key takes this repository's layout, so Agent flow starter does not move and its `.flow/flow.toml` is unchanged.
3. **Config lookup.** `FLOW_CONFIG`, else `<project>/.flow/flow.toml`, else `<project>/.flow/flow.toml`. The hooks, `route_issue.py`, `build_report.py` and the loop scripts all use it, and the loop scripts run from whichever folder holds them.
4. **Without `--stack`** bootstrap writes the old layout, so the first projects and the existing tests are unchanged.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Scope | New projects only; defaults = Agent flow starter | Move Agent flow starter too | Agent flow starter keeps working with no migration |
| Where the flow lives | Hidden `.flow/` | Visible `tools/`; keep `.flow/loop/` and `plugins/` | Flow is setup, like `.claude/` and `.github/` |
| Plugin folder | `.flow/plugin` | `.claude/plugins/` | A task that changes `.claude/` cannot be built by the loop (ADR-023) |
| Tests | Beside the feature; any `tests` folder is protected | One root `tests/` | The owner's tree; the edit guard already matches `tests` at any depth |
| Stacks | `--stack`, one `scripts/check.sh` | Python only | One entry point for the loop and CI on any stack |
| Plugin tests in a new project | Not copied | Copied and run in its CI | They are written for this repository; the plugin is tested here |

## Consequences

- A new project's root reads the same for every stack, and the copy holds no name of this repository.
- Agent flow starter still has `.flow/loop/`, `.flow/plugin` and `docs/specs/`; nothing in its flow changed.
- A plugin text names a project folder by its `paths.*` key, never by a fixed path (a test enforces it).
- New projects start from the template repository `agent-flow-starter`, which is filled from `bootstrap.py --stack` after #453 is merged.
