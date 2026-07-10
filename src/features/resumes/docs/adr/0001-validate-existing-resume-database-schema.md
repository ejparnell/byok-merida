# Validate existing resume database schema

The Resumes feature writes to a user-created Notion database instead of creating or mutating the database schema. The local backend validates that the configured Resume database has a `Name` title property and a `Job Posting` relation to the configured Job Posting database, with the inverse relation named `Resumes` on the Job Posting side, before creating a blank job-specific Resume.
