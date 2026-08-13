# Issue tracker: Local Markdown

Issues, Wayfinder tickets, and specifications for this repo live as Markdown files under the three root categories in `.scratch/`.

## Layout

- Specifications: `.scratch/specs/<spec-slug>.md`
- Implementation issues: `.scratch/issues/<feature-slug>/<NN>-<issue-slug>.md`
- To Tickets bundles: `.scratch/tickets/<effort-slug>/tickets.md`
- Wayfinder maps: `.scratch/tickets/<effort-slug>/map.md`
- Wayfinder child tickets: `.scratch/tickets/<effort-slug>/<NN>-<ticket-slug>.md`

Use lowercase kebab-case slugs. Number issues and child tickets from `01` within their feature or effort. The first Markdown heading is the artifact's canonical human-readable name; references should link that name rather than present a bare number or slug.

## Metadata

- `Status:` records one of the five triage roles in `triage-labels.md`; it is not a lifecycle field.
- `State: open|closed` records issue or Wayfinder lifecycle when needed.
- `Assignee: unassigned|<driver>` records a Wayfinder claim.
- Comments and conversation history append under a `## Comments` heading.
- A specification produced by `/to-spec` has `Status: ready-for-agent` near the top.

## When a skill says "publish to the issue tracker"

- Publish a specification to `.scratch/specs/<spec-slug>.md`.
- Publish an implementation issue to `.scratch/issues/<feature-slug>/<NN>-<issue-slug>.md`.
- Publish a `/to-tickets` bundle to `.scratch/tickets/<effort-slug>/tickets.md`.
- Publish Wayfinder artifacts under `.scratch/tickets/<effort-slug>/`.

Create missing directories when needed.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. If the user provides only a ticket name or number, search the appropriate feature or effort directory and confirm that the match is unique.

## Wayfinding operations

Used by `/wayfinder`. A map is an index with one sibling file per child ticket.

- **Map**: `.scratch/tickets/<effort-slug>/map.md`, with `Labels: wayfinder:map` and `State: open` near the top.
- **Child ticket**: `.scratch/tickets/<effort-slug>/<NN>-<ticket-slug>.md`, with `Parent`, `Type`, `Status`, `State`, `Assignee`, and `Blocked by` metadata. `Type` is `research`, `prototype`, `grilling`, or `task`; AFK tickets begin `ready-for-agent`, while HITL tickets begin `ready-for-human`.
- **Blocking**: `Blocked by:` contains `none` or linked canonical ticket names. A ticket is unblocked when every linked blocker has `State: closed`.
- **Frontier**: scan the effort directory for child tickets with `State: open`, no unresolved blockers, and `Assignee: unassigned`; lowest number wins.
- **Claim**: set `Assignee:` to the driver and save before doing work.
- **Resolve**: append the answer under `## Answer`, set `State: closed`, and append only a linked one-line gist to the map's `## Decisions so far` section.
- **Rule out of scope**: set `State: closed` and `Status: wontfix`, then link the ticket only from the map's `## Out of scope` section.
