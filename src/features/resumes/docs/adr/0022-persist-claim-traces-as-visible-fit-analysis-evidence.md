# Persist claim traces as visible fit analysis evidence

Resume Claim Traces are structured internally during generation and validation, but v1 persists them only as human-readable evidence details in the `Resume Fit Analysis` section. This keeps Notion as the only durable store, avoids hidden local stores or hidden Notion metadata, and lets the generated page be audited without special tooling.
