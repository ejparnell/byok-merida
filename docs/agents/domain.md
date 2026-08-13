# Domain Docs

How the engineering skills should consume this repo's domain and implementation documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT-MAP.md` at the repo root for feature ownership, shared contracts, and links to context-specific `CONTEXT.md` files.
- Each context-specific `CONTEXT.md` relevant to the work.
- `docs/README.md` and the linked implementation guides relevant to the area being changed.
- Relevant ADRs under a context's `docs/adr/` directory, such as `apps/extension/docs/adr/`.
- `docs/adr/` for system-wide decisions if that directory is added later.

If one of these files or directories does not exist, proceed silently. Domain-modeling skills create missing context or decision documents when terms and decisions are actually resolved.

## Layout

This is a multi-context repository:

    /
    ├── CONTEXT-MAP.md
    ├── docs/
    │   ├── README.md
    │   ├── architecture.md
    │   ├── codebase-structure.md
    │   └── ...
    └── apps/
        └── extension/
            ├── CONTEXT.md
            └── docs/adr/

Follow `CONTEXT-MAP.md` rather than assuming every feature has a separate `CONTEXT.md`.

## Use the glossary's vocabulary

When output names a domain concept—in an issue title, refactor proposal, hypothesis, or test name—use the term defined by the relevant context documentation. Do not drift to synonyms the glossary explicitly avoids.

If a needed concept is not documented, reconsider whether the term belongs to the project or note the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly rather than silently overriding the decision.
