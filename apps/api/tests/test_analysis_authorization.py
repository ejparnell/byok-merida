from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from merida_api.features.applications.analysis_authorization import (
    AuthorizedApplicationAnalysisModel,
    PreparedAnalysisCall,
    SpendLimitReached,
)
from merida_api.features.applications.analysis_run_store import (
    AnalysisProviderCallState,
    SqliteAnalysisRunStore,
)
from merida_api.features.applications.analysis_spend import (
    AnalysisCostEstimate,
    AnalysisSettlement,
)
from merida_api.features.applications.workspace import (
    AnalysisCallEvidence,
    AnalysisModelResponse,
    ApplicationRecord,
)


NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _application() -> ApplicationRecord:
    return ApplicationRecord(
        id="app-1",
        url="https://notion.test/app-1",
        company_name="Example",
        role="Engineer",
        job_url="https://jobs.test/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 1, 1),
        application_status="To Apply",
        analyzed=False,
        match_score=None,
        job_content="Build Python services, REST APIs, and automated tests.",
    )


class FixedSpendPolicy:
    def __init__(self, reservation_micros: int, *, settle: bool = True):
        self.reservation_micros = reservation_micros
        self.can_settle = settle

    def estimate(self, **request) -> AnalysisCostEstimate:
        assert request["rendered_request"] == b'{"exact":true}'
        return AnalysisCostEstimate(
            provider="deepseek",
            endpoint=request["endpoint"],
            model=request["model"],
            approval_fingerprint="approval",
            request_fingerprint="fingerprint",
            tokenizer_tokens=4,
            utf8_bytes=14,
            protocol_overhead_tokens=0,
            input_cost_bound_tokens=14,
            max_output_tokens=request["max_output_tokens"],
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
            worst_case_micros=self.reservation_micros,
        )

    def settle(self, estimate, receipt) -> AnalysisSettlement:
        del estimate
        if not self.can_settle or receipt is None:
            return AnalysisSettlement(False, None, "settlement_evidence_missing")
        return AnalysisSettlement(True, 125, None)


class PreparedModel:
    def __init__(self, evidence: AnalysisCallEvidence):
        self.evidence = evidence
        self.transmissions = 0

    def prepare(self, application, *, repair_code=None) -> PreparedAnalysisCall:
        del application, repair_code
        return PreparedAnalysisCall(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            max_output_tokens=8000,
            rendered_request=b'{"exact":true}',
            opaque=None,
        )

    async def transmit(self, prepared) -> AnalysisModelResponse:
        assert prepared.rendered_request == b'{"exact":true}'
        self.transmissions += 1
        return AnalysisModelResponse(payload={}, call_evidence=self.evidence)


def _running_store(tmp_path) -> SqliteAnalysisRunStore:
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="key-1",
        target=1,
        candidate_ids=("app-1",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker")
    return store


def test_valid_receipt_settles_and_releases_unused_reservation(tmp_path):
    store = _running_store(tmp_path)
    model = PreparedModel(
        AnalysisCallEvidence(
            transmission_state="sent",
            model_id="deepseek-v4-flash",
            request_id="request-1",
            input_tokens=100,
            output_tokens=200,
            cache_hit_input_tokens=0,
        )
    )
    authorized = AuthorizedApplicationAnalysisModel(
        model,
        store=store,
        spend_policy=FixedSpendPolicy(10_000),
        run_id="run-1",
        application_id="app-1",
        lease_owner="worker",
        call_id_factory=lambda: "call-1",
    )

    asyncio.run(authorized.generate(_application()))

    [pending] = store.list_provider_calls("run-1")
    assert pending.state is AnalysisProviderCallState.RESPONSE_RECORDED
    assert pending.result_code == "response_received"

    authorized.settle_last_call(result_code="response_valid")

    [call] = store.list_provider_calls("run-1")
    snapshot = store.get_run("run-1")
    assert call.state is AnalysisProviderCallState.SETTLED
    assert call.result_code == "response_valid"
    assert call.verified_cost_micros == 125
    assert snapshot is not None
    assert snapshot.committed_spend_micros == 125


def test_missing_reported_model_keeps_full_reservation_indeterminate(tmp_path):
    store = _running_store(tmp_path)
    model = PreparedModel(
        AnalysisCallEvidence(
            transmission_state="sent",
            request_id="request-without-provider-model",
            input_tokens=100,
            output_tokens=200,
        )
    )
    authorized = AuthorizedApplicationAnalysisModel(
        model,
        store=store,
        spend_policy=FixedSpendPolicy(10_000, settle=False),
        run_id="run-1",
        application_id="app-1",
        lease_owner="worker",
        call_id_factory=lambda: "call-1",
    )

    asyncio.run(authorized.generate(_application()))
    authorized.settle_last_call(result_code="response_invalid")

    [call] = store.list_provider_calls("run-1")
    snapshot = store.get_run("run-1")
    assert call.state is AnalysisProviderCallState.INDETERMINATE
    assert snapshot is not None
    assert snapshot.indeterminate_reservation_micros == 10_000


def test_over_ceiling_blocks_before_transmission(tmp_path):
    store = _running_store(tmp_path)
    model = PreparedModel(AnalysisCallEvidence(transmission_state="sent"))
    authorized = AuthorizedApplicationAnalysisModel(
        model,
        store=store,
        spend_policy=FixedSpendPolicy(500_001),
        run_id="run-1",
        application_id="app-1",
        lease_owner="worker",
        call_id_factory=lambda: "call-1",
    )

    with pytest.raises(SpendLimitReached) as blocked:
        asyncio.run(authorized.generate(_application()))

    assert blocked.value.code == "spend_limited"
    assert blocked.value.call_evidence.transmission_state == "not_transmitted"
    assert model.transmissions == 0
    assert store.list_provider_calls("run-1") == ()
