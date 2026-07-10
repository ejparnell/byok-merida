# Validate existing Notion database schema

The importer writes Job Postings into an existing Configured Notion Database instead of creating or mutating the database schema. The backend validates required property names and types before capture writes, because the Notion database belongs to the user's workspace and automatic schema changes would make the MVP harder to reason about and easier to misconfigure.

The expected MVP schema uses `Job Posting` as the title property. `Company Name`, `Job Title`, and `Location` are rich text properties; `Job URL` and optional `Captured URL` are URL properties; `Application Status` is a select property; `Match Score` is a number property; and `Application Date` is a date property. Job Posting Analysis also requires an `Analyzed` checkbox property so the local backend can count and select unanalyzed To Apply postings without guessing from page content alone.

`Location` is preserved as source display text for MVP. The importer does not derive workplace type, city, state, country, timezone, or region fields until a later filtering workflow proves those fields are needed.

Compensation is preserved inside Job Content for MVP instead of being parsed into dedicated Notion properties. Salary-specific fields should be added later only when a filtering or analysis workflow justifies normalizing ranges, currencies, and pay periods.

Capture writes initialize workflow fields but do not own the later application workflow. `Application Status` defaults to `To Apply`, `Match Score` stays blank until an actual scoring workflow assigns a value, and `Application Date` stays blank until the user updates it in Notion; the backend validates that required options such as `To Apply` already exist instead of creating them automatically.
