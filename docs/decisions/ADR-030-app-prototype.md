# ADR-030: One clickable prototype of the whole app is the design; the work is split only after "Prototype ổn"

- Status: Accepted
- Date: 2026-11-12

## Context

On 2026-11-12 the owner asked whether the flow lacked a design and prototype step. It had one design card per feature: a static Artifact linked from `docs/specs/<feature>/design.md`, showing a few states of one screen. Nothing compared the built screens with it (`design/README.md` and the work-queue skill wrongly said `capture-before-after` did). The owner then asked to design and prototype the whole app before splitting it into epics and tasks, with real actions and animations, built as an Artifact. While the first prototype was built from the screens on `main`, it showed that the dashboard is wider than a phone screen (the grid's children kept their minimum content width).

Spec `docs/specs/app-prototype/spec.md` (pull request #500); #503 (Design vs build in the verify report), #509 (spec templates name prototype states), #510 (dashboard on a phone); #511 is this record and the Project rules.

## Decision

1. **One prototype of the whole app.** `docs/design/prototype.html` is one self-contained file, published as one private Artifact whose link stays the same when it is republished. It shows every screen and state as an id of its `SCENARIOS` list (`#<id>`; `?bare` hides the prototype bar), on the demo data of `seed_demo_data`, with real actions and animations (sign-in, filters, forms with validation, modals, toasts, loading) and no backend. It is the source of truth for what users see.
2. **The design card is retired.** `design/<feature>/` folders stay in git history; new work does not make one.
3. **Prototype first, then the split.** When users will see a change, in either lane, a thread updates the prototype after Grill-me and before any spec file: new screens and states as new ids. It republishes the Artifact and posts a card "Prototype ổn (đề xuất) / Sửa". Epics and tasks are split only after "Prototype ổn".
4. **Gate 1 stays.** Full lane: the spec pull request carries the prototype change, and "Merge PR spec" is Gate 1. Fast lane: "Prototype ổn" is also the OK of Gate 1; the thread opens a pull request `design: <feature>` that changes only `docs/design/prototype.html` and merges it on that same press.
5. **Issues name states.** Every `needs-ui` issue names, in each step of `## Screens to capture`, the prototype state it should match with `"design": "<state id>"`.
6. **Design vs build in the report.** The verify report shows the prototype state next to the built screen, at the same window size (#503). There is no pixel diff and nothing fails because of it; a missing state, prototype or browser is a note. The owner judges.

## Decisions

| Question | Chosen | Rejected | Why |
|---|---|---|---|
| Q1 Form of the prototype | One HTML file `docs/design/prototype.html`, published as a private Artifact | Artifact only | Versioned with the spec, and the loop can open it |
| Q2 Prototype or design card | The prototype replaces the design card | Keep both | One thing to review |
| Q3 What it covers | The whole app, every screen and state; every needs-ui request updates it first, fast lane too | One prototype per epic | One source of truth for the UI |
| Q4 Where the owner approves | A card "Prototype ổn / Sửa" before the split into epics and tasks; "Merge PR spec" stays Gate 1 | Only at "Merge PR spec" | The owner tries the flow before the work is split |
| Q5 Compare design and build | Side by side in the verify report, no automatic failure | Pixel diff that fails the build; no compare | Demo CSS and app CSS differ in small ways; the owner judges |
| Q6 First version | Built from the screens on `main`, merged in the spec pull request #500 | Rules only | A real source of truth from day one |
| Fast lane with a visible change | "Prototype ổn" is the Gate 1 OK; a `design:` pull request with only the prototype, merged on that press | Send every visible change to the full lane | Keeps small UI work light |

## Consequences

- The prototype's CSS is a copy of the app's CSS (with `@media` rules rewritten as container queries); a CSS change in the app is made in the prototype too, or Design vs build shows the difference.
- The prototype grows with the app; one file keeps it simple to publish but makes it large.
- New projects made from the `agent-flow-starter` template do not have the Prototype step yet; that is a follow-up.
