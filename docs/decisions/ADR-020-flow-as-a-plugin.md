# ADR-020: The flow is a Claude Code plugin, agent-flow

- Status: Accepted
- Superseded in part by ADR-023 (no agent:manual)
- Date: 2026-11-05

## Context

The flow's hooks, skills, slash commands and sub-agents lived in Agent flow starter's `.claude/`. A new project got a copy of them through bootstrap (ADR-019), so every fix had to be made in each copy. A loop build on a pull request branch also ran that branch's own copy of the hooks, so a branch could weaken its own guards. Spec `docs/specs/flow-plugin/spec.md`; epic #220, issues #221 (skeleton and probe), #222 (hooks), #223 (skills, commands, sub-agents, this record), #224 (tick update) and #225 (bootstrap).

## Decision

1. **One plugin in this repository.** `.flow/plugin/` holds the 6 guard hooks (`hooks/hooks.json`), the 10 flow skills, the 8 commands and the 5 sub-agents, with their tests. The marketplace `starter` (`.claude-plugin/marketplace.json` at the git root) lists it. Agent flow starter turns it on in `.claude/settings.json` (`extraKnownMarketplaces`, `enabledPlugins`). Its own copies are removed; git history is the archive.
2. **Generic.** The hooks read the project through `$CLAUDE_PROJECT_DIR` (`.flow/flow.toml`, `.flow/loop/flow_config.py`; the allowed repository is `project.repo`). The skills, commands and sub-agents name no project and point to the project's `.claude/rules/`, `.claude/knowledge/` and `.flow/flow.toml`. A test greps the plugin for project names. The app skills (`write-tests`, `diagnose-bug`, `check-in-browser`, `capture-before-after`) stay in the project.
3. **Names.** Skills resolve as `agent-flow:<skill>`, commands as `/agent-flow:<command>`, sub-agents as `agent-flow:<agent>`.
4. **The loop may not edit the plugin.** `before-edit-check` refuses `plugins/` and `.claude-plugin/` at the git root in loop mode; plugin tasks are `agent:manual`. A pull request branch runs the installed plugin from `main`, never its own copy.
5. **Skill scripts without a prompt.** The probe of #221 showed that the plugin's path holds its version and that a permission rule with `*` for the version also matches `..`, so it can run a script outside the plugin. No rule names the plugin's scripts. The plugin's hook `before-skill-script-allow` answers `allow` for exactly one plain `python3 [-I]` or `uv run python` call of a `.py` file at `skills/<skill>/` of the plugin, after resolving its real path; anything else is left to the permission rules (owner's choice A, 2026-11-05).
6. **Versions.** The installed plugin changes only when its version does, so every change raises the version in `plugin.json`. The tick runs `claude plugin marketplace update` and `claude plugin update` once per tick (#224).
7. **The coverage gate is a project setting.** The report reads it from `FLOW_COVERAGE_INCLUDE` and `FLOW_COVERAGE_FAIL_UNDER` in the project's `.claude/settings.json` `env`; `.flow/flow.toml` has no key for it yet.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 Where the plugin lives | This repo: `.flow/plugin/` + root marketplace | New repo `agent-flow` | Only this repo may be touched; one place to review |
| Q2 What goes in | Hooks, 10 flow skills, 8 commands, 5 sub-agents, made generic | Hooks and skills only | One package; bootstrap copies less |
| Q3 New versions on the Mac mini | Marketplace install; tick runs `plugin update` each tick | `--plugin-dir` from main; update by hand | Same route for loop and interactive sessions, works for every project |
| Q4 Who edits the plugin | `agent:manual`; hook blocks the loop | Loop may edit | The loop must not change its own guards |
| Q5 Agent flow starter | Moves to the plugin now; repo copies removed | Two copies side by side | One copy to keep in step |
| Spec: names | Plugin `agent-flow`, marketplace `starter` | `starter-flow` | Generic name, matches the repo |
| Spec: probe first | T1 probes `claude -p`, cache path and allow rules on the Mac mini | Build straight away | Cloud probe could not run a signed-in `claude -p` |
| Skill scripts in `claude -p` (#223) | A plugin hook allows only the plugin's own skill scripts, after resolving the real path | An allow rule with the exact version; `ask` (refused in `claude -p`) | A `*` rule escapes with `..`; an exact rule breaks at each update; `ask` would stop the loop's verify report |
