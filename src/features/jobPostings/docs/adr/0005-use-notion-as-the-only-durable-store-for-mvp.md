# Use Notion as the only durable store for MVP

The MVP treats the Configured Notion Database as the only durable store for captured Job Postings. The local backend may emit logs for debugging, but it does not maintain a local database or retry queue, because adding local persistence would introduce migrations, sync rules, and source-of-truth questions before the capture workflow needs them.
