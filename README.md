# Agent flow starter

A template for a new project that is built with the agent flow: you send requests to a Claude Project, it writes the spec and the issues, and a loop on the Mac mini builds each issue into a pull request that you review and merge. Everything the flow needs is in this repository; a project made from it depends on no other repository.

## What is inside

```
CLAUDE.md  README.md  .env.example  .gitignore
.claude/           settings.json, rules/, knowledge/, project-instructions.md
.claude-plugin/    marketplace.json (the plugin agent-flow, from ./.flow/plugin)
.flow/             flow.toml, loop/ (the loop scripts and setup), plugin/ (hooks, skills, agents)
.github/           workflows/checks.yml, PULL_REQUEST_TEMPLATE.md, ISSUE_TEMPLATE/
docs/              intent/, specs/, plans/, decisions/, templates/, architecture.md
src/               the product's code, one folder per feature, tests beside it
scripts/           check.sh (one command checks everything), setup.sh, setup-project.sh
```

- **Product code** goes in `src/<feature>/`, its tests in `src/<feature>/tests/`.
- **Documents** go in `docs/`: an idea in `intent/`, a spec in `specs/<feature>/`, approved plans in `plans/`, decisions in `decisions/`.
- **The flow** is all in `.flow/`. A feature task never changes it.
- **`bash scripts/check.sh`** runs lint, types and tests; the loop and CI both run it.

## Start a project

1. On GitHub, click **Use this template** and create the new repository (private).
2. On the Mac mini, clone it and run, at its root:

   ```
   bash scripts/setup-project.sh --repo <owner/name> --owner <login> --name "<display name>" \
       --slug <slug> --ntfy-topic <topic> --stack python|node|other --dry-run
   ```

   Read what it would change, then run it again without `--dry-run`. It renames the template values, writes the stack's `scripts/check.sh`, `scripts/setup.sh`, `.gitignore`, CI and `.flow/flow.toml`, writes `~/.<slug>/agent.env`, creates the GitHub labels, and prints the steps only you can do (token, Claude GitHub App, ruleset, ntfy, plugin install, loop). It runs once; a second run stops.
3. Follow the printed steps. The Notion page "Những gì cần cho một dự án mới" walks through the whole kickoff.

The template's own values (`agent-flow-starter`, `Agent flow starter`, slug `starter`, topic `CHANGE-ME`) are only placeholders for the setup script.
