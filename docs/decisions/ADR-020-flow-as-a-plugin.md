# ADR-020: The flow is a Claude Code plugin, agent-flow

- Status: Accepted
- Superseded in part by ADR-023 (the loop edits the files its issue lists)

## Context

The flow's hooks, skills, slash commands and sub-agents must exist once, be generic, and run the same in interactive sessions and in loop builds. A pull request branch must not be able to run a weaker copy of its own guards.

## Decision

1. **One plugin in this repository.** `.flow/plugin/` holds the guard hooks (`hooks/hooks.json`), the flow skills, the commands and the sub-agents. This repository is its own marketplace: `.claude-plugin/marketplace.json` lists it with source `./.flow/plugin`, and `.claude/settings.json` turns on `agent-flow@<slug>` (`extraKnownMarketplaces`, `enabledPlugins`).
2. **Generic.** The hooks read the project through `$CLAUDE_PROJECT_DIR`: `.flow/flow.toml` and its reader `.flow/loop/flow_config.py`; the allowed repository is `project.repo`. The skills, commands and sub-agents name no project; they point to `.claude/rules/`, `.claude/knowledge/` and the folders of `[paths]` in `.flow/flow.toml`.
3. **Names.** Skills resolve as `agent-flow:<skill>`, commands as `/agent-flow:<command>`, sub-agents as `agent-flow:<agent>`.
4. **The installed plugin runs, never the branch's copy.** The plugin is installed from this repository's marketplace at project scope; a build on a pull request branch runs the installed plugin from `main`. A second copy at user scope stays disabled (the build worktrees use it).
5. **Skill scripts without a prompt.** The hook `before-skill-script-allow` answers `allow` for exactly one plain `python3 [-I]` or `uv run python` call of a `.py` file at `skills/<skill>/` of the plugin, after resolving its real path. No permission rule names the plugin's cache path: a `*` for the version also matches `..`.
6. **Versions.** The installed plugin changes only when its version does, so every change under `.flow/plugin/` raises the version in `.flow/plugin/.claude-plugin/plugin.json`; CI checks it (`.flow/loop/check_plugin_version.py`). The tick runs `claude plugin marketplace update` and `claude plugin update` once per tick.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Where the plugin lives | In this repository, `.flow/plugin/`, its own marketplace | A shared plugin repository | The project depends on no other repository |
| What goes in | Hooks, flow skills, commands, sub-agents | Hooks only | One package, one version |
| New versions on the Mac mini | Marketplace install; the tick updates each tick | Load from the working tree | Same route for the loop and interactive sessions |
| Skill scripts in `claude -p` | A plugin hook allows only the plugin's own skill scripts | An allow rule with `*` or an exact version | `*` escapes with `..`; an exact version breaks at each update |
