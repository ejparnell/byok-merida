# Superseded: Defer master resume validation until generation

The first Resume creation pass did not require a `Master Resume` record to exist before creating a blank Job-Specific Resume. The Master Resume was important source language for future resume generation, but it was not an operational dependency while creation only proved the relation workflow.

This decision is superseded by ADR-0011 and ADR-0032. `Create Resume` now derives a Job-Specific Resume from the Master Resume, so exactly one `Master Resume` with extractable evidence is required before the Notion adapter creates and attaches a Job-Specific Resume.
