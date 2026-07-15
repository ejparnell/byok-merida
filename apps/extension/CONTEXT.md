# Extension Capture

Extension Capture is Merida's Chrome side-panel context for review-first Application capture. It reads a Source Page only when the user intentionally starts a capture and keeps the resulting Review separate from later browsing.

## Language

**Source Page**:
The HTTP(S) webpage from which Extension Capture reads Capture Evidence, identified by its tab and URL.
_Avoid_: Current page, job tab

**Persistent Web Access**:
The install-time browser authorization that lets Extension Capture read HTTP(S) Source Pages after navigation without requiring the side panel to be reopened. It does not make Chrome-internal or other non-web pages readable.
_Avoid_: Active-tab access, backend access

**Source Availability**:
The recoverable state of whether the active page is readable as a Source Page. It is separate from backend readiness and does not replace an existing Review.
_Avoid_: Backend blocked, capture failure

**Source Readiness**:
The state of whether the active Source Page has completed its current navigation sufficiently for Capture Evidence to be read. It may delay a user-initiated capture but does not change a Review.
_Avoid_: Backend loading, parser delay

**Source Access**:
The Extension Capture boundary that determines Source Availability and Source Readiness for the active page. It does not own Capture Evidence, a Review, or backend readiness.
_Avoid_: Capture session, backend health

**Source Mismatch**:
The current condition where the active page differs from the Source Page of an existing Review. It ends when the original tab and URL are active again.
_Avoid_: Source history, permanent stale review

**Pending Capture**:
A user-initiated request to read one Source Page that is waiting for that page to become ready. It is cancelled when that Source Page changes rather than being retargeted automatically.
_Avoid_: Background capture, follow-navigation capture

**Review**:
The editable, in-memory Application draft derived from one Source Page before it is written to Notion.
_Avoid_: Application, saved record

**Capture Match**:
The pre-save finding that a non-archived Notion Application has an equivalent Company Name and Role to the current Review, including recognized formatting and abbreviation variants. It informs whether to create a new Application but does not itself change a record.
_Avoid_: Application Status, applied, duplicate
