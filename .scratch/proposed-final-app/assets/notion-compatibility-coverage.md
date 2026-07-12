# Notion Compatibility Coverage

This table maps the compatibility contract to executable acceptance coverage.

| Contract area | Covered behavior | Acceptance seam |
| --- | --- | --- |
| Canonical Application mapping | Legacy `Job Posting`, `Job Title`, `Application Date`, URL, status, score, and relation properties project into canonical records. | Notion CaptureStore mapping tests |
| Capture writes | Canonical drafts write legacy properties, omit unset Match Score, preserve exact Captured URL, and create Capture Summary plus Job Content. | CaptureStore tests and Application Capture workflow test |
| Capture schema | Required legacy types and `To Apply` are validated; optional Captured URL is a warning. | CaptureStore readiness tests |
| Duplicate identity | Canonical Job URL lookup returns one record and rejects ambiguous duplicates. | CaptureStore mapping and shared conformance tests |
| Analysis eligibility | Unreadable Job Content is excluded from eligible-only counts and pages. | ApplicationAnalysisStore queue tests |
| Analysis compatibility | Legacy `Job Posting Analysis` is readable; canonical `Application Analysis` is written with Summary, Match Score, and Skill Signals. | Body codec and ApplicationAnalysisStore tests |
| Analysis repair | Body append and final properties are separate effects in both demo and Notion adapters. | Shared body-first/property-second tests |
| Queue cursors | Merida cursors are context-bound and raw Notion cursors do not escape. | Store pagination tests and public contract tests |
| Resume schema | Database IDs, data-source IDs, inverse relation names, and all three workflow databases are validated. | ResumeCreationStore readiness tests |
| Master Resume | Exactly one active Master Resume is read recursively into canonical document blocks. | ResumeCreationStore body tests |
| Existing artifacts | Only active Job-Specific Resumes count toward idempotency and multiplicity conflicts. | Existing-Resume tests |
| Resume commit | Resume drafts begin unlinked, Notes receive both legacy relations, and final Application attachment occurs last. | ResumeCreationStore effect tests and demo relation-last tests |
| Cleanup | Notes and Resumes archive through narrow operations; PDF removal and reverse cleanup are workflow-owned. | Resume workflow failure tests |
| Demo equivalence | Demo and Notion adapters run the same Capture, Analysis, and Resume store contract assertions. | Shared conformance helpers |
| Provider errors | Raw Notion error payloads and credentials are replaced by typed safe provider errors. | Notion transport privacy test |
| Rich text | Long body values split across legal rich-text segments without truncation. | Body writer limit test |
| Public boundary | API responses remain typed, real workflow routes remain blocked, and generated clients do not change. | Public contract and OpenAPI tests |
