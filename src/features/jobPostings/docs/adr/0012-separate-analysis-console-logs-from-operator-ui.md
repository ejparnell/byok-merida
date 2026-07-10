# Separate analysis console logs from operator UI

Job Posting Analysis keeps detailed diagnostics in console logs while the local HTML interface stays small and focused. Logs include batch start/end, queue count, page id/title, read/extract/LLM/validate/append/checkbox steps, model name, and failure details; the browser UI shows only counts, current item, compact results, and concise errors. Raw Job Content, prompts, API keys, and full model responses are not logged or displayed by default.
