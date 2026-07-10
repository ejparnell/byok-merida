# Split resume fit runtime between Node and Python

The Resume Fit Analysis workflow splits responsibilities between Node and a repo-local Python runtime. Python owns ML/NLP-heavy primitives such as TF-IDF or BM25-style keyword coverage, tokenization, normalization helpers, optional local embedding experiments, similarity math, and scoring calculations, while Node owns Notion reads and writes, workflow orchestration, external LLM or model API calls, evidence validation before writes, Resume page creation, and starting or stopping the Python service through `npm start`.
