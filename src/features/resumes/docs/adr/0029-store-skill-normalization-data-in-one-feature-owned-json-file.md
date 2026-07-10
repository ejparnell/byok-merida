# Store skill normalization data in one feature-owned JSON file

The Skill Normalization dictionary lives in one feature-owned data file under `src/features/resumes/data/`, using a simple format such as JSON that both Node and Python can read. Python uses the shared file for NLP normalization and scoring, while Node uses the same file for validation and tests, avoiding duplicated alias lists across runtimes.
