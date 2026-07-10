# Append analysis before marking analyzed

Job Posting Analysis appends Analysis Findings to the Notion page body before checking the required `Analyzed` checkbox. This keeps failed appends retryable, treats an existing `Job Posting Analysis` section as durable proof of analysis, and lets a later run repair a missed checkbox update without appending duplicate findings.
