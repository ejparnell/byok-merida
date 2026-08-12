from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable, Protocol
from uuid import uuid4

from .analysis_run_store import (
    ActiveAnalysisRunError,
    AnalysisCandidateState,
    AnalysisProviderCallState,
    AnalysisRunIdempotencyConflictError,
    AnalysisRunLifecycle,
    AnalysisRunOutcome,
    AnalysisRunSnapshot,
    SqliteAnalysisRunStore,
    TERMINAL_CANDIDATE_STATES,
)
from .analysis_authorization import AuthorizedApplicationAnalysisModel
from .analysis_graph import ApplicationAnalysisGraph
from .analysis_spend import (
    AnalysisCostEstimate,
    AnalysisSpendPolicy,
    AnalysisUsageReceipt,
)
from .ports import ApplicationAnalysisStore
from ...matching import EvidenceMatchingEngine
from ...shared.workspace import (
    WorkspaceCommitUnknownError,
    WorkspaceDataError,
    WorkspaceProviderError,
    WorkspaceReadiness,
)


logger = logging.getLogger(__name__)
# Notion body appends have one 30-second absolute attempt; the retry-safe
# properties PATCH can use three attempts plus bounded backoff. Two minutes
# keeps the durable fence alive beyond either remote mutation window.
_REMOTE_COMMIT_LEASE_PROTECTION = timedelta(minutes=2)


@dataclass(frozen=True)
class AnalysisCandidateEvaluation:
    state: AnalysisCandidateState
    reason_code: str | None = None
    stop_outcome: AnalysisRunOutcome | None = None
    stop_reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.state not in TERMINAL_CANDIDATE_STATES:
            raise ValueError("An Analysis candidate evaluation must be terminal.")
        if (self.stop_outcome is None) != (self.stop_reason_code is None):
            raise ValueError("A run-scoped stop requires an outcome and reason code.")


class AnalysisCandidateEvaluator(Protocol):
    async def evaluate(
        self, run_id: str, application_id: str, *, lease_owner: str
    ) -> AnalysisCandidateEvaluation: ...

    def reconcile_recorded_calls(
        self, run_id: str, *, lease_owner: str
    ) -> None: ...


class AnalysisReadinessValidator(Protocol):
    async def __call__(self) -> WorkspaceReadiness: ...


class AnalysisRunService:
    """Application-owned durable orchestration for one active Analysis Run."""

    def __init__(
        self,
        *,
        workspace: ApplicationAnalysisStore,
        store: SqliteAnalysisRunStore,
        evaluator: AnalysisCandidateEvaluator,
        readiness: AnalysisReadinessValidator | None = None,
        prerequisite_readiness: Callable[[], tuple[str, str] | None]
        | None = None,
        spend_readiness: Callable[[], bool] | None = None,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
        worker_id: str | None = None,
        lease_duration: timedelta = timedelta(seconds=30),
    ):
        self._workspace = workspace
        self._store = store
        self._evaluator = evaluator
        self._readiness = readiness or workspace.validate_analysis_workspace
        self._prerequisite_readiness = prerequisite_readiness or (
            lambda: None
        )
        self._spend_readiness = spend_readiness or (lambda: True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._run_id_factory = run_id_factory or (
            lambda: f"analysis-run-{uuid4().hex}"
        )
        self._worker_id = worker_id or f"analysis-worker-{uuid4().hex}"
        self._lease_duration = lease_duration

    async def start(
        self, *, target: int, idempotency_key: str
    ) -> AnalysisRunSnapshot:
        if type(target) is not int or not 1 <= target <= 10:
            raise ValueError("Analysis Batch Target must be from 1 through 10.")
        existing = self._store.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.target != target:
                raise AnalysisRunIdempotencyConflictError(
                    "The idempotency key already identifies a different target."
                )
            return existing

        active = self._store.get_active_run()
        if active is not None:
            raise ActiveAnalysisRunError(active.run_id)

        prerequisite_block = self._prerequisite_readiness()
        if prerequisite_block is not None:
            raise AnalysisRunStartBlocked(*prerequisite_block)
        if not self._spend_readiness():
            raise AnalysisRunStartBlocked(
                "spend_authority_unavailable",
                "Analysis spend enforcement is unavailable.",
            )
        await self._reconcile_commit_quarantines()
        readiness = await self._readiness()
        if not readiness.ready:
            raise AnalysisRunStartBlocked(
                "workspace_not_ready",
                "Application Analysis workspace validation is blocked.",
            )
        attempt_budget = target * 2
        quarantined = set(self._store.list_commit_quarantines())
        safe_candidates = [
            candidate
            for candidate in await self._workspace.load_analysis_queue_snapshot(
                excluded_application_ids=frozenset(quarantined)
            )
            if candidate.id not in quarantined
        ]
        candidates = safe_candidates[:attempt_budget]
        return self._store.create_run(
            run_id=self._run_id_factory(),
            idempotency_key=idempotency_key,
            target=target,
            candidate_ids=tuple(candidate.id for candidate in candidates),
            candidate_set_truncated=len(safe_candidates) > attempt_budget,
        )

    async def _reconcile_commit_quarantines(self) -> None:
        for application_id in self._store.list_commit_quarantines():
            try:
                application = await self._workspace.load_analysis_input(
                    application_id
                )
            except (WorkspaceDataError, WorkspaceProviderError):
                continue
            if application.analysis is not None:
                self._store.clear_commit_quarantine(application_id)

    def get(self, run_id: str) -> AnalysisRunSnapshot | None:
        return self._store.get_run(run_id)

    def active(self) -> AnalysisRunSnapshot | None:
        return self._store.get_active_run()

    def cancel(self, run_id: str) -> AnalysisRunSnapshot | None:
        snapshot = self._store.get_run(run_id)
        if snapshot is None:
            return None
        request_cancellation = getattr(self._store, "request_cancellation", None)
        if callable(request_cancellation):
            return request_cancellation(run_id)
        if snapshot.lifecycle is AnalysisRunLifecycle.FINISHED:
            return snapshot
        raise RuntimeError("The Analysis Run Store cannot persist cancellation.")

    async def process_next_run(self) -> AnalysisRunSnapshot | None:
        now = self._clock()
        claimed = self._store.claim_recoverable_run(
            lease_owner=self._worker_id,
            lease_expires_at=now + self._lease_duration,
        )
        if claimed is None:
            return None
        return await self._process_claimed(claimed.run_id)

    async def _process_claimed(self, run_id: str) -> AnalysisRunSnapshot:
        self._store.reconcile_interrupted_provider_calls(
            run_id, lease_owner=self._worker_id
        )
        reconcile_recorded_calls = getattr(
            self._evaluator, "reconcile_recorded_calls", None
        )
        if callable(reconcile_recorded_calls):
            reconcile_recorded_calls(
                run_id, lease_owner=self._worker_id
            )
        while True:
            snapshot = self._require_run(run_id)
            if snapshot.lifecycle is AnalysisRunLifecycle.CANCELLING:
                return await self._finish_cancelling_run(snapshot)
            if snapshot.completion_count >= snapshot.target:
                return self._finish(
                    run_id, AnalysisRunOutcome.TARGET_MET, "target_met"
                )

            self._store.renew_lease(
                run_id,
                lease_owner=self._worker_id,
                lease_expires_at=self._clock() + self._lease_duration,
            )
            candidate = self._store.claim_next_candidate(
                run_id, lease_owner=self._worker_id
            )
            if candidate is None:
                outcome = (
                    AnalysisRunOutcome.ATTEMPT_BUDGET_EXHAUSTED
                    if snapshot.candidate_set_truncated
                    else AnalysisRunOutcome.QUEUE_EXHAUSTED
                )
                return self._finish(run_id, outcome, outcome.value)

            candidate_was_evaluating = any(
                item.state is AnalysisCandidateState.EVALUATING
                for item in snapshot.candidates
            )
            recover = getattr(self._evaluator, "recover", None)
            evaluation = None
            if candidate_was_evaluating and callable(recover):
                evaluation = await self._await_with_heartbeat(
                    run_id,
                    recover(
                        run_id,
                        candidate.application_id,
                        lease_owner=self._worker_id,
                    ),
                )
            if evaluation is None:
                evaluation = await self._evaluate_with_heartbeat(
                    run_id, candidate.application_id
                )
            after = self._store.record_candidate_result(
                run_id,
                candidate.application_id,
                evaluation.state,
                reason_code=evaluation.reason_code,
                stop_outcome=evaluation.stop_outcome,
                stop_reason_code=evaluation.stop_reason_code,
                lease_owner=self._worker_id,
            )

            if after.lifecycle is AnalysisRunLifecycle.FINISHED:
                return after
            if after.lifecycle is AnalysisRunLifecycle.CANCELLING:
                return self._finish(run_id, AnalysisRunOutcome.CANCELLED, "cancelled")
            if after.completion_count >= after.target:
                return self._finish(
                    run_id, AnalysisRunOutcome.TARGET_MET, "target_met"
                )

    async def _finish_cancelling_run(
        self, snapshot: AnalysisRunSnapshot
    ) -> AnalysisRunSnapshot:
        candidate = next(
            (
                item
                for item in snapshot.candidates
                if item.state is AnalysisCandidateState.EVALUATING
            ),
            None,
        )
        if candidate is not None:
            recover = getattr(self._evaluator, "recover", None)
            evaluation = None
            if callable(recover):
                evaluation = await self._await_with_heartbeat(
                    snapshot.run_id,
                    recover(
                        snapshot.run_id,
                        candidate.application_id,
                        lease_owner=self._worker_id,
                        allow_retry=False,
                    ),
                )
            if evaluation is None:
                evaluation = AnalysisCandidateEvaluation(
                    AnalysisCandidateState.INDETERMINATE,
                    "interrupted_provider_call",
                )
            self._store.record_candidate_result(
                snapshot.run_id,
                candidate.application_id,
                evaluation.state,
                reason_code=evaluation.reason_code,
                lease_owner=self._worker_id,
            )
        return self._finish(
            snapshot.run_id, AnalysisRunOutcome.CANCELLED, "cancelled"
        )

    async def _evaluate_with_heartbeat(
        self, run_id: str, application_id: str
    ) -> AnalysisCandidateEvaluation:
        return await self._await_with_heartbeat(
            run_id,
            self._evaluator.evaluate(
                run_id,
                application_id,
                lease_owner=self._worker_id,
            ),
        )

    async def _await_with_heartbeat(self, run_id: str, awaitable):
        evaluation = asyncio.create_task(awaitable)
        heartbeat_seconds = max(
            0.05, self._lease_duration.total_seconds() / 3
        )
        try:
            while True:
                done, _pending = await asyncio.wait(
                    {evaluation}, timeout=heartbeat_seconds
                )
                if done:
                    return await evaluation
                self._store.renew_lease(
                    run_id,
                    lease_owner=self._worker_id,
                    lease_expires_at=self._clock() + self._lease_duration,
                )
        except BaseException:
            evaluation.cancel()
            try:
                await evaluation
            except asyncio.CancelledError:
                pass
            raise

    def _finish(
        self,
        run_id: str,
        outcome: AnalysisRunOutcome,
        reason_code: str | None,
    ) -> AnalysisRunSnapshot:
        return self._store.finish_run(
            run_id,
            outcome,
            reason_code=reason_code,
            lease_owner=self._worker_id,
        )

    def _require_run(self, run_id: str) -> AnalysisRunSnapshot:
        snapshot = self._store.get_run(run_id)
        if snapshot is None:
            raise RuntimeError("The claimed Analysis Run disappeared.")
        return snapshot

class AnalysisRunStartBlocked(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class GraphAnalysisCandidateEvaluator:
    """Connects the durable runner to one independently committed graph run."""

    def __init__(
        self,
        *,
        workspace: ApplicationAnalysisStore,
        model,
        store: SqliteAnalysisRunStore,
        spend_policy: AnalysisSpendPolicy,
        matcher: EvidenceMatchingEngine | None = None,
    ):
        self._workspace = workspace
        self._model = model
        self._store = store
        self._spend_policy = spend_policy
        self._matcher = matcher or EvidenceMatchingEngine()

    async def evaluate(
        self, run_id: str, application_id: str, *, lease_owner: str
    ) -> AnalysisCandidateEvaluation:
        try:
            application = await self._workspace.load_analysis_input(application_id)
        except WorkspaceDataError:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "source_unreadable",
            )
        except WorkspaceProviderError as error:
            if error.status == 404:
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.FAILED,
                    "source_unreadable",
                )
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "unsafe_storage_failure",
                AnalysisRunOutcome.FAILED,
                "unsafe_storage_failure",
            )
        fenced_workspace = _LeaseFencedAnalysisWorkspace(
            self._workspace,
            ledger=self._store,
            run_id=run_id,
            lease_owner=lease_owner,
        )
        authorized_model = AuthorizedApplicationAnalysisModel(
            self._model,
            store=self._store,
            spend_policy=self._spend_policy,
            run_id=run_id,
            application_id=application_id,
            lease_owner=lease_owner,
        )
        outcome = await ApplicationAnalysisGraph(
            fenced_workspace,
            authorized_model,
            self._matcher,
        ).run(application, batch_run_id=run_id)
        if outcome.result == "analyzed":
            self._store.clear_commit_quarantine(application_id)
            return AnalysisCandidateEvaluation(AnalysisCandidateState.ANALYZED)
        if outcome.result == "repaired":
            self._store.clear_commit_quarantine(application_id)
            return AnalysisCandidateEvaluation(AnalysisCandidateState.REPAIRED)
        if outcome.result == "skipped":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.SKIPPED,
                outcome.reason_code or "became_ineligible",
            )

        reason_code = outcome.reason_code or "candidate_evaluation_failed"
        indeterminate = any(
            evidence.transmission_state == "indeterminate"
            for evidence in outcome.call_evidence
        )
        if reason_code == "spend_limited":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                reason_code,
                AnalysisRunOutcome.SPEND_LIMITED,
                reason_code,
            )
        if reason_code in {
            "rate_card_unavailable",
            "model_not_approved",
            "pricing_approval_expired",
            "output_bound_not_approved",
            "tokenizer_unavailable",
            "request_not_rendered",
            "authentication_failed",
            "balance_insufficient",
            "spend_authority_unavailable",
            "request_protocol_mismatch",
            "request_model_mismatch",
            "request_output_bound_mismatch",
        }:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                reason_code,
                AnalysisRunOutcome.AUTHORIZATION_BLOCKED,
                reason_code,
            )
        if outcome.failure_scope == "run":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE
                if indeterminate
                else AnalysisCandidateState.FAILED,
                reason_code,
                AnalysisRunOutcome.FAILED,
                reason_code,
            )
        return AnalysisCandidateEvaluation(
            AnalysisCandidateState.INDETERMINATE
            if indeterminate
            else AnalysisCandidateState.FAILED,
            reason_code,
        )

    def reconcile_recorded_calls(
        self, run_id: str, *, lease_owner: str
    ) -> None:
        for call in self._store.list_provider_calls(run_id):
            if call.state is AnalysisProviderCallState.RESPONSE_RECORDED:
                self._settle_recorded_response(
                    call, lease_owner=lease_owner
                )

    async def recover(
        self,
        run_id: str,
        application_id: str,
        *,
        lease_owner: str,
        allow_retry: bool = True,
    ) -> AnalysisCandidateEvaluation | None:
        calls = tuple(
            call
            for call in self._store.list_provider_calls(run_id)
            if call.application_id == application_id
            and call.state is not AnalysisProviderCallState.RELEASED
        )
        for call in calls:
            if call.state is AnalysisProviderCallState.RESPONSE_RECORDED:
                self._settle_recorded_response(
                    call, lease_owner=lease_owner
                )
        calls = tuple(
            call
            for call in self._store.list_provider_calls(run_id)
            if call.application_id == application_id
            and call.state is not AnalysisProviderCallState.RELEASED
        )
        try:
            application = await self._workspace.load_analysis_input(application_id)
        except WorkspaceDataError:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "source_unreadable",
            )
        except WorkspaceProviderError as error:
            if error.status == 404:
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.FAILED,
                    "source_unreadable",
                )
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "unsafe_storage_failure",
                AnalysisRunOutcome.FAILED,
                "unsafe_storage_failure",
            )
        if application.analyzed and application.analysis is not None:
            self._store.clear_commit_quarantine(application_id)
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.REPAIRED
                if not calls
                else AnalysisCandidateState.ANALYZED
            )
        if application.analyzed:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.SKIPPED,
                "became_ineligible",
            )
        if application.analysis is not None:
            repaired = await self._repair_partial_analysis_during_cancellation(
                run_id,
                application,
                lease_owner=lease_owner,
            )
            if repaired.state is AnalysisCandidateState.REPAIRED:
                self._store.clear_commit_quarantine(application_id)
                if calls:
                    return AnalysisCandidateEvaluation(
                        AnalysisCandidateState.ANALYZED
                    )
            return repaired
        if application_id in set(self._store.list_commit_quarantines()):
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE,
                "commit_unknown",
            )
        transmitted_calls = tuple(
            call for call in calls if call.transmission_index is not None
        )
        last_transmitted_call = max(
            transmitted_calls,
            key=lambda call: call.transmission_index or 0,
            default=None,
        )
        last_result_code = (
            None if last_transmitted_call is None else last_transmitted_call.result_code
        )
        authorization_failure = (
            last_result_code
            if last_result_code
            in {"authentication_failed", "balance_insufficient"}
            else None
        )
        if authorization_failure is not None:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE,
                authorization_failure,
                AnalysisRunOutcome.AUTHORIZATION_BLOCKED,
                authorization_failure,
            )
        terminal_systemic_failure = (
            last_result_code
            if last_result_code in {"invalid_request", "provider_error"}
            else None
        )
        if terminal_systemic_failure is not None:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE,
                terminal_systemic_failure,
                AnalysisRunOutcome.FAILED,
                terminal_systemic_failure,
            )
        if last_result_code in {
            "response_processing_failed",
            "response_valid_storage_rejected",
        }:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "unsafe_storage_failure",
                AnalysisRunOutcome.FAILED,
                "unsafe_storage_failure",
            )
        if last_result_code == "response_valid_source_unreadable":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED,
                "source_unreadable",
            )
        if last_result_code == "response_received":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE,
                "response_processing_interrupted",
            )
        if not calls:
            if not allow_retry:
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.SKIPPED,
                    "cancelled_before_dispatch",
                )
            return None
        transmission_count = len(transmitted_calls)
        exhausted_systemic_failure = (
            last_result_code
            if last_result_code
            in {
                "absolute_deadline_exceeded",
                "provider_unavailable",
                "rate_limited",
                "transport_unavailable",
            }
            else None
        )
        if transmission_count >= 3 and exhausted_systemic_failure is not None:
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE,
                exhausted_systemic_failure,
                AnalysisRunOutcome.FAILED,
                exhausted_systemic_failure,
            )
        if all(
            call.state is AnalysisProviderCallState.SETTLED for call in calls
        ):
            if any(
                call.result_code == "response_valid_commit_unknown"
                for call in calls
            ):
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.INDETERMINATE,
                    "commit_unknown",
                )
            if not allow_retry:
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.FAILED,
                    "cancelled_after_settled_call",
                )
            if any(call.result_code == "response_valid" for call in calls):
                return AnalysisCandidateEvaluation(
                    AnalysisCandidateState.FAILED,
                    "unsafe_storage_failure",
                    AnalysisRunOutcome.FAILED,
                    "unsafe_storage_failure",
                )
            return None
        if allow_retry and transmission_count < 3:
            return None
        return AnalysisCandidateEvaluation(
            AnalysisCandidateState.INDETERMINATE,
            "interrupted_provider_call",
        )

    async def _repair_partial_analysis_during_cancellation(
        self,
        run_id: str,
        application,
        *,
        lease_owner: str,
    ) -> AnalysisCandidateEvaluation:
        outcome = await ApplicationAnalysisGraph(
            _LeaseFencedAnalysisWorkspace(
                self._workspace,
                ledger=self._store,
                run_id=run_id,
                lease_owner=lease_owner,
            ),
            _ProviderCallsForbiddenDuringCancellation(),
            self._matcher,
        ).run(application, batch_run_id=run_id)
        if outcome.result == "repaired":
            return AnalysisCandidateEvaluation(AnalysisCandidateState.REPAIRED)
        if outcome.result == "skipped":
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.SKIPPED,
                outcome.reason_code or "became_ineligible",
            )
        reason_code = outcome.reason_code or "unsafe_storage_failure"
        if outcome.failure_scope == "run":
            indeterminate = any(
                evidence.transmission_state == "indeterminate"
                for evidence in outcome.call_evidence
            )
            return AnalysisCandidateEvaluation(
                AnalysisCandidateState.INDETERMINATE
                if indeterminate
                else AnalysisCandidateState.FAILED,
                reason_code,
                AnalysisRunOutcome.FAILED,
                reason_code,
            )
        return AnalysisCandidateEvaluation(
            AnalysisCandidateState.FAILED,
            reason_code,
        )

    def _settle_recorded_response(self, call, *, lease_owner: str) -> None:
        required = (
            call.endpoint,
            call.model,
            call.approval_fingerprint,
            call.request_fingerprint,
            call.tokenizer_tokens,
            call.utf8_bytes,
            call.protocol_overhead_tokens,
            call.input_cost_bound_tokens,
            call.max_output_tokens,
            call.cache_hit_input_micros_per_million_tokens,
            call.cache_miss_input_micros_per_million_tokens,
            call.output_micros_per_million_tokens,
            call.provider_request_id,
            call.input_tokens,
            call.output_tokens,
            call.cache_hit_input_tokens,
        )
        if any(value is None for value in required):
            self._store.transition_provider_call(
                call.call_id,
                AnalysisProviderCallState.INDETERMINATE,
                lease_owner=lease_owner,
            )
            return
        estimate = AnalysisCostEstimate(
            provider="deepseek",
            endpoint=call.endpoint,
            model=call.model,
            approval_fingerprint=call.approval_fingerprint,
            request_fingerprint=call.request_fingerprint,
            tokenizer_tokens=call.tokenizer_tokens,
            utf8_bytes=call.utf8_bytes,
            protocol_overhead_tokens=call.protocol_overhead_tokens,
            input_cost_bound_tokens=call.input_cost_bound_tokens,
            max_output_tokens=call.max_output_tokens,
            cache_hit_input_micros_per_million_tokens=(
                call.cache_hit_input_micros_per_million_tokens
            ),
            cache_miss_input_micros_per_million_tokens=(
                call.cache_miss_input_micros_per_million_tokens
            ),
            output_micros_per_million_tokens=(
                call.output_micros_per_million_tokens
            ),
            worst_case_micros=call.reservation_micros,
        )
        receipt = AnalysisUsageReceipt(
            provider_request_id=call.provider_request_id,
            endpoint=call.endpoint,
            model=call.model,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            cache_hit_input_tokens=call.cache_hit_input_tokens,
            cache_miss_input_tokens=call.cache_miss_input_tokens,
            total_tokens=call.total_tokens,
            reasoning_output_tokens=call.reasoning_output_tokens,
            finish_reason=call.finish_reason,
        )
        settlement = self._spend_policy.settle(estimate, receipt)
        if settlement.valid and settlement.verified_cost_micros is not None:
            self._store.settle_provider_call(
                call.call_id,
                verified_cost_micros=settlement.verified_cost_micros,
                result_code=call.result_code,
                lease_owner=lease_owner,
            )
        else:
            self._store.transition_provider_call(
                call.call_id,
                AnalysisProviderCallState.INDETERMINATE,
                lease_owner=lease_owner,
            )


class _LeaseFencedAnalysisWorkspace:
    """Revalidates worker ownership at every irreversible Notion boundary."""

    def __init__(self, workspace, *, ledger, run_id: str, lease_owner: str):
        self._workspace = workspace
        self._ledger = ledger
        self._run_id = run_id
        self._lease_owner = lease_owner

    def _assert_lease(self) -> None:
        self._ledger.assert_current_lease(
            self._run_id,
            lease_owner=self._lease_owner,
            allow_cancelling=True,
        )

    def _protect_remote_commit(self) -> None:
        self._ledger.protect_remote_commit(
            self._run_id,
            lease_owner=self._lease_owner,
            minimum_duration=_REMOTE_COMMIT_LEASE_PROTECTION,
        )

    async def validate_analysis_workspace(self):
        return await self._workspace.validate_analysis_workspace()

    async def list_analysis_queue(self, *, limit, cursor):
        return await self._workspace.list_analysis_queue(
            limit=limit, cursor=cursor
        )

    async def load_analysis_queue_snapshot(
        self, *, excluded_application_ids=frozenset()
    ):
        return await self._workspace.load_analysis_queue_snapshot(
            excluded_application_ids=excluded_application_ids
        )

    async def load_analysis_input(self, application_id):
        return await self._workspace.load_analysis_input(application_id)

    async def load_analysis_evidence(self):
        return await self._workspace.load_analysis_evidence()

    async def append_application_analysis(self, application_id, document):
        self._protect_remote_commit()
        self._ledger.quarantine_commit_unknown(
            self._run_id,
            application_id,
            lease_owner=self._lease_owner,
        )
        try:
            result = await self._workspace.append_application_analysis(
                application_id, document
            )
        except WorkspaceProviderError as error:
            if _remote_commit_result_is_unknown(error):
                raise WorkspaceCommitUnknownError(
                    "The Analysis body commit has an unknown remote result."
                ) from error
            self._ledger.clear_commit_quarantine(application_id)
            raise
        except BaseException as error:
            raise WorkspaceCommitUnknownError(
                "The Analysis body commit has an unknown remote result."
            ) from error
        try:
            self._assert_lease()
        except BaseException as error:
            raise WorkspaceCommitUnknownError(
                "The Analysis body commit has an unknown remote result."
            ) from error
        self._ledger.clear_commit_quarantine(application_id)
        return result

    async def finalize_application_analysis(self, application_id, *, match_score):
        self._protect_remote_commit()
        self._ledger.quarantine_commit_unknown(
            self._run_id,
            application_id,
            lease_owner=self._lease_owner,
        )
        try:
            result = await self._workspace.finalize_application_analysis(
                application_id, match_score=match_score
            )
        except WorkspaceProviderError as error:
            if _remote_commit_result_is_unknown(error):
                raise WorkspaceCommitUnknownError(
                    "The Analysis property commit has an unknown remote result."
                ) from error
            self._ledger.clear_commit_quarantine(application_id)
            raise
        except BaseException as error:
            raise WorkspaceCommitUnknownError(
                "The Analysis property commit has an unknown remote result."
            ) from error
        try:
            self._assert_lease()
        except BaseException as error:
            raise WorkspaceCommitUnknownError(
                "The Analysis property commit has an unknown remote result."
            ) from error
        self._ledger.clear_commit_quarantine(application_id)
        return result


def _remote_commit_result_is_unknown(error: WorkspaceProviderError) -> bool:
    """Only a definitive rejected response proves a mutation did not apply."""
    return error.status is None or error.status < 400 or error.status >= 500


class _ProviderCallsForbiddenDuringCancellation:
    async def generate(self, *_args, **_kwargs):
        raise RuntimeError(
            "Provider dispatch is forbidden while recovering a cancelling run."
        )


class AnalysisRunWorker:
    """A lifespan-owned retained task; HTTP requests only wake it."""

    def __init__(
        self,
        service: AnalysisRunService,
        *,
        recovery_poll_seconds: float = 1.0,
    ):
        if recovery_poll_seconds <= 0:
            raise ValueError("Recovery polling must use a positive interval.")
        self._service = service
        self._recovery_poll_seconds = recovery_poll_seconds
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._idle = asyncio.Event()
        self._idle.set()

    def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run())
        self.wake()

    def wake(self) -> None:
        self._idle.clear()
        self._wake.set()

    async def wait_idle(self) -> None:
        await self._idle.wait()

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        # Never shorten a persisted lease during shutdown. A cancelled remote
        # request can still be applied by Notion, so replacement workers wait
        # for the normal or remote-commit-protected lease to expire.

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.wait_for(
                    self._wake.wait(), timeout=self._recovery_poll_seconds
                )
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            if self._stopping:
                return
            self._idle.clear()
            try:
                while await self._service.process_next_run() is not None:
                    pass
            except Exception as error:
                logger.error(
                    "Analysis worker paused after safe failure error_type=%s",
                    type(error).__name__,
                )
            finally:
                self._idle.set()
