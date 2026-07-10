# Move the Local Operator backend shell out of Job Postings

The local HTTP backend is an app-level Local Operator module, not part of the Job Postings feature.

Job Postings still owns Job Posting capture, Job Posting Analysis, Capture Evidence parsing, and the `/analysis` operator page. Resumes still owns Resume Creation, Resume Fit Analysis checks, and the `/resumes` operator page. The Local Operator module owns the shared interface around localhost HTTP routing, CORS, capture-token checks, same-origin operator writes, JSON request parsing, NDJSON streaming support, health response shape, and startup of the repo-local Resume Fit Analysis runtime.

This keeps `/analysis` and `/resumes` as separate operator pages while removing the shallow Job Postings backend module that had started to import Resumes modules and Fit runtime startup. Feature modules now provide route adapters at the Local Operator seam. The seam is real because both Job Postings and Resumes use it, while tests can still replace those adapters or their feature clients without reaching through the shell implementation.

`npm start` starts the Local Operator module from `src/backend/start.js`. `npm run start:node` starts only the Node Local Operator HTTP server from `src/backend/server.js`.
