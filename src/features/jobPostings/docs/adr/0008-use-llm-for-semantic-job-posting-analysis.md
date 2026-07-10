# Use LLM for semantic job posting analysis

Job Posting Analysis uses an LLM as the primary semantic analyzer for three-sentence summaries and grouped Skill Signals, because identifying resume-tailoring signals and grouping near-related requirements needs language understanding beyond deterministic extraction. Deterministic code constrains the result by requiring structured output, validating evidence against Job Content, normalizing group labels, filtering generic trait signals, and failing malformed or unsupported output instead of appending it to Notion.
