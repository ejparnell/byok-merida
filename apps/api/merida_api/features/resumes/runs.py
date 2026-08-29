from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

from .creation import ResumeCreation
from .checkpoint_vault import CheckpointBinding, ResumeCheckpointVault
from .resume_spend import ResumeSpendPolicy, ResumeUsageReceipt
from .run_store import (
    ResumeRunStopping,
    ResumeSpendLimitReached,
    SqliteResumeRunStore,
)
from .source_versions import (
    application_document,
    master_document,
    restore_application,
    restore_master,
    source_proof,
)
from ...integrations.deepseek import DeepSeekCallEvidence
from ...integrations.deepseek_resume import (
    PreparedResumeStageCall,
    ResumeStageResult,
    resume_stage_dispatch_scope,
)


class ResumeRunStartBlocked(RuntimeError):
    def __init__(self, reason_code: str):
        super().__init__("Resume Run prerequisites are not ready.")
        self.reason_code = reason_code


class ResumeRunService:
    def __init__(
        self,
        *,
        resumes: ResumeCreation,
        workspace,
        store: SqliteResumeRunStore,
        user_name: str,
        run_id_factory=None,
        artifact_set_id_factory=None,
        spend_policy: ResumeSpendPolicy | None = None,
        pdf_store_root: Path | None = None,
        checkpoint_vault: ResumeCheckpointVault | None = None,
    ):
        self._resumes = resumes
        self._workspace = workspace
        self._store = store
        self._user_name = user_name
        self._run_id_factory = run_id_factory or (lambda: f"resume-run-{uuid4().hex}")
        self._artifact_set_id_factory = artifact_set_id_factory or (
            lambda: f"resume-artifact-{uuid4().hex}"
        )
        self._spend_policy = spend_policy
        self._pdf_store_root = pdf_store_root.resolve() if pdf_store_root else None
        self._checkpoint_vault = checkpoint_vault

    async def start(self, *, target: int, idempotency_key: str) -> dict:
        replay = self._store.replay(idempotency_key, target)
        if replay is not None:
            return replay
        if not self._store.available or not self._store.transactional:
            raise ResumeRunStartBlocked("run_store_unavailable")
        if self._spend_policy is None:
            raise ResumeRunStartBlocked("resume_authorization_blocked")
        if self._checkpoint_vault is None:
            raise ResumeRunStartBlocked("checkpoint_key_unavailable")
        if not self._user_name.strip():
            raise ResumeRunStartBlocked("resume_configuration_invalid")
        readiness = await self._resumes.validate_readiness()
        if not readiness.ready:
            raise ResumeRunStartBlocked("workspace_contract_mismatch")
        first_master = await self._workspace.load_master_resume()
        second_master = await self._workspace.load_master_resume()
        if first_master != second_master:
            raise ResumeRunStartBlocked("workspace_observation_unstable")
        page = await self._workspace.list_resume_queue(limit=target * 2, cursor=None)
        selected = [item for item in page.items if (item.match_score or 0) >= 70][
            : target * 2
        ]
        candidates = [
            (item.id, f"{item.role} at {item.company_name}") for item in selected
        ]
        run_id = self._run_id_factory()
        master_payload = master_document(first_master)
        master_proof = source_proof(master_payload)
        master_checkpoint = self._checkpoint_vault.seal(
            CheckpointBinding(
                kind="master_source",
                schema_version=1,
                run_id=run_id,
                source_proof=master_proof,
            ),
            master_payload,
        )
        return self._store.start(
            run_id=run_id,
            idempotency_key=idempotency_key,
            target=target,
            candidates=candidates,
            queue_exhausted=page.total <= target * 2,
            master_source_proof=master_proof,
            master_checkpoint=master_checkpoint,
        )

    def get(self, run_id: str) -> dict | None:
        return self._store.get(run_id)

    def active(self) -> dict | None:
        return self._store.active()

    def latest(self) -> dict | None:
        return self._store.latest()

    def cancel(self, run_id: str) -> dict | None:
        return self._store.cancel(run_id)

    def artifact_set(self, artifact_set_id: str) -> dict | None:
        return self._store.artifact_set(artifact_set_id)

    def quarantines(self, *, limit: int, offset: int = 0):
        return self._store.quarantines(limit=limit, offset=offset)

    def request_artifact_action(
        self, *, artifact_set_id: str, kind: str, expected_revision: int,
        idempotency_key: str,
    ):
        return self._store.request_artifact_action(
            artifact_set_id=artifact_set_id, kind=kind,
            expected_revision=expected_revision, idempotency_key=idempotency_key,
        )

    def verified_pdf(self, artifact_set_id: str) -> tuple[Path, str] | None:
        record = self._store.pdf_record(artifact_set_id)
        if record is None or self._pdf_store_root is None:
            return None
        raw_path, expected_digest, filename = record
        try:
            resolved = Path(raw_path).resolve(strict=True)
            resolved.relative_to(self._pdf_store_root)
            if not resolved.is_file():
                return None
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except (OSError, ValueError):
            return None
        if digest != expected_digest:
            return None
        return resolved, filename

    async def process(self, run_id: str) -> None:
        snapshot = self._store.get(run_id)
        if snapshot is None or snapshot["lifecycle"] == "finished":
            return
        if snapshot["lifecycle"] == "cancelling":
            self._store.finish_cancellation(run_id)
            return
        snapshot = self._store.begin(run_id)
        if not snapshot["candidates"]:
            self._store.finish(run_id)
            return
        for candidate in snapshot["candidates"]:
            current = self._store.get(run_id)
            if current is None or current["outcome"] is not None:
                break
            ordinal = candidate["ordinal"]
            if candidate["state"] not in {"pending", "evaluating", "recovering"}:
                continue
            try:
                assert self._checkpoint_vault is not None
                if candidate["state"] == "pending":
                    first = await self._workspace.load_resume_input(
                        candidate["applicationId"]
                    )
                    second = await self._workspace.load_resume_input(
                        candidate["applicationId"]
                    )
                    payload = application_document(first)
                    proof = source_proof(payload)
                    if first != second or (first.match_score or 0) < 70 or first.resume_ids:
                        self._store.begin_candidate(run_id, ordinal)
                        self._store.fail_candidate(
                            run_id, ordinal, "candidate_became_ineligible"
                        )
                        continue
                    checkpoint = self._checkpoint_vault.seal(
                        CheckpointBinding(
                            kind="candidate_source",
                            schema_version=1,
                            run_id=run_id,
                            source_proof=proof,
                            candidate_ordinal=ordinal,
                        ),
                        payload,
                    )
                    if not self._store.admit_candidate(
                        run_id,
                        ordinal,
                        source_proof=proof,
                        checkpoint=checkpoint,
                    ):
                        continue
                candidate_record = self._store.checkpoint(
                    run_id, "candidate_source", ordinal
                )
                master_record = self._store.checkpoint(run_id, "master_source")
                if candidate_record is None or master_record is None:
                    raise RuntimeError("required checkpoint unavailable")
                proof, encrypted_candidate = candidate_record
                master_proof, encrypted_master = master_record
                application = restore_application(
                    self._checkpoint_vault.open(
                        CheckpointBinding(
                            kind="candidate_source", schema_version=1,
                            run_id=run_id, source_proof=proof,
                            candidate_ordinal=ordinal,
                        ),
                        encrypted_candidate,
                    )
                )
                master = restore_master(
                    self._checkpoint_vault.open(
                        CheckpointBinding(
                            kind="master_source", schema_version=1,
                            run_id=run_id, source_proof=master_proof,
                        ),
                        encrypted_master,
                    )
                )
                with resume_stage_dispatch_scope(
                    self._dispatcher(run_id, application, proof)
                ):
                    bundle = await self._resumes.build_fixed_sources(
                        application, master, run_id=run_id
                    )
                await self._require_unchanged(application, proof)
                artifact_set_id = self._artifact_set_id_factory()
                artifact_payload = {
                    "resume": [asdict(block) for block in bundle.resume],
                    "note": [asdict(block) for block in bundle.note],
                }
                artifact_proof = source_proof(artifact_payload)
                artifact_checkpoint = self._checkpoint_vault.seal(
                    CheckpointBinding(
                        kind="artifact", schema_version=1, run_id=run_id,
                        source_proof=artifact_proof, candidate_ordinal=ordinal,
                        artifact_set_id=artifact_set_id,
                    ),
                    artifact_payload,
                )
                self._store.start_artifact_set(
                    artifact_set_id=artifact_set_id,
                    run_id=run_id,
                    ordinal=ordinal,
                    checkpoint_source_proof=artifact_proof,
                    checkpoint=artifact_checkpoint,
                )
                staged = self._resumes.stage_fixed_bundle(bundle)
                committed = await self._resumes.commit_fixed_bundle(
                    application,
                    bundle,
                    run_id=run_id,
                    artifact_set_id=artifact_set_id,
                    staged_pdf=staged,
                )
            except (ResumeRunStopping, ResumeSpendLimitReached):
                current = self._store.get(run_id)
                if current and current["lifecycle"] == "cancelling":
                    break
                self._store.fail_candidate(run_id, ordinal, "spend_limited")
                break
            except Exception:
                self._store.fail_candidate(run_id, ordinal, "run_execution_failure")
                break
            if not committed.committed:
                self._store.fail_candidate(run_id, ordinal, "artifact_commit_failed")
                break
            assert committed.resume is not None
            assert committed.note is not None
            assert committed.pdf_path is not None
            now = datetime.now(timezone.utc).isoformat()
            pdf_path = committed.pdf_path
            completion = {
                "sealedAt": now,
                "resume": {"id": committed.resume.id, "url": committed.resume.url},
                "note": {"id": committed.note.id, "url": committed.note.url},
                "pdf": {
                    "filename": pdf_path.name,
                    "downloadUrl": f"/api/v1/resumes/artifact-sets/{artifact_set_id}/pdf",
                },
            }
            digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            self._store.complete_candidate(
                run_id,
                ordinal,
                artifact_set_id=artifact_set_id,
                completion=completion,
                pdf_path=str(pdf_path.resolve()),
                pdf_digest=digest,
            )
        current = self._store.get(run_id)
        if current is not None and current["lifecycle"] == "cancelling":
            self._store.finish_cancellation(run_id)
        elif current is not None and current["lifecycle"] != "finished":
            self._store.finish(run_id)

    def _dispatcher(self, run_id: str, application, admitted_proof: str):
        async def dispatch(prepared: PreparedResumeStageCall, transport):
            assert self._spend_policy is not None
            await self._require_unchanged(application, admitted_proof)
            estimate = self._spend_policy.estimate(
                endpoint=prepared.endpoint,
                model=prepared.model,
                rendered_request=prepared.rendered_request,
                max_output_tokens=prepared.max_output_tokens,
            )
            attempt = self._store.next_call_attempt(
                run_id, application.id, prepared.stage
            )
            call_id = f"resume-call-{uuid4().hex}"
            self._store.reserve_call(
                call_id=call_id,
                run_id=run_id,
                application_id=application.id,
                stage=prepared.stage,
                attempt=attempt,
                reservation_micros=estimate.worst_case_micros,
                approval_fingerprint=estimate.approval_fingerprint,
                request_fingerprint=estimate.request_fingerprint,
                authorization=asdict(estimate),
            )
            self._store.mark_call_dispatching(call_id)
            try:
                result: ResumeStageResult = await transport(prepared)
            except Exception as error:
                self._resolve_call(call_id, estimate, getattr(error, "evidence", None))
                raise
            self._resolve_call(call_id, estimate, result.evidence)
            return result

        return dispatch

    async def _require_unchanged(self, application, admitted_proof: str) -> None:
        current = await self._workspace.load_resume_input(application.id)
        if source_proof(application_document(current)) != admitted_proof:
            raise ResumeRunStopping("The admitted Resume source changed.")

    def _resolve_call(self, call_id: str, estimate, evidence: DeepSeekCallEvidence | None) -> None:
        assert self._spend_policy is not None
        settlement = self._spend_policy.settle(
            estimate, _usage_receipt(estimate.endpoint, evidence)
        )
        self._store.resolve_call(
            call_id,
            transmission_state=(
                "indeterminate" if evidence is None else evidence.transmission_state
            ),
            verified_cost_micros=(
                settlement.verified_cost_micros if settlement.valid else None
            ),
        )


def _usage_receipt(endpoint: str, evidence: DeepSeekCallEvidence | None):
    if (
        evidence is None
        or evidence.request_id is None
        or evidence.model_id is None
        or evidence.input_tokens is None
        or evidence.output_tokens is None
    ):
        return None
    return ResumeUsageReceipt(
        provider_request_id=evidence.request_id,
        endpoint=endpoint,
        model=evidence.model_id,
        input_tokens=evidence.input_tokens,
        output_tokens=evidence.output_tokens,
        cache_hit_input_tokens=evidence.cache_hit_input_tokens or 0,
        cache_miss_input_tokens=evidence.cache_miss_input_tokens,
        total_tokens=evidence.total_tokens,
        reasoning_output_tokens=evidence.reasoning_output_tokens,
        finish_reason=evidence.finish_reason,
    )


class ResumeRunWorker:
    def __init__(self, service: ResumeRunService):
        self._service = service
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            self.wake()

    def wake(self) -> None:
        self._wake.set()

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopping:
            await self._wake.wait()
            self._wake.clear()
            active = self._service.active()
            if active is not None:
                await self._service.process(active["runId"])
