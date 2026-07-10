# Validate resume page status before writes

The `/resumes` page has a status endpoint that validates both the configured Job Posting database and the configured Resume database before enabling `Create Resume` actions. If either Notion schema is invalid, the page shows a blocked state and avoids write attempts until the relation contract is valid.
