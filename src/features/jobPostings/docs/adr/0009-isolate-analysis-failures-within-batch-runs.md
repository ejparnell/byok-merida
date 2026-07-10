# Isolate analysis failures within batch runs

An Analysis Batch Run treats each Job Posting as an independent unit of work and continues after per-posting failures. Failed postings remain `Analyzed` unchecked with a clear failure reason in the UI and console logs, so malformed model output, thin Job Content, or a Notion update failure does not block the rest of the To Apply queue.
