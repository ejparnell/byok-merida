# Set the concurrency, idempotency, and recovery boundaries

Type: grilling
Status: open
Blocked by: 05, 06, 07
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What v1 execution rules should govern overlapping analysis and resume requests, per-Application exclusion, request retries, idempotency keys or durable markers, partial Notion and PDF commits, compensation, process crashes, and the boundary between automated and manual recovery without a durable LangGraph checkpointer?
