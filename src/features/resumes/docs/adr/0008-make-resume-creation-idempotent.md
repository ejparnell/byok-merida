# Make resume creation idempotent

`Create Resume` is idempotent for Job-Specific Resume creation. If the selected Job Posting already has a related Resume when the backend handles the request, the backend returns that existing Resume instead of creating another one, protecting against stale pages, refresh races, and double-clicks.
