# Prototype the minimal Resume Run durability boundary

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: prototype

Status: ready-for-human

State: closed

Assignee: codex

Blocked by: [Set the Resume Run Spend Ceiling](03-set-resume-run-spend-ceiling.md), [Define Resume Run source consistency and candidate revalidation](04-define-resume-run-source-consistency.md), and [Define run-owned artifact identity and same-run recovery](05-define-run-owned-artifact-recovery.md)

## Question

What is the smallest Resumes-owned durable coordination design that preserves Resume Run identity, idempotency, the fixed Candidate Set, sequential progress, provider-call and spend state, cancellation, leases, source consistency, and run-owned artifact recovery across restart without duplicate paid transmissions or artifacts, while allowing an independent Analysis Run to overlap?

The prototype should make the privacy and feasibility trade-off concrete across crashes before reservation, before and after transmission, between the two model stages, after a validated private result, and after each artifact effect. It must prove the smallest protected Resume Source Version Proof and recovery-scoped private Resume Artifact Checkpoint required by tickets 04 and 05, including their atomic boundary, at-rest protection, quarantine retention, and safe retirement constraints. It should also test whether to extract a generic durable-run kernel or keep Resume semantics in a Resumes-owned store rather than reusing the Applications-owned Analysis schema directly.

## Decisions

- Use one Resumes-owned transactional SQLite database for Resume Run coordination, call accounting, leases, source proofs, private checkpoints, artifact intent, quarantine, and the logical Completion seal. Keeping encrypted checkpoint rows in the same database is what permits the required metadata-and-checkpoint transitions to commit together. A separate checkpoint file or database would require an outbox, orphan collection, and another recovery protocol without reducing the minimum private payload.
- Do not reuse the Applications-owned Analysis Run schema. Analysis and Resume Runs may overlap, have independent active-run constraints and spend ledgers, and disagree at a critical restart boundary: Analysis may release and reuse a proven-unsent transmission slot, while Resume Generation consumes every stage attempt even when its reservation is later released. Reuse only small policy-free primitives after implementation demonstrates a real common interface; do not begin with a generic durable-run kernel.
- Keep ordinary coordination content-free. It may retain opaque run, candidate, call, source-proof, Artifact Set, page, PDF, and lease identities; ordinals; lifecycle and effect states; exact integer-micro reservations and settlements; version tags; digests; bounded reason codes; timestamps; terminal result identities; and the finalized download basename. It must not contain prompts, reasoning, provider request or response bodies, Job Content, Application Analysis, Master Resume content, validated Requirements, or canonical Resume and Note documents.
- Define Resume Source Proof v1 as SHA-256 over the ASCII domain `merida-resume-source-proof-v1`, NUL, ASCII scope, NUL, an unsigned 64-bit big-endian JSON byte length, and canonical UTF-8 JSON for only the semantically relevant fields in one complete Stable Resume Source Observation. JSON objects sort keys lexicographically with no insignificant whitespace; strings normalize only to Unicode NFC and LF line endings; relation identities sort lexicographically; arrays whose order is semantic preserve it; and values are restricted to strings, signed 64-bit integers, Booleans, null, arrays, and string-keyed objects. Observation/revision tokens used to prove a stable read are retained separately and do not enter the semantic proof, so unrelated management edits cannot invalidate a candidate.
- Store the run's exact canonical Master Resume Version in a protected Master Source Checkpoint at run creation, atomically with the fixed Candidate Set and its safe Master proof. This deliberately chooses recovery availability over the smaller fingerprint-only/block-on-edit alternative allowed by ticket 04: all candidates are expected to remain runnable after the live Master is edited or removed. The safe digest detects corruption and binds the snapshot; it is not itself enough to regenerate later candidates.
- Store only the Candidate Source proof in safe coordination. At Candidate Admission and every continuation boundary, reload a fresh Stable Resume Source Observation and require the same proof. If the source remains equal, its current bytes supply the fixed candidate input; a definite change invalidates the candidate rather than requiring a long-lived private candidate snapshot or mixing versions. An ambiguous or incomplete observation fails closed. If artifact effects already exist, source change enters the ticket-05 recovery/quarantine path instead of creating replacements.
- Add one protected Draft Basis Checkpoint between the two provider stages. It contains the exact complete versioned `ResumeDraftInput`: validated Fit Requirements plus the deterministic matching/evidence-selection result and every renderer input not already fixed by the two source proofs. Its binding metadata includes run, candidate, Master proof, Candidate proof, Draft-input schema, matching/evidence-selection policy, renderer version, and producing call identity. It omits source bodies, prompts, reasoning, and the raw provider response. Without this checkpoint, a restart between stages must either replay paid Requirements work or risk changing the Draft request across a deployment.
- Atomically replace the Draft Basis Checkpoint with ticket 05's protected Resume Artifact Checkpoint when a Draft validates. The same transaction creates the immutable Artifact Set ID and intent, stores the exact canonical Resume and Note documents, records their v1 document digests and binding proofs, advances the candidate to artifact recovery, and deletes the superseded Draft Basis checkpoint. No artifact effect may begin before this commit.
- Protect every private checkpoint in production with AES-256-GCM from an audited in-process cryptography library, using a fresh 96-bit nonce, an externally supplied versioned 256-bit key, and authenticated associated data binding the checkpoint kind and schema version to its run, candidate, source proofs, producing call, and Artifact Set where applicable. The database and recovery directory also require least-privilege filesystem permissions, but permissions are defense in depth rather than content protection. Missing, wrong, revoked, or unauthenticated key material fails readiness or recovery closed; keys and plaintext never enter ordinary state, logs, snapshots, or error details.
- Provision and retain checkpoint keys outside the database and include key version in safe metadata. Rotation may rewrap a checkpoint only in one authenticated read/write transaction while its old key remains available. Operational backup and key-retention policy must keep a key for every live or quarantined checkpoint. Logical deletion is the promised retirement boundary; neither SQLite deletion nor key retirement is represented as guaranteed physical erasure from WAL pages, filesystem snapshots, or backups.
- Retire the Draft Basis checkpoint in the atomic Draft-to-Artifact transition or after ticket 07 records a definitive pre-artifact terminal candidate outcome from which no recovery is permitted. Retire an Artifact checkpoint only after the Completion seal or fully verified terminal compensation. Retire the Master checkpoint only when the run has no candidate, unsealed Artifact Set, or quarantine that can still depend on it. Quarantine has no time-based expiry and retains every required checkpoint and key. Post-seal checkpoint deletion is idempotent cleanup and may be retried without reopening or recounting the Completion.
- Persist Resume provider calls with a stage-local monotonically consumed attempt number, exact request fingerprint, reservation, authorization fingerprint, and a pre-dispatch or may-have-dispatched marker. Reservation and attempt consumption commit before transmission. Restart releases spend only from the durable pre-dispatch state, but does not restore that attempt; a may-have-dispatched call becomes indeterminate and keeps its complete reservation committed. A retry always consumes the next stage attempt and a fresh authorization. The store permits at most one durably authorized Resume call at a time, independently of an overlapping Analysis call. Lease reclaim does not assert that an abandoned socket stopped: after a may-have-dispatched marker, the old attempt is permanently uncertain and the next dispatch is possible only after that uncertainty is classified and the stage's separate retry slot and spend authorization remain available.
- Fence Resume workers with a transactional lease epoch presented and checked on every coordination write and immediately before every external dispatch. A fresh claimant advances the epoch; stale epochs cannot write or begin another effect, while any effect already beyond its dispatch marker remains ambiguous and is handled by observation rather than assumed stopped. Cancellation atomically blocks new candidate admissions and provider authorizations, but preserves settled spend, indeterminate reservations, immutable prior Completions, partial-set recovery evidence, and quarantine. Ticket 07 owns whether already-started artifact work recovers forward, pauses, or proceeds to verified compensation; this ticket does not blanket-prohibit those mutations.
- Run creation atomically acquires the single-active-Resume-Run claim, stores the immutable idempotency binding, and writes the run/Master checkpoint transaction. Reusing the same key with the same canonical start request returns the original run forever; the same key with a different request is rejected. A distinct key is rejected while a nonterminal Resume Run owns the claim and creates a new opaque never-reused run identity afterward. Historical bindings and Artifact Set non-reuse tombstones outlive presentation-history cleanup.
- Before every external artifact mutation, commit the exact Artifact Set intent and expected identity/digest evidence. After restart or a lost response, observe the external system and reconcile by exact identity. One valid match advances, multiple matches or unprovable ownership quarantine, and zero matches retries only for a locally repeatable effect or after affirmative non-dispatch. Recovery never reruns generation, allocates a replacement Artifact Set ID, or adopts an independent artifact.
- The Completion seal is one transaction over the candidate Completion, run count/progress, terminal Artifact Set state, compact permanent ownership/non-reuse record, and stable result identities. A crash before it leaves an unsealed set requiring fresh validation; a crash after it cannot recount, reopen, or compensate the set. Checkpoint deletion remains outside the seal as retryable cleanup.

## Atomic boundaries

1. Run creation commits one idempotency binding, one fixed ordered Candidate Set, the captured spend policy, the Master Source proof, and the encrypted Master Source Checkpoint together.
2. Candidate Admission commits one consumed evaluation, one Candidate Source proof, and its evaluating state before the first provider reservation.
3. Call authorization commits the consumed stage attempt, exact-request fingerprint, complete reservation, authorization evidence, and pre-dispatch marker; crossing the may-have-dispatched marker commits before network transmission.
4. A valid Requirements response commits validated-output state, the encrypted Draft Basis Checkpoint, and either trustworthy usage settlement or a full indeterminate reservation together; output validity never manufactures billing evidence.
5. A valid Draft commits validated-output state, either trustworthy usage settlement or a full indeterminate reservation, immutable Artifact Set identity and intent, the encrypted Resume Artifact Checkpoint and both semantic digests, and deletion of the Draft Basis checkpoint together.
6. Every artifact effect commits intent before the external mutation and verified observed evidence afterward. Those are deliberately two transactions because Notion and PDF storage cannot participate in SQLite's transaction; exact identity and fresh observation close the gap.
7. The logical Completion seal commits Completion, progress, permanent ownership, non-reuse, and stable result identities together. Private-checkpoint deletion follows only as idempotent terminal cleanup.

## Digest v1 golden vectors

Artifact Document Digest v1 serializes the ASCII domain tag `merida-artifact-document-digest-v1`, NUL, the document kind as an unsigned 16-bit big-endian byte length plus ASCII bytes, the ordered block count as unsigned 32-bit big-endian, then every block's kind as an unsigned 16-bit big-endian length plus ASCII bytes, depth as unsigned 32-bit big-endian, and text as an unsigned 64-bit big-endian length plus normalized UTF-8 bytes. Only Unicode NFC and CRLF/CR-to-LF normalization apply. Resume and Note kinds are distinct digest domains.

| Input | SHA-256 |
| --- | --- |
| Resume blocks `heading_1(depth 0, "Résumé\\r\\nWriter")`, `paragraph(depth 1, "Cafe\\u0301")` | `ca26bbf982a00dc784cfdc5ed53ec33c079e8038122fd0d757c03f4512d9a32b` |
| Empty Note document | `8f7c7a799512782163635c9cefe56ca2f7f15a9e110c98207fc077e7ca373592` |
| Master Source Proof implementation vector for `{"revision":7,"skills":["Cafe\\u0301"],"title":"Résumé\\r\\nWriter"}` | `ffe91a518bf4912ef764e5873f4fe813bed10df09e8b8bbfd51627cb3488d714` |

The first Resume vector is byte-identical to the same blocks using LF and precomposed `Café`; block reordering, document-kind change, depth change, or any other textual change produces a different digest.

## Prototype evidence

The throwaway prototype lives beside the Resumes feature in `apps/api/merida_api/features/resumes/prototype_resume_run_durability/` and runs with `npm run resume-run-durability-prototype`. Its deterministic matrix uses a scratch SQLite database, separates safe JSON from encrypted private rows, and scans the database plus WAL/SHM files for known plaintext markers.

| Scenario | Observed result |
| --- | --- |
| Idempotent identity, lease fencing, Analysis overlap | The same start key returned one fixed Candidate Set, a second worker was fenced, and the simulated Analysis Run stayed active. |
| Stale-worker reclaim | A fresh store instance advanced the epoch, continued the run, and the old store instance could no longer mutate coordination. |
| Before and after provider transmission | A pre-dispatch crash released the reservation but retained the consumed attempt; a post-marker crash retained the full reservation as indeterminate and used the next attempt for recovery. |
| Between Requirements and Draft | Restart reopened the validated encrypted Draft Basis checkpoint and authorized Draft without replaying Requirements. |
| Draft/checkpoint atomicity | The injected rollback exposed either Draft-Basis-ready state or Artifact Set intent plus both documents, never a half-created boundary. |
| Checkpoint tampering | Wrong key, modified ciphertext, and a row-identity transplant all failed closed. |
| Effect intent without observation | A fresh process retried a proven-unsent local intent, while a zero-match remote effect after its dispatch marker quarantined. |
| Lost response after every artifact effect | PDF staging, Resume creation, PDF publication, Note creation, and relation attachment each reconciled forward with the original Artifact Set ID and no provider replay. |
| Completion seal | The injected pre-commit crash left zero Completions; one later seal recorded exactly one Completion, and repeated restart did not recount it. |
| Fresh Completion Gate | A uniquely keyed Resume whose semantic digest changed after earlier observation was rejected and quarantined rather than sealed. |
| Ambiguous ownership | Multiple exact-key matches quarantined the Application and retained its private checkpoint through restart and cancellation. |
| Source edits | An encrypted Master snapshot survived a live edit; the digest-only admitted Candidate Source invalidated on a definite change instead of being substituted. |
| Spend boundary | A reservation equal to remaining authorized budget succeeded, one micro above failed, and the Analysis ledger remained separate. |

The experiment supports a Resume-specific transaction model and three narrowly scoped encrypted checkpoint kinds. It rejects both a content-free-only design, which cannot cross the two-stage or partial-artifact crash windows, and direct reuse of the Analysis schema, whose call-attempt and lifecycle semantics differ.

## Answer

The smallest viable boundary for the selected availability contract is one Resumes-owned transactional store with content-free coordination and three encrypted, recovery-scoped checkpoint kinds: one run-level Master Resume snapshot, one per-current-candidate complete deterministic Draft Basis, and one per-unsealed Artifact Set containing only the exact canonical Resume and Note documents. Safe versioned digests bind those private rows to the run, fixed sources, calls, and Artifact Set without exposing their content. Candidate source values themselves need no durable snapshot: Merida reloads and proves their exact admitted version before continuing, and invalidates rather than substitutes on a definite change.

Provider reservation, attempt consumption, and the pre-dispatch marker live in the same transaction authority as run progress. The may-have-dispatched marker precedes network I/O, so restart may release only a reservation that is durably proven unsent, never restore its consumed attempt, and must conservatively retain every possibly sent call. Artifact intent and observed evidence bracket each external effect, while exact Artifact Set identity makes lost responses reconcilable without provider replay or replacement artifacts. One atomic logical seal prevents duplicate Completion counts; checkpoint deletion is later retryable cleanup.

Production should implement this as a Resumes-owned schema, not an Applications-owned Analysis schema or a premature generic kernel. It should use audited AEAD with externally managed versioned keys and fail closed when protected state is unavailable. Quarantine retains the checkpoint and key for as long as ownership is unresolved. Safe retirement means policy-gated logical deletion after seal or verified compensation plus ordinary WAL/checkpoint and backup-retention operations; it does not promise forensic erasure from copies outside the live store.

## Testing decisions

- Replace the prototype matrix with deterministic store-contract tests at every transaction and external-effect barrier. Reopen a fresh application instance over the same stores; use no timing sleeps and make no paid or live Notion calls.
- Publish Artifact Document Digest and Resume Source Proof golden-vector suites that cover every accepted block kind, ordering, depth validation, document-kind separation, Unicode NFC, LF normalization, preserved whitespace/case/punctuation, multibyte text, unknown kinds, truncation, canonical object ordering, relation ordering, and torn/incomplete observations.
- Test the public safe-state allowlist and inspect SQLite, WAL, SHM, logs, errors, events, spend rows, ownership records, and snapshots for private markers. Separately prove authenticated decryption, wrong-key and modified-ciphertext failure, key-version rotation, and readiness failure when required key authority is unavailable.
- Test exact-boundary and one-micro-over spend admission, consumed attempts after proven non-dispatch, indeterminate retention after the dispatch marker, usage settlement independent of output validity, cancellation, lease fencing, and simultaneous independent Analysis activity.
- Run ticket 05's complete artifact crash matrix through the same Resume transaction authority, including checkpoint corruption/deletion, multiple matches, quarantine retention, seal replay, post-seal cleanup retry, and strict verified compensation.

## Out of scope

- Ticket 07 owns failure classes, attempt exhaustion outcomes, cancellation precedence, backfill behavior, compensation initiation, and terminal reason codes.
- Ticket 08 owns public routes, snapshots, recovery commands, result retention, operator diagnostics, and download-name presentation.
- Ticket 09 owns dashboard presentation and interaction.
- Key-provider selection, deployment-secret delivery, backup retention periods, and live-store migration mechanics belong to implementation/operations tickets, but they may not weaken the readiness, retention, or fail-closed rules fixed here.
- The prototype's OpenSSL-backed encrypt-then-MAC construction is experimental scaffolding only and is not an approved production cryptographic implementation.
