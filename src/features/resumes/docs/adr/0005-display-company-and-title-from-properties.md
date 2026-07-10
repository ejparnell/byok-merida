# Display company and title from properties

The `/resumes` queue displays Job Posting `Company Name` and `Job Title` from their dedicated Notion properties instead of parsing the combined `Job Posting` title. Those properties already exist in the Job Posting database, match the operator-facing UI, and avoid brittle title parsing when company or role names contain words such as `at` or use unusual formatting.
