from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
import threading

import pytest

import merida_api.features.applications.analysis_run_store as analysis_run_store_module
from merida_api.features.applications.analysis_run_store import (
    ANALYSIS_SPEND_CEILING_MICROS,
    AnalysisCandidateState,
    AnalysisProviderAuthorizationMetadata,
    AnalysisProviderCallState,
    AnalysisProviderSettlementMetadata,
    ApplicationCallBudgetExhaustedError,
    AnalysisRunLifecycle,
    AnalysisRunLeaseError,
    AnalysisRunOutcome,
    AnalysisRunStoreUnavailableError,
    ActiveAnalysisRunError,
    InvalidAnalysisRunTransitionError,
    ProviderDispatchBlockedError,
    SqliteAnalysisRunStore,
    open_analysis_run_store,
)


NOW = datetime(2026, 8, 12, 14, 30, tzinfo=timezone.utc)


class ControlledClock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def _authorization() -> AnalysisProviderAuthorizationMetadata:
    return AnalysisProviderAuthorizationMetadata(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-flash",
        approval_fingerprint="sha256:approval",
        request_fingerprint="sha256:request",
        tokenizer_tokens=120,
        utf8_bytes=400,
        protocol_overhead_tokens=27,
        input_cost_bound_tokens=427,
        max_output_tokens=8_000,
        cache_hit_input_micros_per_million_tokens=2_800,
        cache_miss_input_micros_per_million_tokens=140_000,
        output_micros_per_million_tokens=280_000,
    )


def test_analysis_run_metadata_survives_a_fresh_store_instance(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)

    created = store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=2,
        candidate_ids=("app-alpha", "app-beta", "app-gamma"),
    )
    store.start_run(
        created.run_id,
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.record_candidate_result(
        created.run_id,
        "app-alpha",
        AnalysisCandidateState.ANALYZED,
        lease_owner="worker-1",
    )

    reloaded = SqliteAnalysisRunStore(path, clock=lambda: NOW).get_run("run-1")

    assert reloaded is not None
    assert reloaded.lifecycle is AnalysisRunLifecycle.RUNNING
    assert reloaded.outcome is None
    assert reloaded.target == 2
    assert reloaded.attempt_budget == 3
    assert reloaded.completion_count == 1
    assert reloaded.evaluated_count == 1
    assert reloaded.lease_owner == "worker-1"
    assert reloaded.candidates == (
        reloaded.candidates[0].__class__(
            application_id="app-alpha",
            ordinal=0,
            state=AnalysisCandidateState.ANALYZED,
            reason_code=None,
            completed_at=NOW,
        ),
        reloaded.candidates[0].__class__(
            application_id="app-beta",
            ordinal=1,
            state=AnalysisCandidateState.PENDING,
            reason_code=None,
        ),
        reloaded.candidates[0].__class__(
            application_id="app-gamma",
            ordinal=2,
            state=AnalysisCandidateState.PENDING,
            reason_code=None,
        ),
    )

    finished = store.finish_run(
        "run-1", AnalysisRunOutcome.TARGET_MET, lease_owner="worker-1"
    )

    assert finished.lifecycle is AnalysisRunLifecycle.FINISHED
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert finished.lease_owner is None
    assert finished.finished_at == NOW


def test_provider_call_reservations_are_atomic_under_concurrent_admission(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    first_store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    second_store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    first_store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha", "app-beta"),
    )
    first_store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    first_store.claim_next_candidate("run-1", lease_owner="worker-1")
    barrier = threading.Barrier(2)

    def reserve(store, call_id, call_index):
        barrier.wait()
        return store.reserve_provider_call(
            run_id="run-1",
            application_id="app-alpha",
            call_id=call_id,
            call_index=call_index,
            reservation_micros=300_000,
            authorization=_authorization(),
            lease_owner="worker-1",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        admissions = tuple(
            executor.map(
                lambda arguments: reserve(*arguments),
                (
                        (first_store, "call-alpha", 1),
                        (second_store, "call-beta", 2),
                ),
            )
        )

    assert sum(admission is not None for admission in admissions) == 1
    assert first_store.get_run("run-1").committed_spend_micros == 300_000

    denied = first_store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-over",
        call_index=3,
        reservation_micros=200_001,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    admitted = first_store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-boundary",
        call_index=4,
        reservation_micros=200_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )

    assert denied is None
    assert admitted is not None
    assert admitted.state is AnalysisProviderCallState.RESERVED
    assert admitted.reservation_micros == 200_000
    snapshot = SqliteAnalysisRunStore(path, clock=lambda: NOW).get_run("run-1")
    assert snapshot is not None
    assert snapshot.spend_ceiling_micros == ANALYSIS_SPEND_CEILING_MICROS
    assert snapshot.committed_spend_micros == 500_000
    assert snapshot.active_reservation_micros == 500_000
    assert snapshot.indeterminate_reservation_micros == 0
    assert snapshot.verified_cost_micros == 0
    assert snapshot.remaining_authorized_micros == 0
    assert all(
        call.state is AnalysisProviderCallState.RESERVED
        for call in first_store.list_provider_calls("run-1")
    )


def test_only_one_analysis_run_can_be_active_across_store_instances(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    stores = (
        SqliteAnalysisRunStore(path, clock=lambda: NOW),
        SqliteAnalysisRunStore(path, clock=lambda: NOW),
    )
    barrier = threading.Barrier(2)

    def create(store, suffix):
        barrier.wait()
        try:
            snapshot = store.create_run(
                run_id=f"run-{suffix}",
                idempotency_key=f"start-{suffix}",
                target=1,
                candidate_ids=(f"app-{suffix}",),
            )
        except ActiveAnalysisRunError as error:
            return "conflict", error.active_run_id
        return "created", snapshot.run_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda arguments: create(*arguments),
                ((stores[0], "alpha"), (stores[1], "beta")),
            )
        )

    created_run_id = next(run_id for result, run_id in results if result == "created")
    assert sorted(result for result, _run_id in results) == ["conflict", "created"]
    assert next(run_id for result, run_id in results if result == "conflict") == (
        created_run_id
    )
    assert stores[0].get_active_run().run_id == created_run_id

    stores[0].claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    stores[0].finish_run(
        created_run_id,
        AnalysisRunOutcome.QUEUE_EXHAUSTED,
        lease_owner="worker-1",
    )
    next_run = stores[1].create_run(
        run_id="run-next",
        idempotency_key="start-next",
        target=1,
        candidate_ids=(),
    )

    assert next_run.lifecycle is AnalysisRunLifecycle.QUEUED


def test_provider_call_states_preserve_conservative_spend_categories(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")
    store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-indeterminate",
        call_index=1,
        reservation_micros=200_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )

    store.transition_provider_call(
        "call-indeterminate",
        AnalysisProviderCallState.DISPATCHING,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "call-indeterminate",
        AnalysisProviderCallState.INDETERMINATE,
        lease_owner="worker-1",
    )
    store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-settled",
        call_index=2,
        reservation_micros=250_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "call-settled",
        AnalysisProviderCallState.DISPATCHING,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "call-settled",
        AnalysisProviderCallState.SENT,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "call-settled",
        AnalysisProviderCallState.RESPONSE_RECORDED,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "call-settled",
        AnalysisProviderCallState.SETTLED,
        verified_cost_micros=125_000,
        lease_owner="worker-1",
    )

    snapshot = store.get_run("run-1")

    assert snapshot is not None
    assert snapshot.committed_spend_micros == 325_000
    assert snapshot.active_reservation_micros == 0
    assert snapshot.indeterminate_reservation_micros == 200_000
    assert snapshot.verified_cost_micros == 125_000
    assert snapshot.remaining_authorized_micros == 175_000
    assert tuple(call.state for call in store.list_provider_calls("run-1")) == (
        AnalysisProviderCallState.INDETERMINATE,
        AnalysisProviderCallState.SETTLED,
    )


def test_unavailable_store_fails_closed_before_provider_authorization(tmp_path):
    invalid_path = tmp_path / "not-a-database"
    invalid_path.mkdir()

    store = open_analysis_run_store(invalid_path, clock=lambda: NOW)

    assert store.available is False
    assert store.transactional is False
    assert store.error == "Analysis Run coordination is unavailable."
    with pytest.raises(
        AnalysisRunStoreUnavailableError,
        match="Analysis Run coordination is unavailable",
    ):
        store.reserve_provider_call(
            run_id="run-1",
            application_id="app-alpha",
            call_id="call-1",
            call_index=1,
            reservation_micros=1,
            authorization=_authorization(),
            lease_owner="worker-1",
        )


def test_analysis_run_ledger_rejects_private_content_and_has_only_safe_columns(
    tmp_path,
):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    private_content = "Full Job Content: secret Python requirements and prompt text"
    store.create_run(
        run_id="run-1",
        idempotency_key=private_content,
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )

    with pytest.raises(ValueError, match="safe reason code"):
        store.record_candidate_result(
            "run-1",
            "app-alpha",
            AnalysisCandidateState.FAILED,
            reason_code=private_content,
            lease_owner="worker-1",
        )
    store.record_candidate_result(
        "run-1",
        "app-alpha",
        AnalysisCandidateState.FAILED,
        reason_code="source_unreadable",
        lease_owner="worker-1",
    )

    with sqlite3.connect(path) as connection:
        schema = "\n".join(
            row[0]
            for row in connection.execute(
                "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL"
            )
        ).lower()
    database_bytes = path.read_bytes()

    assert private_content.encode() not in database_bytes
    for forbidden_column in (
        "job_content",
        "master_resume",
        "prompt",
        "provider_request_payload",
        "provider_response_payload",
        "generated_analysis",
        "model_reasoning",
    ):
        assert forbidden_column not in schema


def test_recovery_claim_never_reclaims_a_healthy_lease_for_any_owner(tmp_path):
    clock = ControlledClock()
    path = tmp_path / "analysis-runs.sqlite3"
    first_store = SqliteAnalysisRunStore(path, clock=clock)
    second_store = SqliteAnalysisRunStore(path, clock=clock)
    first_store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )

    claimed = first_store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    replayed = first_store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(AnalysisRunLeaseError, match="owned by another worker"):
        second_store.start_run(
            "run-1",
            lease_owner="worker-2",
            lease_expires_at=NOW + timedelta(minutes=2),
        )
    competing = second_store.claim_recoverable_run(
        lease_owner="worker-2",
        lease_expires_at=NOW + timedelta(minutes=2),
    )

    assert claimed is not None
    assert claimed.lifecycle is AnalysisRunLifecycle.RUNNING
    assert replayed is None
    assert competing is None
    assert second_store.list_recoverable_runs() == ()

    clock.now = NOW + timedelta(minutes=3)
    assert tuple(run.run_id for run in second_store.list_recoverable_runs()) == (
        "run-1",
    )
    reclaimed = second_store.claim_recoverable_run(
        lease_owner="worker-2",
        lease_expires_at=clock.now + timedelta(minutes=1),
    )

    assert reclaimed is not None
    assert reclaimed.run_id == "run-1"
    assert reclaimed.lease_owner == "worker-2"
    assert reclaimed.started_at == NOW


def test_only_the_lease_owner_can_renew_an_active_run(tmp_path):
    clock = ControlledClock()
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    clock.now = NOW + timedelta(seconds=30)

    renewed = store.renew_lease(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=2),
    )

    assert renewed.lease_owner == "worker-1"
    assert renewed.lease_expires_at == NOW + timedelta(minutes=2)
    assert renewed.updated_at == clock.now
    with pytest.raises(AnalysisRunLeaseError, match="owned by another worker"):
        store.renew_lease(
            "run-1",
            lease_owner="worker-2",
            lease_expires_at=NOW + timedelta(minutes=3),
        )


def test_an_expired_lease_cannot_be_resurrected_by_its_previous_owner(tmp_path):
    clock = ControlledClock()
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(seconds=1),
    )
    clock.now = NOW + timedelta(seconds=2)

    with pytest.raises(AnalysisRunLeaseError, match="expired"):
        store.renew_lease(
            "run-1",
            lease_owner="worker-1",
            lease_expires_at=clock.now + timedelta(minutes=1),
        )


def test_remote_commit_protection_cannot_be_shortened_by_normal_heartbeats(
    tmp_path,
):
    clock = ControlledClock()
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
    )

    protected = store.protect_remote_commit(
        "run-1",
        lease_owner="worker-1",
        minimum_duration=timedelta(minutes=2),
    )
    clock.now = NOW + timedelta(seconds=10)
    same_worker_reclaim = store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=clock.now + timedelta(seconds=30),
    )
    heartbeat = store.renew_lease(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=clock.now + timedelta(seconds=30),
    )
    clock.now = NOW + timedelta(seconds=31)
    competing = store.claim_recoverable_run(
        lease_owner="worker-2",
        lease_expires_at=clock.now + timedelta(seconds=30),
    )

    assert protected.lease_expires_at == NOW + timedelta(minutes=2)
    assert same_worker_reclaim is None
    assert heartbeat.lease_expires_at == protected.lease_expires_at
    assert competing is None


def test_candidate_claim_is_ordered_idempotent_and_never_evaluates_twice(tmp_path):
    clock = ControlledClock()
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=clock)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha", "app-beta"),
    )
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )

    first = store.claim_next_candidate("run-1", lease_owner="worker-1")
    clock.now = NOW + timedelta(seconds=10)
    replayed = SqliteAnalysisRunStore(path, clock=clock).claim_next_candidate(
        "run-1", lease_owner="worker-1"
    )

    assert first is not None
    assert replayed == first
    assert first.application_id == "app-alpha"
    assert first.state is AnalysisCandidateState.EVALUATING
    assert first.started_at == NOW
    assert first.completed_at is None

    store.record_candidate_result(
        "run-1", "app-alpha", AnalysisCandidateState.FAILED,
        reason_code="invalid_output",
        lease_owner="worker-1",
    )
    second = store.claim_next_candidate("run-1", lease_owner="worker-1")

    assert second is not None
    assert second.application_id == "app-beta"
    assert second.started_at == clock.now
    snapshot = store.get_run("run-1")
    assert snapshot.candidates[0].completed_at == clock.now
    assert snapshot.candidates[0].started_at == NOW


def test_cancellation_is_durable_idempotent_and_blocks_new_candidate_work(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )

    requested = store.request_cancellation("run-1")
    replayed = store.request_cancellation("run-1")

    assert requested.lifecycle is AnalysisRunLifecycle.CANCELLING
    assert replayed == requested
    assert requested.outcome is None
    assert requested.reason_code is None
    claimed = store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    assert claimed is not None
    assert claimed.lifecycle is AnalysisRunLifecycle.CANCELLING
    assert store.claim_next_candidate("run-1", lease_owner="worker-1") is None
    with pytest.raises(ValueError, match="safe reason code"):
        store.finish_run(
            "run-1",
            AnalysisRunOutcome.CANCELLED,
            reason_code="Job Content and model reasoning must stay private",
            lease_owner="worker-1",
        )

    finished = store.finish_run(
        "run-1",
        AnalysisRunOutcome.CANCELLED,
        reason_code="operator_cancelled",
        lease_owner="worker-1",
    )

    assert finished.lifecycle is AnalysisRunLifecycle.FINISHED
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.reason_code == "operator_cancelled"
    assert store.request_cancellation("run-1") == finished
    assert store.list_recoverable_runs() == ()
    with pytest.raises(
        InvalidAnalysisRunTransitionError,
        match="reason cannot be replaced",
    ):
        store.finish_run(
            "run-1",
            AnalysisRunOutcome.CANCELLED,
            reason_code="different_reason",
            lease_owner="worker-1",
        )


def test_cancellation_atomically_wins_a_racing_non_cancel_finish(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.request_cancellation("run-1")
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )

    finished = store.finish_run(
        "run-1",
        AnalysisRunOutcome.TARGET_MET,
        reason_code="target_met",
        lease_owner="worker-1",
    )

    assert finished.lifecycle is AnalysisRunLifecycle.FINISHED
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.reason_code == "cancelled"


def test_reclaimed_lease_fences_stale_worker_mutations(tmp_path):
    class ControlledClock:
        def __init__(self):
            self.now = NOW

        def __call__(self):
            return self.now

    clock = ControlledClock()
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.claim_recoverable_run(
        lease_owner="old-worker",
        lease_expires_at=NOW + timedelta(seconds=1),
    )
    store.claim_next_candidate("run-1", lease_owner="old-worker")
    clock.now = NOW + timedelta(seconds=2)
    store.claim_recoverable_run(
        lease_owner="new-worker",
        lease_expires_at=clock.now + timedelta(minutes=1),
    )

    with pytest.raises(AnalysisRunLeaseError):
        store.reserve_provider_call(
            run_id="run-1",
            application_id="app-alpha",
            call_id="stale-call",
            call_index=1,
            reservation_micros=100,
            authorization=_authorization(),
            lease_owner="old-worker",
        )
    with pytest.raises(AnalysisRunLeaseError):
        store.record_candidate_result(
            "run-1",
            "app-alpha",
            AnalysisCandidateState.FAILED,
            reason_code="stale_worker",
            lease_owner="old-worker",
        )
    with pytest.raises(AnalysisRunLeaseError):
        store.finish_run(
            "run-1",
            AnalysisRunOutcome.FAILED,
            reason_code="stale_worker",
            lease_owner="old-worker",
        )

    reserved = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="new-call",
        call_index=1,
        reservation_micros=100,
        authorization=_authorization(),
        lease_owner="new-worker",
    )
    assert reserved is not None
    with pytest.raises(AnalysisRunLeaseError):
        store.begin_provider_dispatch(
            reserved.call_id, lease_owner="old-worker"
        )
    dispatched = store.begin_provider_dispatch(
        reserved.call_id, lease_owner="new-worker"
    )
    assert dispatched.state is AnalysisProviderCallState.DISPATCHING


def test_reclaimed_lease_fences_an_idempotent_dispatch_replay(tmp_path):
    clock = ControlledClock()
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.claim_recoverable_run(
        lease_owner="old-worker",
        lease_expires_at=NOW + timedelta(seconds=1),
    )
    store.claim_next_candidate("run-1", lease_owner="old-worker")
    reserved = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-1",
        call_index=1,
        reservation_micros=100,
        authorization=_authorization(),
        lease_owner="old-worker",
    )
    dispatched = store.begin_provider_dispatch(
        reserved.call_id, lease_owner="old-worker"
    )
    assert dispatched.state is AnalysisProviderCallState.DISPATCHING

    clock.now = NOW + timedelta(seconds=2)
    store.claim_recoverable_run(
        lease_owner="new-worker",
        lease_expires_at=clock.now + timedelta(minutes=1),
    )

    with pytest.raises(AnalysisRunLeaseError):
        store.begin_provider_dispatch(
            dispatched.call_id, lease_owner="old-worker"
        )


def test_recovery_releases_only_unsent_calls_and_keeps_uncertain_spend(tmp_path):
    expected = {
        AnalysisProviderCallState.RESERVED: AnalysisProviderCallState.RELEASED,
        AnalysisProviderCallState.DISPATCHING: AnalysisProviderCallState.INDETERMINATE,
        AnalysisProviderCallState.SENT: AnalysisProviderCallState.INDETERMINATE,
        AnalysisProviderCallState.RESPONSE_RECORDED: (
            AnalysisProviderCallState.RESPONSE_RECORDED
        ),
    }
    stores = {}

    for starting_state, recovered_state in expected.items():
        store = SqliteAnalysisRunStore(
            tmp_path / starting_state.value / "analysis-runs.sqlite3",
            clock=lambda: NOW,
        )
        run_id = f"run-{starting_state.value}"
        call_id = f"call-{starting_state.value}"
        store.create_run(
            run_id=run_id,
            idempotency_key=f"start-{starting_state.value}",
            target=1,
            candidate_ids=("app-alpha",),
        )
        store.start_run(
            run_id,
            lease_owner="worker-1",
            lease_expires_at=NOW + timedelta(minutes=1),
        )
        store.claim_next_candidate(run_id, lease_owner="worker-1")
        store.reserve_provider_call(
            run_id=run_id,
            application_id="app-alpha",
            call_id=call_id,
            call_index=1,
            reservation_micros=100_000,
            authorization=_authorization(),
            lease_owner="worker-1",
        )
        if starting_state is not AnalysisProviderCallState.RESERVED:
            store.begin_provider_dispatch(call_id, lease_owner="worker-1")
        if starting_state in {
            AnalysisProviderCallState.SENT,
            AnalysisProviderCallState.RESPONSE_RECORDED,
        }:
            store.transition_provider_call(
                call_id,
                AnalysisProviderCallState.SENT,
                lease_owner="worker-1",
            )
        if starting_state is AnalysisProviderCallState.RESPONSE_RECORDED:
            store.transition_provider_call(
                call_id,
                AnalysisProviderCallState.RESPONSE_RECORDED,
                lease_owner="worker-1",
            )

        [reconciled] = store.reconcile_interrupted_provider_calls(
            run_id, lease_owner="worker-1"
        )
        [replayed] = store.reconcile_interrupted_provider_calls(
            run_id, lease_owner="worker-1"
        )

        assert reconciled.state is recovered_state
        assert replayed.state is recovered_state
        if recovered_state is AnalysisProviderCallState.RELEASED:
            assert reconciled.transmission_index is None
        snapshot = store.get_run(run_id)
        assert snapshot is not None
        assert snapshot.committed_spend_micros == (
            0 if recovered_state is AnalysisProviderCallState.RELEASED else 100_000
        )
        stores[starting_state] = (store, call_id, run_id)

    reserved_store, reserved_call, _run_id = stores[AnalysisProviderCallState.RESERVED]
    assert reserved_store.release_provider_call(
        reserved_call, lease_owner="worker-1"
    ).state is (
        AnalysisProviderCallState.RELEASED
    )
    sent_store, sent_call, _run_id = stores[AnalysisProviderCallState.SENT]
    with pytest.raises(
        InvalidAnalysisRunTransitionError,
        match="sent provider call",
    ):
        sent_store.release_provider_call(
            sent_call, lease_owner="worker-1"
        )
    response_store, response_call, response_run = stores[
        AnalysisProviderCallState.RESPONSE_RECORDED
    ]
    settled = response_store.settle_provider_call(
        response_call,
        verified_cost_micros=40_000,
        lease_owner="worker-1",
    )

    assert settled.state is AnalysisProviderCallState.SETTLED
    settled_snapshot = response_store.get_run(response_run)
    assert settled_snapshot.committed_spend_micros == 40_000
    assert settled_snapshot.verified_cost_micros == 40_000
    assert settled_snapshot.indeterminate_reservation_micros == 0


def test_run_cannot_finish_while_provider_call_is_active(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-active-call",
        idempotency_key="start-active-call",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-active-call",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-active-call", lease_owner="worker-1")
    store.reserve_provider_call(
        run_id="run-active-call",
        application_id="app-alpha",
        call_id="call-active",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )

    with pytest.raises(
        InvalidAnalysisRunTransitionError,
        match="active provider call",
    ):
        store.finish_run(
            "run-active-call",
            AnalysisRunOutcome.FAILED,
            lease_owner="worker-1",
        )

    assert store.get_run("run-active-call").lifecycle is (
        AnalysisRunLifecycle.RUNNING
    )


def test_run_scoped_candidate_result_finishes_atomically_before_next_candidate(
    tmp_path,
):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-atomic-stop",
        idempotency_key="start-atomic-stop",
        target=1,
        candidate_ids=("app-alpha", "app-beta"),
    )
    store.start_run(
        "run-atomic-stop",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-atomic-stop", lease_owner="worker-1")

    finished = store.record_candidate_result(
        "run-atomic-stop",
        "app-alpha",
        AnalysisCandidateState.FAILED,
        reason_code="authentication_failed",
        stop_outcome=AnalysisRunOutcome.AUTHORIZATION_BLOCKED,
        stop_reason_code="authentication_failed",
        lease_owner="worker-1",
    )

    assert finished.lifecycle is AnalysisRunLifecycle.FINISHED
    assert finished.outcome is AnalysisRunOutcome.AUTHORIZATION_BLOCKED
    assert finished.reason_code == "authentication_failed"
    assert finished.candidates[0].state is AnalysisCandidateState.FAILED
    assert finished.candidates[1].state is AnalysisCandidateState.PENDING
    assert store.claim_recoverable_run(
        lease_owner="worker-2",
        lease_expires_at=NOW + timedelta(minutes=2),
    ) is None


def test_run_reason_is_safe_stable_and_preserved_when_the_run_finishes(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=(),
    )
    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )

    recorded = store.record_run_reason(
        "run-1", "provider_unavailable", lease_owner="worker-1"
    )
    replayed = store.record_run_reason(
        "run-1", "provider_unavailable", lease_owner="worker-1"
    )

    assert recorded.reason_code == "provider_unavailable"
    assert replayed == recorded
    with pytest.raises(
        InvalidAnalysisRunTransitionError,
        match="reason cannot be replaced",
    ):
        store.record_run_reason(
            "run-1", "different_reason", lease_owner="worker-1"
        )

    finished = store.finish_run(
        "run-1", AnalysisRunOutcome.FAILED, lease_owner="worker-1"
    )

    assert finished.reason_code == "provider_unavailable"
    assert (
        store.finish_run(
            "run-1", AnalysisRunOutcome.FAILED, lease_owner="worker-1"
        )
        == finished
    )


def test_schema_v1_store_is_migrated_without_losing_observable_run_data(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")
    store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="call-released",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    store.begin_provider_dispatch(
        "call-released", lease_owner="worker-1"
    )
    store.release_provider_call(
        "call-released", lease_owner="worker-1"
    )
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            ALTER TABLE analysis_provider_calls
                RENAME TO analysis_provider_calls_v4;
            CREATE TABLE analysis_provider_calls (
                call_id TEXT PRIMARY KEY NOT NULL,
                run_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                call_index INTEGER NOT NULL,
                state TEXT NOT NULL,
                reservation_micros INTEGER NOT NULL,
                verified_cost_micros INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id, application_id)
                    REFERENCES analysis_run_candidates(run_id, application_id)
                    ON DELETE CASCADE,
                UNIQUE (run_id, application_id, call_index)
            );
            INSERT INTO analysis_provider_calls (
                call_id,
                run_id,
                application_id,
                call_index,
                state,
                reservation_micros,
                verified_cost_micros,
                created_at,
                updated_at
            )
            SELECT
                call_id,
                run_id,
                application_id,
                authorization_index,
                state,
                reservation_micros,
                verified_cost_micros,
                created_at,
                updated_at
            FROM analysis_provider_calls_v4;
            DROP TABLE analysis_provider_calls_v4;
            """
        )
        connection.execute("ALTER TABLE analysis_runs DROP COLUMN reason_code")
        connection.execute(
            "ALTER TABLE analysis_runs DROP COLUMN candidate_set_truncated"
        )
        connection.execute(
            "UPDATE analysis_runs SET idempotency_key = 'start-1'"
        )
        connection.execute("PRAGMA user_version = 1")

    migrated = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    snapshot = migrated.get_run("run-1")

    assert snapshot is not None
    assert snapshot.run_id == "run-1"
    assert snapshot.reason_code is None
    assert snapshot.candidate_set_truncated is False
    assert snapshot.candidates[0].application_id == "app-alpha"
    assert migrated.get_by_idempotency_key("start-1") == snapshot
    [call] = migrated.list_provider_calls("run-1")
    assert call.authorization_index == 1
    assert call.transmission_index is None
    assert call.state is AnalysisProviderCallState.RELEASED
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 7


@pytest.mark.parametrize("replacement_created", [False, True])
def test_interrupted_provider_call_rebuild_recovers_authoritative_paid_rows(
    tmp_path, replacement_created
):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")
    call = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="paid-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    assert call is not None
    store.begin_provider_dispatch("paid-call", lease_owner="worker-1")
    store.transition_provider_call(
        "paid-call",
        AnalysisProviderCallState.SENT,
        lease_owner="worker-1",
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "ALTER TABLE analysis_provider_calls "
            "RENAME TO analysis_provider_calls_v2"
        )
        if replacement_created:
            connection.execute(
                "CREATE TABLE analysis_provider_calls AS "
                "SELECT * FROM analysis_provider_calls_v2 WHERE 0"
            )

    recovered_store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    [recovered_call] = recovered_store.list_provider_calls("run-1")
    snapshot = recovered_store.get_run("run-1")

    assert recovered_call.call_id == "paid-call"
    assert recovered_call.state is AnalysisProviderCallState.SENT
    assert recovered_call.reservation_micros == 10_000
    assert snapshot is not None
    assert snapshot.committed_spend_micros == 10_000
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "analysis_provider_calls" in tables
    assert "analysis_provider_calls_v2" not in tables


@pytest.mark.parametrize("newer_transmission_index", [2, 1])
def test_interrupted_rebuild_never_discards_paid_rows_from_either_table(
    tmp_path, newer_transmission_index
):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-alpha",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")
    old_call = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-alpha",
        call_id="old-paid-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    assert old_call is not None
    store.begin_provider_dispatch("old-paid-call", lease_owner="worker-1")
    store.transition_provider_call(
        "old-paid-call",
        AnalysisProviderCallState.SENT,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        "old-paid-call",
        AnalysisProviderCallState.INDETERMINATE,
        lease_owner="worker-1",
    )

    with sqlite3.connect(path) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'analysis_provider_calls'"
        ).fetchone()[0]
        connection.execute(
            "ALTER TABLE analysis_provider_calls "
            "RENAME TO analysis_provider_calls_v2"
        )
        connection.execute(table_sql)
        connection.execute(
            """
            INSERT INTO analysis_provider_calls (
                call_id,
                run_id,
                application_id,
                authorization_index,
                transmission_index,
                state,
                reservation_micros,
                verified_cost_micros,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "newer-paid-call",
                "run-1",
                "app-alpha",
                2,
                newer_transmission_index,
                "sent",
                20_000,
                None,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

    recovered = open_analysis_run_store(path, clock=lambda: NOW)

    if newer_transmission_index == 2:
        assert recovered.available is True
        assert {
            call.call_id for call in recovered.list_provider_calls("run-1")
        } == {"old-paid-call", "newer-paid-call"}
        snapshot = recovered.get_run("run-1")
        assert snapshot is not None
        assert snapshot.committed_spend_micros == 30_000
        return

    assert recovered.available is False
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM analysis_provider_calls"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM analysis_provider_calls_v2"
        ).fetchone()[0] == 1


def test_schema_migration_and_version_bump_roll_back_together(
    tmp_path, monkeypatch
):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=(),
    )
    with sqlite3.connect(path) as connection:
        original_key = connection.execute(
            "SELECT idempotency_key FROM analysis_runs WHERE run_id = 'run-1'"
        ).fetchone()[0]
        connection.execute("PRAGMA user_version = 1")

    def interrupt_migration(connection, _script):
        connection.execute("CREATE TABLE interrupted_migration(value TEXT)")
        connection.execute(
            "UPDATE analysis_runs SET idempotency_key = 'partial-write'"
        )
        raise RuntimeError("simulated process interruption")

    monkeypatch.setattr(
        analysis_run_store_module,
        "_execute_sql_script",
        interrupt_migration,
    )
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        SqliteAnalysisRunStore(path, clock=lambda: NOW)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute(
            "SELECT idempotency_key FROM analysis_runs WHERE run_id = 'run-1'"
        ).fetchone()[0] == original_key
        assert connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'interrupted_migration'"
        ).fetchone() is None


def test_interrupted_idempotency_hash_migration_is_not_double_hashed(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    expected = store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=(),
    )
    with sqlite3.connect(path) as connection:
        digest_before_restart = connection.execute(
            "SELECT idempotency_key FROM analysis_runs WHERE run_id = 'run-1'"
        ).fetchone()[0]
        connection.execute("PRAGMA user_version = 1")

    recovered = SqliteAnalysisRunStore(path, clock=lambda: NOW)

    assert recovered.get_by_idempotency_key("start-1") == expected
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT idempotency_key FROM analysis_runs WHERE run_id = 'run-1'"
        ).fetchone()[0] == digest_before_restart


def test_run_persists_whether_the_fixed_candidate_set_was_truncated(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)

    created = store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=2,
        candidate_ids=("app-1", "app-2", "app-3", "app-4"),
        candidate_set_truncated=True,
    )
    reloaded = SqliteAnalysisRunStore(path, clock=lambda: NOW).get_run("run-1")

    assert created.candidate_set_truncated is True
    assert reloaded is not None
    assert reloaded.candidate_set_truncated is True

    store.claim_recoverable_run(
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.finish_run(
        "run-1",
        AnalysisRunOutcome.ATTEMPT_BUDGET_EXHAUSTED,
        lease_owner="worker-1",
    )
    complete_set = store.create_run(
        run_id="run-2",
        idempotency_key="start-2",
        target=2,
        candidate_ids=("app-5", "app-6"),
    )

    assert complete_set.candidate_set_truncated is False


def test_worker_can_relinquish_its_lease_for_immediate_restart_recovery(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-1",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=5),
    )

    relinquished = store.relinquish_lease("run-1", lease_owner="worker-1")
    reclaimed = store.claim_recoverable_run(
        lease_owner="worker-2",
        lease_expires_at=NOW + timedelta(minutes=1),
    )

    assert relinquished.lease_owner is None
    assert relinquished.lease_expires_at is None
    assert reclaimed is not None
    assert reclaimed.run_id == "run-1"
    assert reclaimed.lease_owner == "worker-2"


def test_released_authorization_reuses_slot_but_no_fourth_transmission_exists(
    tmp_path,
):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-1",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")

    released = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-1",
        call_id="authorization-1",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    assert released is not None
    dispatching = store.transition_provider_call(
        released.call_id,
        AnalysisProviderCallState.DISPATCHING,
        lease_owner="worker-1",
    )
    assert dispatching.transmission_index == 1
    released = store.release_provider_call(
        released.call_id, lease_owner="worker-1"
    )
    assert released.state is AnalysisProviderCallState.RELEASED
    assert released.transmission_index is None

    for authorization_index in (2, 3, 4):
        call = store.reserve_provider_call(
            run_id="run-1",
            application_id="app-1",
            call_id=f"authorization-{authorization_index}",
            call_index=authorization_index,
            reservation_micros=10_000,
            authorization=_authorization(),
            lease_owner="worker-1",
        )
        assert call is not None
        call = store.transition_provider_call(
            call.call_id,
            AnalysisProviderCallState.DISPATCHING,
            lease_owner="worker-1",
        )
        assert call.transmission_index == authorization_index - 1
        store.transition_provider_call(
            call.call_id,
            AnalysisProviderCallState.SENT,
            lease_owner="worker-1",
        )
        store.transition_provider_call(
            call.call_id,
            AnalysisProviderCallState.INDETERMINATE,
            lease_owner="worker-1",
        )

    with pytest.raises(
        ApplicationCallBudgetExhaustedError,
        match="three provider transmissions",
    ):
        store.reserve_provider_call(
            run_id="run-1",
            application_id="app-1",
            call_id="authorization-5",
            call_index=5,
            reservation_micros=10_000,
            authorization=_authorization(),
            lease_owner="worker-1",
        )

    calls = store.list_provider_calls("run-1")
    assert tuple(call.authorization_index for call in calls) == (1, 2, 3, 4)
    assert tuple(call.transmission_index for call in calls) == (None, 1, 2, 3)
    assert sum(call.transmission_index is not None for call in calls) == 3
    assert store.get_run("run-1").committed_spend_micros == 30_000


def test_safe_authorization_and_settlement_metadata_survive_restart(tmp_path):
    path = tmp_path / "analysis-runs.sqlite3"
    store = SqliteAnalysisRunStore(path, clock=lambda: NOW)
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-1",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    store.claim_next_candidate("run-1", lease_owner="worker-1")
    authorization = AnalysisProviderAuthorizationMetadata(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-flash",
        approval_fingerprint="sha256:approval",
        request_fingerprint="sha256:request",
        tokenizer_tokens=120,
        utf8_bytes=400,
        protocol_overhead_tokens=12,
        input_cost_bound_tokens=412,
        max_output_tokens=8_000,
        cache_hit_input_micros_per_million_tokens=28_000,
        cache_miss_input_micros_per_million_tokens=140_000,
        output_micros_per_million_tokens=280_000,
    )
    reserved = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-1",
        call_id="authorization-1",
        call_index=1,
        reservation_micros=250_000,
        authorization=authorization,
        lease_owner="worker-1",
    )
    assert reserved is not None
    store.transition_provider_call(
        reserved.call_id,
        AnalysisProviderCallState.DISPATCHING,
        lease_owner="worker-1",
    )
    store.transition_provider_call(
        reserved.call_id,
        AnalysisProviderCallState.SENT,
        lease_owner="worker-1",
    )
    recorded = store.record_provider_call_response(
        reserved.call_id,
        AnalysisProviderSettlementMetadata(
            provider_request_id="request-123",
            input_tokens=100,
            output_tokens=200,
            cache_hit_input_tokens=25,
            cache_miss_input_tokens=75,
            total_tokens=300,
            reasoning_output_tokens=125,
            finish_reason="stop",
            result_code="usage_recorded",
        ),
        lease_owner="worker-1",
    )

    reloaded = SqliteAnalysisRunStore(path, clock=lambda: NOW).list_provider_calls(
        "run-1"
    )[0]

    assert recorded.state is AnalysisProviderCallState.RESPONSE_RECORDED
    assert reloaded.endpoint == authorization.endpoint
    assert reloaded.model == authorization.model
    assert reloaded.approval_fingerprint == "sha256:approval"
    assert reloaded.request_fingerprint == "sha256:request"
    assert reloaded.input_cost_bound_tokens == 412
    assert reloaded.max_output_tokens == 8_000
    assert reloaded.cache_miss_input_micros_per_million_tokens == 140_000
    assert reloaded.output_micros_per_million_tokens == 280_000
    assert reloaded.provider_request_id == "request-123"
    assert reloaded.input_tokens == 100
    assert reloaded.output_tokens == 200
    assert reloaded.cache_hit_input_tokens == 25
    assert reloaded.finish_reason == "stop"
    assert reloaded.result_code == "usage_recorded"

    private_content = "Full Job Content with private requirements"
    with pytest.raises(ValueError, match="safe model identity"):
        AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model=private_content,
            approval_fingerprint="approval",
            request_fingerprint="request",
            tokenizer_tokens=1,
            utf8_bytes=1,
            protocol_overhead_tokens=0,
            input_cost_bound_tokens=1,
            max_output_tokens=1,
            cache_hit_input_micros_per_million_tokens=1,
            cache_miss_input_micros_per_million_tokens=1,
            output_micros_per_million_tokens=1,
        )
    assert private_content.encode() not in path.read_bytes()


def test_dispatch_revalidates_run_candidate_and_single_flight_atomically(tmp_path):
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=lambda: NOW
    )
    store.create_run(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidate_ids=("app-1",),
    )
    store.start_run(
        "run-1",
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=1),
    )
    first = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-1",
        call_id="authorization-1",
        call_index=1,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    assert first is not None

    with pytest.raises(ProviderDispatchBlockedError, match="candidate to be evaluating"):
        store.begin_provider_dispatch(
            first.call_id, lease_owner="worker-1"
        )

    store.claim_next_candidate("run-1", lease_owner="worker-1")
    dispatched = store.begin_provider_dispatch(
        first.call_id, lease_owner="worker-1"
    )
    assert dispatched.state is AnalysisProviderCallState.DISPATCHING
    second = store.reserve_provider_call(
        run_id="run-1",
        application_id="app-1",
        call_id="authorization-2",
        call_index=2,
        reservation_micros=10_000,
        authorization=_authorization(),
        lease_owner="worker-1",
    )
    assert second is not None
    with pytest.raises(ProviderDispatchBlockedError, match="already in flight"):
        store.begin_provider_dispatch(
            second.call_id, lease_owner="worker-1"
        )

    store.release_provider_call(first.call_id, lease_owner="worker-1")
    store.request_cancellation("run-1")
    with pytest.raises(AnalysisRunLeaseError, match="outside its leased"):
        store.begin_provider_dispatch(
            second.call_id, lease_owner="worker-1"
        )

    unchanged = store.list_provider_calls("run-1")[1]
    assert unchanged.state is AnalysisProviderCallState.RESERVED
    assert unchanged.transmission_index is None
