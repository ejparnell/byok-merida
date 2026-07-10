# Run fit analysis as a long-running local Python service

The repo-local Python runtime for Resume Fit Analysis runs as a long-running localhost service started by `npm start`, not as a per-request script. This gives the Node backend a clean health-check target, avoids repeated model or vectorizer startup cost, and lets `/resumes/status` report ML runtime availability before enabling `Create Resume`.
