from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace as dataclass_replace
from datetime import date, datetime, timedelta, timezone

import pytest

from merida_api.features.applications.analysis_run_store import (
    ActiveAnalysisRunError,
    AnalysisCandidateState,
    AnalysisProviderAuthorizationMetadata,
    AnalysisProviderCallState,
    AnalysisProviderSettlementMetadata,
    AnalysisRunLifecycle,
    AnalysisRunLeaseError,
    AnalysisRunOutcome,
    AnalysisRunStoreError,
    SqliteAnalysisRunStore,
)
from merida_api.features.applications.analysis_runs import (
    AnalysisCandidateEvaluation,
    AnalysisRunService,
    AnalysisRunWorker,
    GraphAnalysisCandidateEvaluator,
)
from merida_api.features.applications.analysis_spend import (
    AnalysisCostEstimate,
    AnalysisSettlement,
)
from merida_api.features.applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
    PersistedSkillSignal,
)
from merida_api.matching import EvidenceItem
from merida_api.shared.workspace import (
    QueuePage,
    WorkspaceCommitUnknownError,
    WorkspaceProviderError,
    WorkspaceReadiness,
)
from fakes.models import FakeApplicationAnalysisModel
from fakes.workspace import FakeWorkspace


def _application(index: int) -> ApplicationRecord:
    return ApplicationRecord(
        id=f"app-{index}",
        url=f"https://notion.test/app-{index}",
        company_name=f"Company {index}",
        role="Engineer",
        job_url=f"https://jobs.test/{index}",
        captured_url=None,
        location=None,
        date_found=date(2026, 1, index),
        application_status="To Apply",
        analyzed=False,
        match_score=None,
        job_content="Build Python services, REST APIs, and automated tests.",
    )


class QueueWorkspace:
    def __init__(self, applications: list[ApplicationRecord]):
        self.applications = applications

    async def validate_analysis_workspace(self) -> WorkspaceReadiness:
        return WorkspaceReadiness()

    async def list_analysis_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage[ApplicationRecord]:
        assert cursor is None
        selected = tuple(self.applications[:limit])
        return QueuePage(
            items=selected,
            total=len(self.applications),
            limit=limit,
            next_cursor=None,
            has_more=len(self.applications) > limit,
        )

    async def load_analysis_queue_snapshot(
        self, *, excluded_application_ids=frozenset()
    ):
        return tuple(
            item
            for item in self.applications
            if item.id not in excluded_application_ids
        )


@dataclass
class RecordedEvaluator:
    results: dict[str, AnalysisCandidateEvaluation]

    def __post_init__(self):
        self.application_ids: list[str] = []

    async def evaluate(
        self, run_id: str, application_id: str, *, lease_owner: str
    ) -> AnalysisCandidateEvaluation:
        assert run_id.startswith("analysis-run-")
        assert lease_owner
        self.application_ids.append(application_id)
        return self.results[application_id]


def test_worker_rechecks_recoverable_runs_after_initial_healthy_lease():
    class EventuallyRecoverableService:
        def __init__(self):
            self.calls = 0
            self.rechecked = asyncio.Event()

        async def process_next_run(self):
            self.calls += 1
            if self.calls >= 2:
                self.rechecked.set()
            return None

    async def exercise():
        service = EventuallyRecoverableService()
        worker = AnalysisRunWorker(service, recovery_poll_seconds=0.01)
        worker.start()
        await asyncio.wait_for(service.rechecked.wait(), timeout=0.2)
        await worker.stop()
        return service.calls

    assert asyncio.run(exercise()) >= 2


def test_worker_shutdown_cancels_inflight_evaluation_without_shortening_lease(
    tmp_path,
):
    class ControlledClock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class BlockingEvaluator:
        def __init__(self, store):
            self.store = store
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def evaluate(self, run_id, _application_id, *, lease_owner):
            assert lease_owner
            self.store.protect_remote_commit(
                run_id,
                lease_owner=lease_owner,
                minimum_duration=timedelta(minutes=2),
            )
            self.started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()

    async def exercise():
        clock = ControlledClock()
        path = tmp_path / "analysis-runs.sqlite3"
        store = SqliteAnalysisRunStore(
            path, clock=clock
        )
        evaluator = BlockingEvaluator(store)
        service = AnalysisRunService(
            workspace=QueueWorkspace([_application(1)]),
            store=store,
            evaluator=evaluator,
            clock=clock,
            worker_id="shutdown-worker",
        )
        run = await service.start(target=1, idempotency_key="shutdown-start")
        worker = AnalysisRunWorker(service)
        worker.start()
        await asyncio.wait_for(evaluator.started.wait(), timeout=0.2)

        # Only 29 seconds remain on the protected two-minute lease. This is
        # deliberately less than the normal 30-second worker lease.
        clock.now += timedelta(seconds=91)
        await worker.stop()

        snapshot = store.get_run(run.run_id)
        replacement = SqliteAnalysisRunStore(path, clock=clock)
        competing = replacement.claim_recoverable_run(
            lease_owner="replacement-worker",
            lease_expires_at=clock.now + timedelta(seconds=30),
        )
        assert evaluator.cancelled.is_set()
        assert snapshot is not None
        assert snapshot.lease_owner == "shutdown-worker"
        assert snapshot.lease_expires_at == datetime(
            2026, 8, 12, 0, 2, tzinfo=timezone.utc
        )
        assert competing is None

    asyncio.run(exercise())


def test_lease_renewal_failure_cancels_inflight_evaluation(tmp_path):
    class LeaseFailingStore(SqliteAnalysisRunStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.renewals = 0

        def renew_lease(self, *args, **kwargs):
            self.renewals += 1
            if self.renewals >= 2:
                raise RuntimeError("injected lease loss")
            return super().renew_lease(*args, **kwargs)

    class BlockingEvaluator:
        def __init__(self):
            self.cancelled = asyncio.Event()

        async def evaluate(self, _run_id, _application_id, *, lease_owner):
            assert lease_owner
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()

    async def exercise():
        clock = lambda: datetime(2026, 8, 12, tzinfo=timezone.utc)
        store = LeaseFailingStore(
            tmp_path / "analysis-runs.sqlite3", clock=clock
        )
        evaluator = BlockingEvaluator()
        service = AnalysisRunService(
            workspace=QueueWorkspace([_application(1)]),
            store=store,
            evaluator=evaluator,
            clock=clock,
            worker_id="lease-worker",
            lease_duration=timedelta(milliseconds=30),
        )
        await service.start(target=1, idempotency_key="lease-start")

        with pytest.raises(RuntimeError, match="injected lease loss"):
            await service.process_next_run()

        assert evaluator.cancelled.is_set()
        snapshot = store.get_active_run()
        assert snapshot is not None
        assert snapshot.lifecycle is AnalysisRunLifecycle.RUNNING
        assert snapshot.candidates[0].state is AnalysisCandidateState.EVALUATING

    asyncio.run(exercise())


def test_reclaimed_worker_fences_stale_notion_commit_after_provider_response(
    tmp_path,
):
    class Clock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class BlockingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def transmit(self, prepared):
            self.started.set()
            await self.release.wait()
            return await super().transmit(prepared)

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = Clock()
        path = tmp_path / "analysis-runs.sqlite3"
        workspace = FakeWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(path, clock=clock)
        model = BlockingModel()
        old_service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=model,
                store=store,
                spend_policy=FixedSpendPolicy(),
            ),
            clock=clock,
            worker_id="old-worker",
            lease_duration=timedelta(seconds=30),
        )
        run = await old_service.start(
            target=1, idempotency_key="fenced-side-effect"
        )
        processing = asyncio.create_task(old_service.process_next_run())
        await asyncio.wait_for(model.started.wait(), timeout=0.2)

        clock.now += timedelta(seconds=31)
        replacement = SqliteAnalysisRunStore(path, clock=clock)
        reclaimed = replacement.claim_recoverable_run(
            lease_owner="new-worker",
            lease_expires_at=clock.now + timedelta(seconds=30),
        )
        assert reclaimed is not None
        model.release.set()

        with pytest.raises(AnalysisRunLeaseError):
            await processing
        application = await workspace.load_analysis_input("app-northstar")
        assert application.analysis is None
        assert application.analyzed is False
        snapshot = replacement.get_run(run.run_id)
        assert snapshot is not None
        assert snapshot.lease_owner == "new-worker"

    asyncio.run(exercise())


def test_inflight_notion_commit_holds_a_durable_nonshortening_lease(tmp_path):
    class ControlledClock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class BlockingAppendWorkspace(FakeWorkspace):
        def __init__(self, path):
            super().__init__(path)
            self.append_started = asyncio.Event()
            self.release_append = asyncio.Event()

        async def append_application_analysis(self, application_id, document):
            self.append_started.set()
            await self.release_append.wait()
            await super().append_application_analysis(application_id, document)

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = ControlledClock()
        path = tmp_path / "analysis-runs.sqlite3"
        workspace = BlockingAppendWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(path, clock=clock)
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=FakeApplicationAnalysisModel(),
                store=store,
                spend_policy=FixedSpendPolicy(),
            ),
            clock=clock,
            worker_id="commit-worker",
            lease_duration=timedelta(seconds=1),
        )
        run = await service.start(
            target=1, idempotency_key="protected-notion-commit"
        )
        processing = asyncio.create_task(service.process_next_run())
        await asyncio.wait_for(workspace.append_started.wait(), timeout=0.2)

        clock.now += timedelta(seconds=2)
        replacement = SqliteAnalysisRunStore(path, clock=clock)
        competing = replacement.claim_recoverable_run(
            lease_owner="replacement-worker",
            lease_expires_at=clock.now + timedelta(seconds=30),
        )

        assert competing is None
        protected = replacement.get_run(run.run_id)
        assert protected is not None
        assert protected.lease_owner == "commit-worker"
        assert protected.lease_expires_at > clock.now

        workspace.release_append.set()
        finished = await processing
        assert finished is not None
        assert finished.outcome is AnalysisRunOutcome.TARGET_MET

    asyncio.run(exercise())


def test_unresolved_ambiguous_body_commit_quarantines_candidate_without_blocking_later_runs(
    tmp_path,
):
    class ControlledClock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class NeverAppliedWorkspace(QueueWorkspace):
        def __init__(self):
            super().__init__([_application(1), _application(2), _application(3)])
            self.append_calls = 0
            self.finalize_calls = 0
            self.saved = {}

        async def list_analysis_queue(self, *, limit, cursor):
            assert cursor is None
            eligible = []
            for item in self.applications:
                application = await self.load_analysis_input(item.id)
                if not application.analyzed:
                    eligible.append(application)
            return QueuePage(
                items=tuple(eligible[:limit]),
                total=len(eligible),
                limit=limit,
                next_cursor=None,
                has_more=len(eligible) > limit,
            )

        async def load_analysis_queue_snapshot(
            self, *, excluded_application_ids=frozenset()
        ):
            eligible = []
            for item in self.applications:
                application = await self.load_analysis_input(item.id)
                if (
                    not application.analyzed
                    and application.id not in excluded_application_ids
                ):
                    eligible.append(application)
            return tuple(eligible)

        async def load_analysis_input(self, application_id):
            application = next(
                item for item in self.applications if item.id == application_id
            )
            return self.saved.get(application_id, application)

        async def load_analysis_evidence(self):
            return (
                EvidenceItem(
                    id="resume-evidence",
                    text="Python REST APIs automated tests",
                    source_section="Experience",
                ),
            )

        async def append_application_analysis(self, application_id, document):
            self.append_calls += 1
            if application_id == "app-1":
                raise WorkspaceProviderError(
                    "Notion response was lost.", retryable=True
                )
            application = await self.load_analysis_input(application_id)
            self.saved[application_id] = dataclass_replace(
                application, analysis=document
            )

        async def finalize_application_analysis(
            self, application_id, *, match_score
        ):
            self.finalize_calls += 1
            application = await self.load_analysis_input(application_id)
            self.saved[application_id] = dataclass_replace(
                application, analyzed=True, match_score=match_score
            )

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.application_ids = []

        async def transmit(self, prepared):
            self.application_ids.append(prepared)
            return await super().transmit(prepared)

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = ControlledClock()
        workspace = NeverAppliedWorkspace()
        store = SqliteAnalysisRunStore(
            tmp_path / "analysis-runs.sqlite3", clock=clock
        )
        model = CountingModel()
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=model,
                store=store,
                spend_policy=FixedSpendPolicy(),
            ),
            clock=clock,
            worker_id="commit-worker",
        )
        first = await service.start(target=1, idempotency_key="unknown-body")
        with pytest.raises(WorkspaceCommitUnknownError):
            await service.process_next_run()

        clock.now += timedelta(minutes=2, seconds=1)
        quarantined = await service.process_next_run()
        assert quarantined is not None
        assert quarantined.outcome is AnalysisRunOutcome.TARGET_MET
        assert quarantined.candidates[0].reason_code == "commit_unknown"

        second = await service.start(target=1, idempotency_key="later-run")
        assert [candidate.application_id for candidate in second.candidates] == [
            "app-3"
        ]
        finished = await service.process_next_run()
        assert finished is not None
        assert finished.outcome is AnalysisRunOutcome.TARGET_MET
        assert len(model.application_ids) == 3
        assert first.run_id != second.run_id

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "ambiguous_stage", ["append", "append_malformed_2xx", "finalize"]
)
def test_ambiguous_notion_commit_waits_for_fence_then_recovers_without_retransmission(
    tmp_path, ambiguous_stage
):
    class ControlledClock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class AppliedThenAmbiguousWorkspace(FakeWorkspace):
        def __init__(self, path):
            super().__init__(path)
            self.append_calls = 0
            self.finalize_calls = 0

        async def append_application_analysis(self, application_id, document):
            self.append_calls += 1
            await super().append_application_analysis(application_id, document)
            if ambiguous_stage.startswith("append"):
                raise WorkspaceProviderError(
                    "Notion response was lost.",
                    status=(200 if ambiguous_stage == "append_malformed_2xx" else None),
                    retryable=ambiguous_stage == "append",
                )

        async def finalize_application_analysis(
            self, application_id, *, match_score
        ):
            self.finalize_calls += 1
            await super().finalize_application_analysis(
                application_id, match_score=match_score
            )
            if ambiguous_stage == "finalize":
                raise WorkspaceProviderError(
                    "Notion response was lost.", retryable=True
                )

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.transmissions = 0

        async def transmit(self, prepared):
            self.transmissions += 1
            return await super().transmit(prepared)

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = ControlledClock()
        workspace = AppliedThenAmbiguousWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(
            tmp_path / "analysis-runs.sqlite3", clock=clock
        )
        model = CountingModel()
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=model,
                store=store,
                spend_policy=FixedSpendPolicy(),
            ),
            clock=clock,
            worker_id="commit-worker",
            lease_duration=timedelta(seconds=30),
        )
        run = await service.start(
            target=1, idempotency_key=f"ambiguous-{ambiguous_stage}"
        )

        with pytest.raises(WorkspaceCommitUnknownError):
            await service.process_next_run()

        protected = store.get_run(run.run_id)
        [call] = store.list_provider_calls(run.run_id)
        assert protected is not None
        assert protected.lifecycle is AnalysisRunLifecycle.RUNNING
        assert protected.lease_expires_at == clock.now + timedelta(minutes=2)
        assert call.state is AnalysisProviderCallState.SETTLED
        assert call.result_code == (
            "response_valid_commit_unknown"
            if ambiguous_stage.startswith("append")
            else "response_valid"
        )
        with pytest.raises(ActiveAnalysisRunError):
            await service.start(target=1, idempotency_key="new-run-too-soon")
        assert await service.process_next_run() is None

        clock.now += timedelta(minutes=2, seconds=1)
        finished = await service.process_next_run()

        assert finished is not None
        assert finished.outcome is AnalysisRunOutcome.TARGET_MET
        assert finished.repaired_count == 0
        assert (
            finished.candidates[0].state
            is AnalysisCandidateState.ANALYZED
        )
        assert model.transmissions == 1
        assert workspace.append_calls == 1
        assert workspace.finalize_calls == int(
            ambiguous_stage.startswith("append") or ambiguous_stage == "finalize"
        )

    asyncio.run(exercise())


def test_definitive_notion_rejection_clears_quarantine_and_backfills(tmp_path):
    class RejectingAppendWorkspace(FakeWorkspace):
        async def append_application_analysis(self, application_id, document):
            if application_id == "app-northstar":
                raise WorkspaceProviderError(
                    "Notion rejected the body append.", status=404
                )
            await super().append_application_analysis(application_id, document)

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = lambda: datetime(2026, 8, 12, tzinfo=timezone.utc)
        workspace = RejectingAppendWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(
            tmp_path / "analysis-runs.sqlite3", clock=clock
        )
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=FakeApplicationAnalysisModel(),
                store=store,
                spend_policy=FixedSpendPolicy(),
            ),
            clock=clock,
            worker_id="settlement-worker",
        )
        run = await service.start(
            target=1,
            idempotency_key="definitive-body-append-rejection",
        )

        finished = await service.process_next_run()

        assert finished is not None
        assert finished.run_id == run.run_id
        assert finished.outcome is AnalysisRunOutcome.TARGET_MET
        assert finished.candidates[0].state is AnalysisCandidateState.FAILED
        assert finished.candidates[0].reason_code == "source_unreadable"
        assert finished.candidates[1].state is AnalysisCandidateState.ANALYZED
        assert finished.active_reservation_micros == 0
        assert finished.verified_cost_micros == 246
        calls = store.list_provider_calls(run.run_id)
        assert all(
            call.state is AnalysisProviderCallState.SETTLED for call in calls
        )
        rejected_call = next(
            call for call in calls if call.application_id == "app-northstar"
        )
        assert rejected_call.result_code == "response_valid_source_unreadable"
        assert store.list_commit_quarantines() == ()
        application = await workspace.load_analysis_input("app-northstar")
        assert application.analysis is None
        assert application.analyzed is False

    asyncio.run(exercise())


def test_post_response_processing_failure_settles_the_durable_receipt(tmp_path):
    class FailingMatcher:
        def match(self, *_args, **_kwargs):
            raise RuntimeError("injected matching failure")

    class FixedSpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        workspace = FakeWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(tmp_path / "analysis-runs.sqlite3")
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=FakeApplicationAnalysisModel(),
                store=store,
                spend_policy=FixedSpendPolicy(),
                matcher=FailingMatcher(),
            ),
            worker_id="processing-failure-worker",
        )
        run = await service.start(
            target=1, idempotency_key="post-response-processing-failure"
        )

        finished = await service.process_next_run()

        assert finished is not None
        assert finished.outcome is AnalysisRunOutcome.FAILED
        assert finished.reason_code == "unsafe_storage_failure"
        assert finished.active_reservation_micros == 0
        assert finished.verified_cost_micros == 123
        [call] = store.list_provider_calls(run.run_id)
        assert call.state is AnalysisProviderCallState.SETTLED
        assert call.result_code == "response_processing_failed"

    asyncio.run(exercise())


def test_receipt_persistence_failure_keeps_candidate_recoverable(tmp_path):
    class ControlledClock:
        def __init__(self):
            self.now = datetime(2026, 8, 12, tzinfo=timezone.utc)

        def __call__(self):
            return self.now

    class FailingReceiptStore(SqliteAnalysisRunStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fail_receipt_once = True

        def record_provider_call_response(self, *args, **kwargs):
            if self.fail_receipt_once:
                self.fail_receipt_once = False
                raise AnalysisRunStoreError(
                    "injected response receipt persistence failure"
                )
            return super().record_provider_call_response(*args, **kwargs)

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.transmissions = 0

        async def transmit(self, prepared):
            self.transmissions += 1
            return await super().transmit(prepared)

    class FixedSpendPolicy:
        def __init__(self, observed_model):
            self.observed_model = observed_model

        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint=(
                    f"request-{self.observed_model.transmissions}"
                ),
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    async def exercise():
        clock = ControlledClock()
        path = tmp_path / "analysis-runs.sqlite3"
        workspace = FakeWorkspace(tmp_path / "workspace.json")
        store = FailingReceiptStore(path, clock=clock)
        model = CountingModel()
        spend_policy = FixedSpendPolicy(model)
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=model,
                store=store,
                spend_policy=spend_policy,
            ),
            clock=clock,
            worker_id="first-worker",
            lease_duration=timedelta(seconds=1),
        )
        run = await service.start(
            target=1, idempotency_key="receipt-write-recovery"
        )

        with pytest.raises(AnalysisRunStoreError):
            await service.process_next_run()

        interrupted = store.get_run(run.run_id)
        assert interrupted is not None
        assert interrupted.lifecycle is AnalysisRunLifecycle.RUNNING
        assert interrupted.candidates[0].state is AnalysisCandidateState.EVALUATING
        [first_call] = store.list_provider_calls(run.run_id)
        assert first_call.state is AnalysisProviderCallState.DISPATCHING

        clock.now += timedelta(seconds=2)
        restarted_store = SqliteAnalysisRunStore(path, clock=clock)
        restarted = AnalysisRunService(
            workspace=workspace,
            store=restarted_store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=model,
                store=restarted_store,
                spend_policy=spend_policy,
            ),
            clock=clock,
            worker_id="restarted-worker",
        )
        finished = await restarted.process_next_run()

        assert finished is not None
        assert finished.outcome is AnalysisRunOutcome.TARGET_MET
        assert model.transmissions == 2
        calls = restarted_store.list_provider_calls(finished.run_id)
        assert [call.state for call in calls] == [
            AnalysisProviderCallState.INDETERMINATE,
            AnalysisProviderCallState.SETTLED,
        ]
        assert finished.committed_spend_micros == 10_123

    asyncio.run(exercise())


def test_shared_workspace_provider_failure_finishes_instead_of_reclaiming_forever(
    tmp_path,
):
    class ProviderFailureWorkspace(FakeWorkspace):
        async def load_analysis_input(self, application_id):
            del application_id
            raise WorkspaceProviderError(
                "private Notion outage", retryable=True
            )

    clock = lambda: datetime(2026, 8, 12, tzinfo=timezone.utc)
    workspace = ProviderFailureWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    service = AnalysisRunService(
        workspace=workspace,
        store=store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=FakeApplicationAnalysisModel(),
            store=store,
            spend_policy=None,
        ),
        clock=clock,
        worker_id="workspace-failure-worker",
    )
    run = asyncio.run(
        service.start(target=1, idempotency_key="workspace-provider-failure")
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.run_id == run.run_id
    assert finished.outcome is AnalysisRunOutcome.FAILED
    assert finished.reason_code == "unsafe_storage_failure"
    assert finished.candidates[0].state is AnalysisCandidateState.FAILED
    assert finished.candidates[0].reason_code == "unsafe_storage_failure"
    assert store.list_recoverable_runs() == ()


@pytest.mark.parametrize("failure_on_load", [1, 2])
def test_candidate_page_disappearance_is_candidate_scoped_on_each_revalidation_load(
    tmp_path, failure_on_load
):
    class DeletedCandidateWorkspace(FakeWorkspace):
        def __init__(self, path):
            super().__init__(path)
            self.loads = 0

        async def load_analysis_input(self, application_id):
            self.loads += 1
            if self.loads == failure_on_load:
                raise WorkspaceProviderError(
                    "Notion page was not found.", status=404
                )
            return await super().load_analysis_input(application_id)

    async def exercise():
        workspace = DeletedCandidateWorkspace(tmp_path / "workspace.json")
        workspace._state["applications"] = workspace._state["applications"][:1]
        workspace._save()
        store = SqliteAnalysisRunStore(tmp_path / "analysis-runs.sqlite3")
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=FakeApplicationAnalysisModel(),
                store=store,
                spend_policy=None,
            ),
            worker_id="deleted-candidate-worker",
        )
        await service.start(target=1, idempotency_key="deleted-candidate")
        return await service.process_next_run()

    finished = asyncio.run(exercise())
    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.QUEUE_EXHAUSTED
    assert finished.failed_count == 1
    assert finished.candidates[0].reason_code == "source_unreadable"


def test_missing_master_resume_evidence_stops_before_provider_dispatch(tmp_path):
    class MissingEvidenceWorkspace(FakeWorkspace):
        async def load_analysis_evidence(self):
            return ()

    class NoTransmissionModel(FakeApplicationAnalysisModel):
        async def transmit(self, _prepared):
            raise AssertionError("Missing shared evidence must stop before dispatch.")

    async def exercise():
        workspace = MissingEvidenceWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(tmp_path / "analysis-runs.sqlite3")
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=NoTransmissionModel(),
                store=store,
                spend_policy=None,
            ),
            worker_id="missing-evidence-worker",
        )
        await service.start(target=1, idempotency_key="missing-evidence")
        return await service.process_next_run(), store

    finished, store = asyncio.run(exercise())
    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.FAILED
    assert finished.reason_code == "master_resume_evidence_unavailable"
    assert store.list_provider_calls(finished.run_id) == ()


@pytest.mark.parametrize("evidence_failure", ["empty", "not_found"])
def test_missing_shared_evidence_stops_the_run_without_backfill(
    tmp_path, evidence_failure
):
    class MissingEvidenceWorkspace(FakeWorkspace):
        def __init__(self, path):
            super().__init__(path)
            self.evidence_loads = 0

        async def load_analysis_evidence(self):
            self.evidence_loads += 1
            if evidence_failure == "not_found":
                raise WorkspaceProviderError(
                    "Master Resume page was not found.", status=404
                )
            return ()

    class NoTransmissionModel(FakeApplicationAnalysisModel):
        async def transmit(self, _prepared):
            raise AssertionError(
                "Missing shared evidence must stop before dispatch."
            )

    async def exercise():
        workspace = MissingEvidenceWorkspace(tmp_path / "workspace.json")
        store = SqliteAnalysisRunStore(tmp_path / "analysis-runs.sqlite3")
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=NoTransmissionModel(),
                store=store,
                spend_policy=None,
            ),
            worker_id="missing-shared-evidence-worker",
        )
        await service.start(target=1, idempotency_key=evidence_failure)
        return await service.process_next_run(), workspace

    finished, workspace = asyncio.run(exercise())
    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.FAILED
    assert finished.reason_code == "master_resume_evidence_unavailable"
    assert finished.evaluated_count == 1
    assert finished.candidates[0].reason_code == (
        "master_resume_evidence_unavailable"
    )
    assert finished.candidates[1].state is AnalysisCandidateState.PENDING
    assert workspace.evidence_loads == 1


def test_legacy_repair_without_score_requires_shared_evidence(tmp_path):
    class MissingRepairEvidenceWorkspace(FakeWorkspace):
        async def load_analysis_evidence(self):
            raise WorkspaceProviderError(
                "Master Resume page was not found.", status=404
            )

    class NoTransmissionModel(FakeApplicationAnalysisModel):
        async def transmit(self, _prepared):
            raise AssertionError("An existing Analysis body needs no model call.")

    async def exercise():
        workspace = MissingRepairEvidenceWorkspace(tmp_path / "workspace.json")
        application = next(
            item
            for item in workspace._state["applications"]
            if item["id"] == "app-northstar"
        )
        application["analysis"] = {
            "summary": "Existing findings",
            "skillSignals": ["REST APIs"],
        }
        application["matchScore"] = None
        workspace._save()
        store = SqliteAnalysisRunStore(tmp_path / "analysis-runs.sqlite3")
        service = AnalysisRunService(
            workspace=workspace,
            store=store,
            evaluator=GraphAnalysisCandidateEvaluator(
                workspace=workspace,
                model=NoTransmissionModel(),
                store=store,
                spend_policy=None,
            ),
            worker_id="missing-repair-evidence-worker",
        )
        await service.start(target=1, idempotency_key="repair-no-evidence")
        finished = await service.process_next_run()
        return finished, await workspace.load_analysis_input("app-northstar")

    finished, application = asyncio.run(exercise())
    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.FAILED
    assert finished.reason_code == "master_resume_evidence_unavailable"
    assert finished.completion_count == 0
    assert application.analyzed is False
    assert application.match_score is None


def test_run_pursues_completion_target_through_fixed_candidate_set(tmp_path):
    clock = lambda: datetime(2026, 8, 12, tzinfo=timezone.utc)
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    workspace = QueueWorkspace([_application(index) for index in range(1, 8)])
    evaluator = RecordedEvaluator(
        {
            "app-1": AnalysisCandidateEvaluation(
                AnalysisCandidateState.SKIPPED, "became_ineligible"
            ),
            "app-2": AnalysisCandidateEvaluation(AnalysisCandidateState.ANALYZED),
            "app-3": AnalysisCandidateEvaluation(
                AnalysisCandidateState.FAILED, "invalid_source"
            ),
            "app-4": AnalysisCandidateEvaluation(AnalysisCandidateState.REPAIRED),
            "app-5": AnalysisCandidateEvaluation(AnalysisCandidateState.ANALYZED),
            "app-6": AnalysisCandidateEvaluation(AnalysisCandidateState.ANALYZED),
        }
    )
    service = AnalysisRunService(
        workspace=workspace,
        store=store,
        evaluator=evaluator,
        clock=clock,
        run_id_factory=lambda: "analysis-run-one",
        worker_id="test-worker",
    )

    accepted = asyncio.run(service.start(target=3, idempotency_key="start-one"))

    assert accepted.lifecycle is AnalysisRunLifecycle.QUEUED
    assert accepted.target == 3
    assert accepted.attempt_budget == 6
    assert [item.application_id for item in accepted.candidates] == [
        "app-1",
        "app-2",
        "app-3",
        "app-4",
        "app-5",
        "app-6",
    ]

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.lifecycle is AnalysisRunLifecycle.FINISHED
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert finished.completion_count == 3
    assert finished.evaluated_count == 5
    assert evaluator.application_ids == [
        "app-1",
        "app-2",
        "app-3",
        "app-4",
        "app-5",
    ]
    assert finished.candidates[-1].state is AnalysisCandidateState.PENDING


def test_start_is_idempotent_and_does_not_resnapshot_candidates(tmp_path):
    clock = lambda: datetime(2026, 8, 12, tzinfo=timezone.utc)
    store = SqliteAnalysisRunStore(
        tmp_path / "analysis-runs.sqlite3", clock=clock
    )
    workspace = QueueWorkspace([_application(index) for index in range(1, 5)])
    evaluator = RecordedEvaluator({})
    service = AnalysisRunService(
        workspace=workspace,
        store=store,
        evaluator=evaluator,
        run_id_factory=lambda: "analysis-run-stable",
        clock=clock,
    )

    first = asyncio.run(service.start(target=2, idempotency_key="stable-key"))
    workspace.applications.insert(0, _application(9))
    replay = asyncio.run(service.start(target=2, idempotency_key="stable-key"))

    assert replay.run_id == first.run_id
    assert replay.candidates == first.candidates


def test_restart_settles_recorded_response_and_repairs_without_retransmission(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    asyncio.run(
        workspace.append_application_analysis(
            "app-northstar",
            ApplicationAnalysisDocument(
                summary="A valid provider response was already committed.",
                match_score=77,
                skill_signals=(PersistedSkillSignal("React", "React"),),
                heading="Application Analysis",
            ),
        )
    )
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-recovery",
        idempotency_key="recovery-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-recovery",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-recovery", lease_owner="old-worker"
    )
    authorization = AnalysisProviderAuthorizationMetadata(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-flash",
        approval_fingerprint="approval",
        request_fingerprint="request",
        tokenizer_tokens=100,
        utf8_bytes=300,
        protocol_overhead_tokens=27,
        input_cost_bound_tokens=327,
        max_output_tokens=8_000,
        cache_hit_input_micros_per_million_tokens=2_800,
        cache_miss_input_micros_per_million_tokens=140_000,
        output_micros_per_million_tokens=280_000,
    )
    call = store.reserve_provider_call(
        run_id="analysis-run-recovery",
        application_id="app-northstar",
        call_id="call-recorded",
        call_index=1,
        reservation_micros=10_000,
        authorization=authorization,
        lease_owner="old-worker",
    )
    assert call is not None
    store.begin_provider_dispatch(call.call_id, lease_owner="old-worker")
    store.record_provider_call_response(
        call.call_id,
        AnalysisProviderSettlementMetadata(
            provider_request_id="request-1",
            input_tokens=100,
            output_tokens=200,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=100,
            total_tokens=300,
            reasoning_output_tokens=150,
            finish_reason="stop",
            result_code="response_valid",
        ),
        lease_owner="old-worker",
    )

    class RecoverySpendPolicy:
        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

        def estimate(self, **_request):
            raise AssertionError("Recovery must not authorize another call.")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("Recovery must not render another request.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(
        path, clock=lambda: restarted_at
    )
    evaluator = GraphAnalysisCandidateEvaluator(
        workspace=workspace,
        model=NoTransmissionModel(),
        store=restarted_store,
        spend_policy=RecoverySpendPolicy(),
    )
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=evaluator,
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert finished.repaired_count == 0
    assert finished.candidates[0].state is AnalysisCandidateState.ANALYZED
    assert finished.verified_cost_micros == 123
    [recovered_call] = restarted_store.list_provider_calls(finished.run_id)
    assert recovered_call.state is AnalysisProviderCallState.SETTLED
    application = asyncio.run(workspace.load_analysis_input("app-northstar"))
    assert application.analyzed is True
    assert application.match_score == 77


def test_restart_after_recorded_response_before_processing_does_not_retransmit(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-recorded-unprocessed",
        idempotency_key="recorded-unprocessed-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-recorded-unprocessed",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-recorded-unprocessed", lease_owner="old-worker"
    )
    call = store.reserve_provider_call(
        run_id="analysis-run-recorded-unprocessed",
        application_id="app-northstar",
        call_id="recorded-unprocessed-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            approval_fingerprint="approval",
            request_fingerprint="request",
            tokenizer_tokens=100,
            utf8_bytes=300,
            protocol_overhead_tokens=27,
            input_cost_bound_tokens=327,
            max_output_tokens=8_000,
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
        ),
        lease_owner="old-worker",
    )
    assert call is not None
    store.begin_provider_dispatch(call.call_id, lease_owner="old-worker")
    store.record_provider_call_response(
        call.call_id,
        AnalysisProviderSettlementMetadata(
            provider_request_id="request-1",
            input_tokens=100,
            output_tokens=200,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=100,
            total_tokens=300,
            reasoning_output_tokens=150,
            finish_reason="stop",
            result_code="response_received",
        ),
        lease_owner="old-worker",
    )

    class RecoverySpendPolicy:
        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

        def estimate(self, **_request):
            raise AssertionError("An unprocessed response must not be retried.")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("An unprocessed response must not be retried.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=RecoverySpendPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.QUEUE_EXHAUSTED
    assert finished.indeterminate_count == 1
    assert finished.candidates[0].state is AnalysisCandidateState.INDETERMINATE
    assert finished.candidates[0].reason_code == (
        "response_processing_interrupted"
    )
    assert finished.verified_cost_micros == 123
    [recovered_call] = restarted_store.list_provider_calls(finished.run_id)
    assert recovered_call.state is AnalysisProviderCallState.SETTLED
    assert recovered_call.result_code == "response_received"


def test_restart_counts_no_call_repair_committed_before_candidate_result(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-repaired-recovery",
        idempotency_key="repaired-recovery-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-repaired-recovery",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-repaired-recovery",
        lease_owner="old-worker",
    )
    analysis = ApplicationAnalysisDocument(
        summary="An existing analysis was repaired before the process stopped.",
        match_score=77,
        skill_signals=(PersistedSkillSignal("React", "React"),),
        heading="Application Analysis",
    )
    asyncio.run(workspace.append_application_analysis("app-northstar", analysis))
    asyncio.run(
        workspace.finalize_application_analysis(
            "app-northstar",
            match_score=77,
        )
    )

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("A committed repair must not call the provider.")

    class NoAuthorizationPolicy:
        def estimate(self, **_request):
            raise AssertionError("A committed repair must not reserve provider spend.")

        def settle(self, *_args):
            raise AssertionError("A no-call repair has no provider settlement.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=NoAuthorizationPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert finished.completion_count == 1
    assert finished.repaired_count == 1
    assert finished.evaluated_count == 1
    assert finished.candidates[0].state is AnalysisCandidateState.REPAIRED
    assert restarted_store.list_provider_calls(finished.run_id) == ()


def test_normal_restart_preserves_run_scoped_partial_repair_failure(tmp_path):
    class RejectingRepairWorkspace(FakeWorkspace):
        async def finalize_application_analysis(
            self, application_id, *, match_score
        ):
            raise WorkspaceProviderError(
                "Notion rejected the property repair.", status=400
            )

    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = RejectingRepairWorkspace(tmp_path / "workspace.json")
    analysis = ApplicationAnalysisDocument(
        summary="A paid analysis body already exists.",
        match_score=77,
        skill_signals=(PersistedSkillSignal("React", "React"),),
        heading="Application Analysis",
    )
    asyncio.run(workspace.append_application_analysis("app-northstar", analysis))
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-repair-rejected",
        idempotency_key="repair-rejected-start",
        target=1,
        candidate_ids=("app-northstar", "app-lantern"),
    )
    store.start_run(
        "analysis-run-repair-rejected",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-repair-rejected", lease_owner="old-worker"
    )

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("Partial repair must not call the provider.")

    class NoAuthorizationPolicy:
        def estimate(self, **_request):
            raise AssertionError("Partial repair must not authorize spend.")

        def settle(self, *_args):
            raise AssertionError("Partial repair has no receipt to settle.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=NoAuthorizationPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.FAILED
    assert finished.reason_code == "unsafe_storage_failure"
    assert finished.candidates[0].state is AnalysisCandidateState.FAILED
    assert finished.candidates[0].reason_code == "unsafe_storage_failure"
    assert finished.candidates[1].state is AnalysisCandidateState.PENDING


def test_restart_continues_after_settled_invalid_response_with_fresh_call(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-settled-invalid",
        idempotency_key="settled-invalid-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-settled-invalid",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-settled-invalid",
        lease_owner="old-worker",
    )
    prior = store.reserve_provider_call(
        run_id="analysis-run-settled-invalid",
        application_id="app-northstar",
        call_id="settled-invalid-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            approval_fingerprint="approval",
            request_fingerprint="request",
            tokenizer_tokens=100,
            utf8_bytes=300,
            protocol_overhead_tokens=27,
            input_cost_bound_tokens=327,
            max_output_tokens=8_000,
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
        ),
        lease_owner="old-worker",
    )
    assert prior is not None
    store.begin_provider_dispatch(prior.call_id, lease_owner="old-worker")
    store.transition_provider_call(
        prior.call_id,
        AnalysisProviderCallState.SENT,
        lease_owner="old-worker",
    )
    store.transition_provider_call(
        prior.call_id,
        AnalysisProviderCallState.RESPONSE_RECORDED,
        lease_owner="old-worker",
    )
    store.settle_provider_call(
        prior.call_id,
        verified_cost_micros=100,
        lease_owner="old-worker",
    )

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.transmissions = 0

        async def transmit(self, prepared):
            self.transmissions += 1
            return await super().transmit(prepared)

    class RetrySpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="fresh-request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    model = CountingModel()
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=model,
            store=restarted_store,
            spend_policy=RetrySpendPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert finished.completion_count == 1
    assert model.transmissions == 1
    calls = restarted_store.list_provider_calls(finished.run_id)
    assert tuple(call.authorization_index for call in calls) == (1, 2)
    assert tuple(call.transmission_index for call in calls) == (1, 2)
    assert all(call.state is AnalysisProviderCallState.SETTLED for call in calls)
    assert finished.verified_cost_micros == 223


def test_restart_reauthorizes_after_indeterminate_sent_call(tmp_path):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-indeterminate-retry",
        idempotency_key="indeterminate-retry-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-indeterminate-retry",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-indeterminate-retry",
        lease_owner="old-worker",
    )
    prior = store.reserve_provider_call(
        run_id="analysis-run-indeterminate-retry",
        application_id="app-northstar",
        call_id="interrupted-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            approval_fingerprint="approval",
            request_fingerprint="interrupted-request",
            tokenizer_tokens=100,
            utf8_bytes=300,
            protocol_overhead_tokens=27,
            input_cost_bound_tokens=327,
            max_output_tokens=8_000,
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
        ),
        lease_owner="old-worker",
    )
    assert prior is not None
    store.begin_provider_dispatch(prior.call_id, lease_owner="old-worker")
    store.transition_provider_call(
        prior.call_id,
        AnalysisProviderCallState.SENT,
        lease_owner="old-worker",
    )

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.transmissions = 0

        async def transmit(self, prepared):
            self.transmissions += 1
            return await super().transmit(prepared)

    class RetrySpendPolicy:
        def estimate(self, **request):
            return AnalysisCostEstimate(
                provider="deepseek",
                endpoint=request["endpoint"],
                model=request["model"],
                approval_fingerprint="approval",
                request_fingerprint="fresh-request",
                tokenizer_tokens=100,
                utf8_bytes=300,
                protocol_overhead_tokens=27,
                input_cost_bound_tokens=327,
                max_output_tokens=request["max_output_tokens"],
                cache_hit_input_micros_per_million_tokens=2_800,
                cache_miss_input_micros_per_million_tokens=140_000,
                output_micros_per_million_tokens=280_000,
                worst_case_micros=10_000,
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(True, 123, None)

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    model = CountingModel()
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=model,
            store=restarted_store,
            spend_policy=RetrySpendPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.TARGET_MET
    assert model.transmissions == 1
    calls = restarted_store.list_provider_calls(finished.run_id)
    assert tuple(call.state for call in calls) == (
        AnalysisProviderCallState.INDETERMINATE,
        AnalysisProviderCallState.SETTLED,
    )
    assert tuple(call.transmission_index for call in calls) == (1, 2)
    assert finished.indeterminate_reservation_micros == 10_000
    assert finished.verified_cost_micros == 123
    assert finished.committed_spend_micros == 10_123


def test_restarted_cancellation_reconciles_evaluating_candidate_without_retry(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-cancelling-recovery",
        idempotency_key="cancelling-recovery-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-cancelling-recovery",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-cancelling-recovery",
        lease_owner="old-worker",
    )
    prior = store.reserve_provider_call(
        run_id="analysis-run-cancelling-recovery",
        application_id="app-northstar",
        call_id="cancelling-interrupted-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            approval_fingerprint="approval",
            request_fingerprint="interrupted-request",
            tokenizer_tokens=100,
            utf8_bytes=300,
            protocol_overhead_tokens=27,
            input_cost_bound_tokens=327,
            max_output_tokens=8_000,
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
        ),
        lease_owner="old-worker",
    )
    assert prior is not None
    store.begin_provider_dispatch(prior.call_id, lease_owner="old-worker")
    store.transition_provider_call(
        prior.call_id,
        AnalysisProviderCallState.SENT,
        lease_owner="old-worker",
    )
    store.request_cancellation("analysis-run-cancelling-recovery")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("Cancellation recovery must not prepare a retry.")

    class NoAuthorizationPolicy:
        def estimate(self, **_request):
            raise AssertionError("Cancellation recovery must not reserve a retry.")

        def settle(self, *_args):
            raise AssertionError("An ambiguous call has no valid settlement.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=NoAuthorizationPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.candidates[0].state is AnalysisCandidateState.INDETERMINATE
    assert finished.candidates[0].reason_code == "interrupted_provider_call"
    assert finished.indeterminate_reservation_micros == 10_000
    [reconciled] = restarted_store.list_provider_calls(finished.run_id)
    assert reconciled.state is AnalysisProviderCallState.INDETERMINATE


def test_restarted_cancellation_before_dispatch_is_skipped_not_indeterminate(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-cancelled-before-dispatch",
        idempotency_key="cancelled-before-dispatch-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-cancelled-before-dispatch",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-cancelled-before-dispatch",
        lease_owner="old-worker",
    )
    store.request_cancellation("analysis-run-cancelled-before-dispatch")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("Cancellation must not prepare a provider call.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=None,
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.candidates[0].state is AnalysisCandidateState.SKIPPED
    assert finished.candidates[0].reason_code == "cancelled_before_dispatch"
    assert finished.indeterminate_count == 0
    assert restarted_store.list_provider_calls(finished.run_id) == ()


def test_restarted_cancellation_counts_already_committed_evaluating_candidate(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-cancelled-commit",
        idempotency_key="cancelled-commit-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-cancelled-commit",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-cancelled-commit",
        lease_owner="old-worker",
    )
    analysis = ApplicationAnalysisDocument(
        summary="A valid completion was committed before cancellation.",
        match_score=77,
        skill_signals=(PersistedSkillSignal("React", "React"),),
        heading="Application Analysis",
    )
    asyncio.run(workspace.append_application_analysis("app-northstar", analysis))
    asyncio.run(
        workspace.finalize_application_analysis(
            "app-northstar",
            match_score=77,
        )
    )
    store.request_cancellation("analysis-run-cancelled-commit")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError("Committed recovery must not prepare a call.")

    class NoAuthorizationPolicy:
        def estimate(self, **_request):
            raise AssertionError("Committed recovery must not authorize a call.")

        def settle(self, *_args):
            raise AssertionError("No provider call exists to settle.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=NoAuthorizationPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.completion_count == 1
    assert finished.repaired_count == 1
    assert finished.candidates[0].state is AnalysisCandidateState.REPAIRED


def test_restarted_cancellation_repairs_body_first_partial_without_provider_call(
    tmp_path,
):
    initial = datetime(2026, 8, 12, tzinfo=timezone.utc)
    path = tmp_path / "analysis-runs.sqlite3"
    workspace = FakeWorkspace(tmp_path / "workspace.json")
    store = SqliteAnalysisRunStore(path, clock=lambda: initial)
    store.create_run(
        run_id="analysis-run-cancelled-body-first",
        idempotency_key="cancelled-body-first-start",
        target=1,
        candidate_ids=("app-northstar",),
    )
    store.start_run(
        "analysis-run-cancelled-body-first",
        lease_owner="old-worker",
        lease_expires_at=initial + timedelta(seconds=1),
    )
    store.claim_next_candidate(
        "analysis-run-cancelled-body-first",
        lease_owner="old-worker",
    )
    call = store.reserve_provider_call(
        run_id="analysis-run-cancelled-body-first",
        application_id="app-northstar",
        call_id="cancelled-body-first-call",
        call_index=1,
        reservation_micros=10_000,
        authorization=AnalysisProviderAuthorizationMetadata(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            approval_fingerprint="approval",
            request_fingerprint="body-first-request",
            tokenizer_tokens=100,
            utf8_bytes=300,
            protocol_overhead_tokens=27,
            input_cost_bound_tokens=327,
            max_output_tokens=8_000,
            cache_hit_input_micros_per_million_tokens=2_800,
            cache_miss_input_micros_per_million_tokens=140_000,
            output_micros_per_million_tokens=280_000,
        ),
        lease_owner="old-worker",
    )
    assert call is not None
    store.begin_provider_dispatch(call.call_id, lease_owner="old-worker")
    store.transition_provider_call(
        call.call_id,
        AnalysisProviderCallState.RESPONSE_RECORDED,
        lease_owner="old-worker",
    )
    store.settle_provider_call(
        call.call_id,
        verified_cost_micros=123,
        lease_owner="old-worker",
    )
    analysis = ApplicationAnalysisDocument(
        summary="A paid analysis body was committed before cancellation.",
        match_score=77,
        skill_signals=(PersistedSkillSignal("React", "React"),),
        heading="Application Analysis",
    )
    asyncio.run(
        workspace.append_application_analysis("app-northstar", analysis)
    )
    store.request_cancellation("analysis-run-cancelled-body-first")

    class NoTransmissionModel:
        def prepare(self, *_args, **_kwargs):
            raise AssertionError(
                "Body-first cancellation recovery must not prepare a call."
            )

    class NoAuthorizationPolicy:
        def estimate(self, **_request):
            raise AssertionError(
                "Body-first cancellation recovery must not authorize a call."
            )

        def settle(self, *_args):
            raise AssertionError("No provider call exists to settle.")

    restarted_at = initial + timedelta(seconds=2)
    restarted_store = SqliteAnalysisRunStore(path, clock=lambda: restarted_at)
    service = AnalysisRunService(
        workspace=workspace,
        store=restarted_store,
        evaluator=GraphAnalysisCandidateEvaluator(
            workspace=workspace,
            model=NoTransmissionModel(),
            store=restarted_store,
            spend_policy=NoAuthorizationPolicy(),
        ),
        clock=lambda: restarted_at,
        worker_id="new-worker",
    )

    finished = asyncio.run(service.process_next_run())

    assert finished is not None
    assert finished.outcome is AnalysisRunOutcome.CANCELLED
    assert finished.completion_count == 1
    assert finished.repaired_count == 0
    assert finished.candidates[0].state is AnalysisCandidateState.ANALYZED
    recovered = asyncio.run(workspace.load_analysis_input("app-northstar"))
    assert recovered.analysis is not None
    assert recovered.analyzed is True
    assert recovered.match_score == 77
    [recovered_call] = restarted_store.list_provider_calls(finished.run_id)
    assert recovered_call.state is AnalysisProviderCallState.SETTLED
    assert finished.verified_cost_micros == 123
