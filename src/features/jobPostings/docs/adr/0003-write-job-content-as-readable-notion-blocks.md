# Write job content as readable Notion blocks

The importer writes Job Content into the Notion page body as simple structured blocks instead of one plain-text dump. Each captured page includes a capture summary with source information, followed by cleaned headings, paragraphs, and bullet lists from the posting, because the Notion record should be readable and scannable after capture without manual cleanup.

Raw Capture Evidence such as full HTML or DOM dumps is not stored in Notion by default. The durable Notion record keeps parsed fields, source URLs, capture timing, cleaned Job Content, and optional parsing notes, while raw evidence can remain a local development/debugging concern.

Long Job Content is split into Notion blocks while preserving paragraph and list boundaries where possible, and blocks may be appended in batches to stay within API limits. If content must be truncated after a project-defined cap, the Notion page is still created with an explicit parsing note so content loss is visible.

Job Content preserves source section headings where possible. The importer may lightly infer headings for clearly separated unlabeled content, but it does not aggressively rewrite the posting into canonical sections during capture.
