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
| Partial-effect recovery | Content-free JSON effect journal                   |

The graphs use no durable LangGraph checkpointer. Runs are bounded, have no human interrupt, and may contain private Job Content or Master Resume evidence that must not be copied into a graph database or normal logs.

## DeepSeek adapter contract

The product composition creates task-specific adapters for:

- Application Analysis
- Fit Requirement extraction
- Resume Draft generation

Adapters own provider client construction, model selection, prompt messages, JSON request encoding, structured-output decoding, bounded retry policy, and safe provider-error translation. Workflow modules consume semantic values and validate every proposal before persistence.

Normal logs and public responses must not contain credentials, prompts, Job Content, Master Resume content, generated Resume text, raw provider payloads, or local paths.

## Application Analysis graph

One graph invocation processes one eligible Application:

1. load the Application and readable Job Content;
2. detect a readable persisted analysis that needs property repair;
3. otherwise request a structured DeepSeek analysis proposal;
4. validate the three-sentence analysis and every Skill Signal/evidence pair;
5. permit one structured repair request for invalid model output;
6. load Master Resume evidence;
7. calculate Match Score through `matching-v1`;
8. persist the readable analysis body first;
9. commit `Analyzed` and Match Score properties last.

The batch workflow runs Applications sequentially and isolates item failures. A body-first partial result remains repairable without repeating model work.

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
