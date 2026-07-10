# Deepen Capture Evidence module

Capture Evidence now has a feature-owned module at `src/features/jobPostings/lib/captureEvidence.js` with one primary interface: `createCaptureEvidence(input)`.

The Chrome extension is a Source Page adapter. It collects per-frame evidence from the rendered page and sends a frame payload with the active tab URL to the Local Operator backend, but it does not merge frames, choose the canonical evidence URL, normalize text, or shape backend diagnostics.

`createCaptureEvidence(input)` accepts both the frame payload and the older merged payload shape. The module owns frame merge, URL selection, field normalization, text length limits, structured metadata extraction, content-source selection, debug summaries, and validation warnings. The Job Posting parser consumes the normalized Capture Evidence object and stays focused on deriving Job Posting fields and Job Content.

This seam improves locality because changes to Capture Evidence shape now land in one module instead of being split across the extension, parser, and route diagnostics. It improves leverage because capture, parse-only review, route logging, and parser tests all exercise the same interface.
