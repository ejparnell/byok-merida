# Use a centralized repo-local skill normalization dictionary

Skill Normalization starts with a repo-local dictionary instead of integrating a full external taxonomy such as O*NET or ESCO. High-value aliases such as `Postgres -> PostgreSQL`, `RESTful APIs -> REST APIs`, `JS -> JavaScript`, and project-specific AI or LLM terms should live in one centralized, testable data source shared by the Resume Fit Analysis runtime rather than being hard-coded throughout the codebase, so the dictionary can grow from real postings without scattering matching rules.
