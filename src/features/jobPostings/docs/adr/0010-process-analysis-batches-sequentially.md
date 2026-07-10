# Process analysis batches sequentially

Analysis Batch Runs process one Job Posting at a time instead of parallelizing LLM and Notion updates. Sequential processing keeps local progress reporting, console logs, retry behavior, and API-rate-limit handling simple for a small operator-triggered tool where debuggability matters more than throughput.
