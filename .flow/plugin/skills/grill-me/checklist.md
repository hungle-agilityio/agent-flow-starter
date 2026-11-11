# Decision checklist

The rulebook of `grill-me`: kinds of decisions to look for. Edit this file to change what gets asked; the skill does not need to change.

For each kind, first look in the project for an existing answer. Ask only when there is none.

| Kind | Typical decisions | Where the answer may already be |
|---|---|---|
| Definitions | What does "good", "bad", "week", "location" mean? | `rules/domain.md`, `knowledge/BUSINESS_RULES.md` |
| Numbers | Rounding, decimals, what counts in the denominator, empty means no score or zero | `KNOWN_PITFALLS.md` (rounding) |
| Dates and time | Time zone, week start, inclusive or exclusive ends | `rules/domain.md` |
| Lists | Order and tie-break, page size, invalid page number, filters combined with AND or OR | `KNOWN_PITFALLS.md` (pagination) |
| Empty and error cases | What the screen or output shows when there is nothing, or the input is wrong | the issue's acceptance criteria |
| Scope | In, out, later; one issue or split | the issue or epic |
| Layers | Which layer holds the rule (service), which query (repository) | `rules/architecture.md` |
| Data | Migration, existing rows, demo data | `knowledge/` |
| Security | Personal data, secrets, who may see or send what, what leaves the machine | `rules/security.md` |
| Proof | How it will be shown to work: tests, query count, browser check, screenshots | `commands/verify.md` |
| Names and words | Skill, helper, file and label names | `rules/naming.md` |
| Order and cost | Which comes first, what depends on what, optional or required | the epic |
