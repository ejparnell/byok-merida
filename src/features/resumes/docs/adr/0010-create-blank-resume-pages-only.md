# Superseded: Create blank resume pages only

The first Resume creation workflow created a blank Job-Specific Resume by setting only `Name` and the `Job Posting` relation. It did not add placeholder blocks, copy Job Posting Analysis, or write a "created from" note, because that pass only proved the Resume database relation and queue workflow.

This decision is superseded by ADR-0011 and ADR-0032. `Create Resume` now creates an application-ready Job-Specific Resume from Master Resume evidence and Job Posting analysis. The Notion adapter creates an unlinked draft, writes the generated body, and only then attaches the `Job Posting` relation so a failed generation does not remove the Job Posting from the Resume Creation Queue.
