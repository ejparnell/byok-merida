from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import uuid4

from .analysis_run_store import (
    AnalysisProviderAuthorizationMetadata,
    AnalysisProviderCallState,
    AnalysisProviderSettlementMetadata,
    AnalysisRunStoreError,
    SqliteAnalysisRunStore,
)
from .analysis_spend import (
    AnalysisSpendPolicy,
    AnalysisSpendPolicyError,
    AnalysisUsageReceipt,
)
from .workspace import (
    AnalysisCallEvidence,
    AnalysisModelResponse,
    ApplicationRecord,
)


@dataclass(frozen=True)
class PreparedAnalysisCall:
    endpoint: str
    model: str
    max_output_tokens: int
    rendered_request: bytes
    opaque: object


class PreparedApplicationAnalysisModel(Protocol):
    def prepare(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> PreparedAnalysisCall: ...

    async def transmit(
        self, prepared: PreparedAnalysisCall
    ) -> AnalysisModelResponse: ...


class AnalysisCallBlocked(RuntimeError):
    retryable = False

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.call_evidence = AnalysisCallEvidence(
            transmission_state="not_transmitted"
        )


class SpendLimitReached(AnalysisCallBlocked):
    pass


class SpendAuthorizationBlocked(AnalysisCallBlocked):
    pass


class AuthorizedApplicationAnalysisModel:
    """Reserves and settles every call around one exact provider dispatch."""

    def __init__(
        self,
        model: PreparedApplicationAnalysisModel,
        *,
        store: SqliteAnalysisRunStore,
        spend_policy: AnalysisSpendPolicy,
        run_id: str,
        application_id: str,
        lease_owner: str,
        call_id_factory: Callable[[], str] | None = None,
    ):
        self._model = model
        self._store = store
        self._spend_policy = spend_policy
        self._run_id = run_id
        self._application_id = application_id
        self._lease_owner = lease_owner
        self._call_id_factory = call_id_factory or (
            lambda: f"analysis-call-{uuid4().hex}"
        )
        all_calls = tuple(
            call
            for call in self._store.list_provider_calls(run_id)
            if call.application_id == application_id
        )
        self._authorization_index = max(
            (call.authorization_index for call in all_calls), default=0
        )
        self._pending_settlement: tuple[str, int] | None = None

    async def generate(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> AnalysisModelResponse:
        try:
            prepared = self._model.prepare(application, repair_code=repair_code)
        except Exception as error:
            raise SpendAuthorizationBlocked(
                "request_not_rendered",
                "The exact Analysis request could not be rendered.",
            ) from error
        try:
            estimate = self._spend_policy.estimate(
                endpoint=prepared.endpoint,
                model=prepared.model,
                rendered_request=prepared.rendered_request,
                max_output_tokens=prepared.max_output_tokens,
            )
        except AnalysisSpendPolicyError as error:
            raise SpendAuthorizationBlocked(error.code, str(error)) from error

        transmitted = sum(
            call.transmission_index is not None
            for call in self._store.list_provider_calls(self._run_id)
            if call.application_id == self._application_id
        )
        if transmitted >= 3:
            raise SpendAuthorizationBlocked(
                "application_call_budget_exhausted",
                "The Application provider-call budget is exhausted.",
            )
        self._authorization_index += 1
        call_id = self._call_id_factory()
        try:
            reservation = self._store.reserve_provider_call(
                run_id=self._run_id,
                application_id=self._application_id,
                call_id=call_id,
                call_index=self._authorization_index,
                reservation_micros=estimate.worst_case_micros,
                authorization=AnalysisProviderAuthorizationMetadata(
                    endpoint=estimate.endpoint,
                    model=estimate.model,
                    approval_fingerprint=estimate.approval_fingerprint,
                    request_fingerprint=estimate.request_fingerprint,
                    tokenizer_tokens=estimate.tokenizer_tokens,
                    utf8_bytes=estimate.utf8_bytes,
                    protocol_overhead_tokens=estimate.protocol_overhead_tokens,
                    input_cost_bound_tokens=estimate.input_cost_bound_tokens,
                    max_output_tokens=estimate.max_output_tokens,
                    cache_hit_input_micros_per_million_tokens=(
                        estimate.cache_hit_input_micros_per_million_tokens
                    ),
                    cache_miss_input_micros_per_million_tokens=(
                        estimate.cache_miss_input_micros_per_million_tokens
                    ),
                    output_micros_per_million_tokens=(
                        estimate.output_micros_per_million_tokens
                    ),
                ),
                lease_owner=self._lease_owner,
            )
        except AnalysisRunStoreError as error:
            raise SpendAuthorizationBlocked(
                "spend_authority_unavailable",
                "Analysis spend enforcement is unavailable.",
            ) from error
        if reservation is None:
            raise SpendLimitReached(
                "spend_limited",
                "The next Analysis call cannot fit under the $0.50 run ceiling.",
            )

        # This committed transition is the final local action before dispatch.
        begin_dispatch = getattr(self._store, "begin_provider_dispatch", None)
        try:
            if callable(begin_dispatch):
                begin_dispatch(call_id, lease_owner=self._lease_owner)
            else:
                self._store.transition_provider_call(
                    call_id,
                    AnalysisProviderCallState.DISPATCHING,
                    lease_owner=self._lease_owner,
                )
        except AnalysisRunStoreError as error:
            try:
                self._store.release_provider_call(
                    call_id, lease_owner=self._lease_owner
                )
            except AnalysisRunStoreError:
                pass
            raise SpendAuthorizationBlocked(
                "cancelled_before_dispatch",
                "The Analysis call was stopped before dispatch.",
            ) from error
        try:
            response = await self._model.transmit(prepared)
        except BaseException as error:
            evidence = getattr(error, "call_evidence", None)
            if not isinstance(evidence, AnalysisCallEvidence):
                evidence = AnalysisCallEvidence(transmission_state="indeterminate")
            result_code = getattr(error, "code", "provider_error")
            if not isinstance(result_code, str):
                result_code = "provider_error"
            self._reconcile(
                call_id,
                estimate,
                prepared,
                evidence,
                result_code=result_code,
            )
            raise
        evidence = response.call_evidence or AnalysisCallEvidence(
            transmission_state="indeterminate"
        )
        if evidence.transmission_state == "not_transmitted":
            self._reconcile(
                call_id,
                estimate,
                prepared,
                evidence,
                result_code="response_unusable",
            )
        else:
            verified_cost_micros = self._record_response(
                call_id,
                estimate,
                prepared,
                evidence,
                result_code="response_received",
            )
            if verified_cost_micros is not None:
                self._pending_settlement = (call_id, verified_cost_micros)
        return response

    def settle_last_call(self, *, result_code: str) -> None:
        pending = self._pending_settlement
        if pending is None:
            return
        call_id, verified_cost_micros = pending
        self._store.settle_provider_call(
            call_id,
            verified_cost_micros=verified_cost_micros,
            result_code=result_code,
            lease_owner=self._lease_owner,
        )
        self._pending_settlement = None

    def _reconcile(
        self,
        call_id: str,
        estimate,
        prepared: PreparedAnalysisCall,
        evidence: AnalysisCallEvidence,
        *,
        result_code: str,
    ) -> None:
        if evidence.transmission_state == "not_transmitted":
            self._store.release_provider_call(
                call_id, lease_owner=self._lease_owner
            )
            return

        verified_cost_micros = self._record_response(
            call_id,
            estimate,
            prepared,
            evidence,
            result_code=result_code,
        )
        if verified_cost_micros is not None:
            self._store.settle_provider_call(
                call_id,
                verified_cost_micros=verified_cost_micros,
                result_code=result_code,
                lease_owner=self._lease_owner,
            )

    def _record_response(
        self,
        call_id: str,
        estimate,
        prepared: PreparedAnalysisCall,
        evidence: AnalysisCallEvidence,
        *,
        result_code: str,
    ) -> int | None:
        receipt = _usage_receipt(prepared, evidence)
        if receipt is not None:
            self._store.record_provider_call_response(
                call_id,
                AnalysisProviderSettlementMetadata(
                    provider_request_id=receipt.provider_request_id,
                    input_tokens=receipt.input_tokens,
                    output_tokens=receipt.output_tokens,
                    cache_hit_input_tokens=receipt.cache_hit_input_tokens,
                    cache_miss_input_tokens=receipt.cache_miss_input_tokens,
                    total_tokens=receipt.total_tokens,
                    reasoning_output_tokens=receipt.reasoning_output_tokens,
                    finish_reason=_safe_result_code(receipt.finish_reason),
                    result_code=result_code,
                ),
                lease_owner=self._lease_owner,
            )
            settlement = self._spend_policy.settle(estimate, receipt)
            if settlement.valid and settlement.verified_cost_micros is not None:
                return settlement.verified_cost_micros
        self._store.transition_provider_call(
            call_id,
            AnalysisProviderCallState.INDETERMINATE,
            result_code=result_code,
            lease_owner=self._lease_owner,
        )
        return None


def _usage_receipt(
    prepared: PreparedAnalysisCall,
    evidence: AnalysisCallEvidence,
) -> AnalysisUsageReceipt | None:
    if (
        evidence.transmission_state != "sent"
        or not evidence.request_id
        or evidence.model_id != prepared.model
        or type(evidence.input_tokens) is not int
        or type(evidence.output_tokens) is not int
    ):
        return None
    cache_hit = evidence.cache_hit_input_tokens
    if type(cache_hit) is not int:
        cache_hit = 0
    return AnalysisUsageReceipt(
        provider_request_id=evidence.request_id,
        endpoint=prepared.endpoint,
        model=evidence.model_id,
        input_tokens=evidence.input_tokens,
        output_tokens=evidence.output_tokens,
        cache_hit_input_tokens=cache_hit,
        cache_miss_input_tokens=(
            evidence.cache_miss_input_tokens
            if type(evidence.cache_miss_input_tokens) is int
            else None
        ),
        total_tokens=(
            evidence.total_tokens if type(evidence.total_tokens) is int else None
        ),
        reasoning_output_tokens=(
            evidence.reasoning_output_tokens
            if type(evidence.reasoning_output_tokens) is int
            else None
        ),
        finish_reason=evidence.finish_reason,
    )


def _safe_result_code(value: str | None) -> str | None:
    if value in {"stop", "length", "max_tokens"}:
        return value
    return None
