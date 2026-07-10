# Add Job Posting Analysis Store

Job Posting Analysis now uses a feature-owned storage module at `src/features/jobPostings/lib/analysisStore.js`.

The module exposes one small semantic interface for the Analysis Batch Run:

- read analysis readiness from the configured Notion database
- find Analysis Queue items
- load a Job Posting for analysis
- save Analysis Findings

The store owns the Notion-specific implementation details behind that interface: validating the database schema, counting and listing the Analysis Queue, reading page children, detecting an existing `Job Posting Analysis` section, extracting `Job Content`, appending Analysis Findings, marking the `Analyzed` checkbox, and repairing the checkbox when durable findings already exist.

This preserves ADR-0007 by keeping append-before-marking inside the storage module instead of spreading that ordering across analysis orchestration tests. The Analysis Batch Run stays focused on batch progress, isolated per-posting failures, and LLM analysis, while tests can exercise storage behavior through the same semantic interface used in production.
