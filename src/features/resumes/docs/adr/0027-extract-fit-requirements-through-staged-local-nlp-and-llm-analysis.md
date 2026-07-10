# Extract Fit Requirements through staged local NLP and LLM analysis

Fit Requirement extraction uses both local NLP and an LLM in stages. The Python runtime extracts candidate keywords, normalized terms, repeated phrases, and lexical coverage from Job Content; the LLM produces structured Fit Requirements with source evidence phrases; then Node validates those requirements against Job Content and enriches them with local keyword and similarity metrics so semantic structure is useful without being trusted blindly.
