# AI and ML Workflows

Merida uses DeepSeek for bounded structured generation and deterministic Python modules for evidence matching and scoring. Language-model output is always treated as a proposal: Pydantic validation, evidence checks, deterministic policies, and ordered persistence decide whether it can become durable Application or Resume data.

## Runtime boundaries

| Concern                 | Owner                                              |
| ----------------------- | -------------------------------------------------- |
| Graph orchestration     | Feature-owned LangGraph `StateGraph` modules       |
| Provider transport      | DeepSeek adapters under `merida_api/integrations/` |
| Structured model output | Task-specific Pydantic proposal models             |
| Prompt payloads         | JSON produced immediately before the provider call |
| Evidence matching       | Versioned deterministic `matching-v1` policy       |
| Durable records         | Workflow-owned Notion store operations             |
| Analysis coordination   | Applications-owned SQLite Analysis Run Store       |
| Partial-effect recovery | Content-free JSON effect journal                   |

The graphs use no durable LangGraph checkpointer. Graph invocations are bounded,
have no human interrupt, and may contain private Job Content or Master Resume
evidence that must not be copied into a graph database or normal logs. Durable
Application Analysis coordination lives outside the graph in a metadata-only
SQLite store; Notion remains authoritative for completed analyses.

## DeepSeek adapter contract

The product composition creates task-specific adapters for:

- Application Analysis
- Fit Requirement extraction
- Resume Draft generation

Adapters own provider client construction, model selection, prompt messages, JSON request encoding, structured-output decoding, deadlines, and safe provider-error translation. The Application Analysis graph owns its one shared recovery loop so transport retries and structured-output repairs cannot multiply. Workflow modules consume semantic values and validate every proposal before persistence.

Normal logs and public responses must not contain credentials, prompts, Job Content, Master Resume content, generated Resume text, raw provider payloads, or local paths.

## Application Analysis graph

One graph invocation evaluates one eligible Application:

1. load the Application and readable Job Content;
2. detect a readable persisted analysis that needs property repair;
3. otherwise request a structured DeepSeek analysis proposal with thinking explicitly enabled at high effort, a reasoning-inclusive 8,000 generated-token ceiling, and non-streaming transport;
4. validate the three-sentence analysis as a unit and validate every Skill Signal/evidence pair independently;
5. discard unsupported, generic, and duplicate signals, merge near-duplicates, order required before preferred and other useful signals, and accept only three to ten valid signals;
6. when necessary, recover within one three-transmission Application Call Budget shared by initial generation, transient transport recovery, and structured-output repair;
7. load Master Resume evidence;
8. calculate Match Score through `matching-v1` from accepted signals only;
9. persist the readable analysis body first;
10. commit `Analyzed` and Match Score properties last.

Each transmitted response consumes one of the three slots, including truncation,
empty output, malformed JSON, and semantically invalid output. Every recovery
call retains thinking at high effort and the same output ceiling; there is no
non-thinking fallback and no fourth transmission. The transport uses a 10-second
connection timeout, 120-second read-inactivity timeout, and five-minute absolute
deadline. Safe evidence records transmission state, finish reason, exact model,
request identity, and usage, but never reasoning content. A post-transmission
deadline is indeterminate.

## Durable Analysis Run orchestration

An Analysis Run pursues a successful-completion target rather than an attempt
count. At creation it snapshots at most `target × 2` candidate identities in
canonical queue order. A background worker reloads and revalidates candidates,
evaluates each at most once and sequentially, and backfills after skips and
Candidate-Scoped Failures. A body-first partial result remains repairable without
repeating model work and counts only after final properties commit.

Before every provider transmission, the backend measures the exact rendered
request and obtains Cost Authorization against an approved endpoint/model rate
card. The full worst-case charge commits in SQLite before dispatch. Cost
Settlement releases unused reservation only from a proven pre-transmission
failure or trustworthy matching usage; missing or ambiguous evidence remains
committed. Verified cost, active reservations, and indeterminate reservations
together can never exceed 500,000 USD micros for one run.

Candidate-specific source/output defects allow backfill. Shared authorization,
pricing, storage, or exhausted systemic provider defects stop the run. On
restart, queued runs plus running or cancelling runs with expired leases are
reclaimed, sent calls are reconciled or conservatively made indeterminate before
new authorization, and terminal runs never resume. Cancellation prevents future
calls while preserving prior completions and honestly settling any call already
in flight.

## Resume Creation graphs

Resume Creation has an outer effect workflow and an inner Resume Document graph.

The Resume Document graph:

1. validates Job Content, Application Analysis, and Master Resume structure;
2. extracts typed Fit Requirements with source evidence;
3. matches each requirement against Master Resume evidence deterministically;
4. blocks before writes when required evidence is insufficient;
5. supplies only selected evidence and role targets to Resume Draft generation;
6. validates every generated bullet, evidence ID, requirement ID, and source role;
7. removes unsupported or cross-role claims;
8. preserves role chronology and non-work sections;
9. deterministically completes role coverage within the five-to-seven bullet policy;
10. renders one canonical Resume Document plus Resume Fit Analysis Note content.

The outer workflow revalidates eligibility and idempotency, stages the PDF, then delegates ordered effects to `ResumeArtifactCommitter`.

## Deterministic Matching

Matching is provider-independent. It owns:

- text normalization and the versioned skill-normalization dictionary;
- candidate ranking;
- evidence-strength classification;
- requirement/category scoring;
- Match Score and Resume Fit Score calculation;
- generation gates based on validated evidence.

The active policy is versioned as `matching-v1`. Model variability cannot change deterministic scores or bypass evidence gates.

## Artifact commit and recovery

Resume artifacts use one validated source document for Notion and PDF rendering. Effects occur in this order:

1. stage the PDF locally;
2. create the Resume draft;
3. create the Resume Fit Analysis Note;
4. publish the PDF;
5. attach the Resume to the Application last.

Failures compensate completed effects in reverse order. Ambiguous residue is recorded in the content-free effect journal and blocks conflicting mutations until reconciliation or explicit operator acknowledgement.

Use `npm run recovery -- inspect` before attempting repair. Recovery reports safe identifiers and phases, never private content.

## Test composition

Credential-free tests inject deterministic model, workspace, PDF, and journal fakes through `create_app`. They exercise the same workflow modules and ASGI routes as the real composition but cannot be selected as a product runtime.

Provider adapters are covered with deterministic transports and recordings. The final behavior corpus under `apps/api/tests/fixtures/final-parity.v1.json` assigns every protected behavior to a final workflow or public regression.
