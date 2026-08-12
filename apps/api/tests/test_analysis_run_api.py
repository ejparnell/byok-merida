from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import replace as dataclass_replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.features.applications.analysis_authorization import (
    PreparedAnalysisCall,
)
from merida_api.features.applications.analysis_run_store import (
    UnavailableAnalysisRunStore,
)
from merida_api.features.applications.analysis_spend import (
    AnalysisAuthorizationBlocked,
    AnalysisContextLimitExceeded,
    AnalysisCostEstimate,
    AnalysisSettlement,
)
from merida_api.features.applications.workspace import (
    AnalysisCallEvidence,
    AnalysisModelResponse,
)
from fakes.app import create_test_app
from fakes.models import FakeApplicationAnalysisModel
from fakes.workspace import FakeWorkspace
from merida_api.shared.workspace import (
    QueuePage,
    WorkspaceDataError,
    WorkspaceIssue,
    WorkspaceReadiness,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
        analysis_run_store_path=tmp_path / "analysis-runs.sqlite3",
    )


def _eventually_finished(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        response = client.get(
            f"/api/v1/applications/analysis/runs/{run_id}"
        )
        assert response.status_code == 200
        run = response.json()["run"]
        if run["lifecycle"] == "finished":
            return run
        time.sleep(0.005)
    raise AssertionError("Analysis Run did not finish.")


def test_public_run_returns_202_and_pursues_multiple_completions(tmp_path):
    app = create_test_app(
        _settings(tmp_path), state_path=tmp_path / "workspace.json"
    )

    with TestClient(app) as client:
        empty_active = client.get(
            "/api/v1/applications/analysis/runs/active"
        )
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "analysis-start-one"},
            json={"target": 2},
        )

        assert empty_active.status_code == 200
        assert empty_active.json()["run"] is None
        assert accepted.status_code == 202
        initial = accepted.json()["run"]
        assert initial["target"] == 2
        assert initial["lifecycle"] in {"queued", "running"}
        assert len(initial["candidates"]) == 2

        finished = _eventually_finished(client, initial["runId"])
        assert finished["progress"]["failed"] == 0, finished
        assert finished["outcome"] == "target_met"
        assert finished["progress"]["completions"] == 2
        assert finished["progress"]["evaluated"] == 2
        assert finished["spend"]["committedMicros"] <= 500_000
        assert finished["spend"]["activeReservationMicros"] == 0


@pytest.mark.parametrize("failure_on_load", (1, 2))
def test_candidate_source_reload_defect_backfills_without_failing_the_run(
    tmp_path, failure_on_load,
):
    class SourceDefectWorkspace(FakeWorkspace):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.source_loads = 0

        async def load_analysis_input(self, application_id):
            if application_id == "app-northstar":
                self.source_loads += 1
                if self.source_loads == failure_on_load:
                    raise WorkspaceDataError("Application source is unreadable.")
            return await super().load_analysis_input(application_id)

    state_path = tmp_path / "workspace.json"
    app = create_test_app(
        _settings(tmp_path),
        workspace=SourceDefectWorkspace(state_path),
        state_path=state_path,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "source-defect-backfill"},
            json={"target": 1},
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert finished["outcome"] == "target_met"
    assert finished["progress"] == {
        "completions": 1,
        "repaired": 0,
        "evaluated": 2,
        "skipped": 0,
        "failed": 1,
        "indeterminate": 0,
    }
    assert [candidate["state"] for candidate in finished["candidates"]] == [
        "failed",
        "analyzed",
    ]
    assert finished["candidates"][0]["reasonCode"] == "source_unreadable"


def test_source_context_overflow_dispatches_nothing_for_candidate_and_backfills(
    tmp_path,
):
    class OversizedFirstWorkspace(FakeWorkspace):
        async def load_analysis_input(self, application_id):
            application = await super().load_analysis_input(application_id)
            if application_id == "app-northstar":
                return dataclass_replace(
                    application,
                    job_content="oversized-context-marker " * 100,
                )
            return application

    class ContextBoundPolicy:
        def estimate(self, **request):
            if b"oversized-context-marker" in request["rendered_request"]:
                raise AnalysisContextLimitExceeded(
                    "source_context_exceeded",
                    "Job Content exceeds the approved model context.",
                )
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

    class CountingModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.transmissions = 0

        async def transmit(self, prepared):
            self.transmissions += 1
            return await super().transmit(prepared)

    state_path = tmp_path / "workspace.json"
    model = CountingModel()
    app = create_test_app(
        _settings(tmp_path),
        workspace=OversizedFirstWorkspace(state_path),
        state_path=state_path,
        analysis_model=model,
        analysis_spend_policy=ContextBoundPolicy(),
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "context-overflow-backfill"},
            json={"target": 1},
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert finished["outcome"] == "target_met"
    assert [candidate["state"] for candidate in finished["candidates"]] == [
        "failed",
        "analyzed",
    ]
    assert finished["candidates"][0]["reasonCode"] == (
        "source_context_exceeded"
    )
    assert model.transmissions == 1


def test_shared_storage_defect_stops_before_the_next_candidate(tmp_path):
    class SharedStorageDefectWorkspace(FakeWorkspace):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.evidence_reads = 0

        async def load_analysis_evidence(self):
            self.evidence_reads += 1
            if self.evidence_reads == 1:
                return await super().load_analysis_evidence()
            raise RuntimeError("Shared Analysis storage is unsafe.")

    state_path = tmp_path / "workspace.json"
    app = create_test_app(
        _settings(tmp_path),
        workspace=SharedStorageDefectWorkspace(state_path),
        state_path=state_path,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "shared-storage-defect"},
            json={"target": 1},
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert finished["outcome"] == "failed"
    assert finished["reasonCode"] == "unsafe_storage_failure"
    assert finished["progress"]["evaluated"] == 1
    assert [candidate["state"] for candidate in finished["candidates"]] == [
        "failed",
        "pending",
    ]
    assert finished["candidates"][0]["reasonCode"] == "unsafe_storage_failure"


def test_start_idempotency_and_typed_active_conflict(tmp_path):
    class DormantWorker:
        def __init__(self):
            self.wake_count = 0

        def start(self):
            return None

        def wake(self):
            self.wake_count += 1

        async def stop(self):
            return None

    worker = DormantWorker()
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_worker=worker,
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "stable-start"},
            json={"target": 2},
        )
        replay = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "stable-start"},
            json={"target": 2},
        )
        active_conflict = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "different-start"},
            json={"target": 1},
        )
        key_conflict = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "stable-start"},
            json={"target": 1},
        )

        assert replay.status_code == 202
        assert replay.json()["run"]["runId"] == first.json()["run"]["runId"]
        assert active_conflict.status_code == 409
        assert active_conflict.json()["error"] == {
            "code": "analysis_run_active",
            "message": "An Analysis Run is already active.",
            "requestId": None,
            "activeRunId": first.json()["run"]["runId"],
        }
        assert key_conflict.status_code == 409
        assert key_conflict.json()["error"]["code"] == "idempotency_conflict"
        assert worker.wake_count == 2


def test_start_requires_idempotency_key_and_rejects_legacy_limit(tmp_path):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_worker=DormantWorker(),
    )

    with TestClient(app) as client:
        missing_key = client.post(
            "/api/v1/applications/analysis/run", json={"target": 1}
        )
        legacy = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "legacy-start"},
            json={"limit": 1},
        )
        whitespace_key = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "   "},
            json={"target": 1},
        )

    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "invalid_request"
    assert legacy.status_code == 400
    assert legacy.json()["error"]["code"] == "invalid_request"
    assert whitespace_key.status_code == 400
    assert whitespace_key.json()["error"]["code"] == "invalid_request"


def test_analysis_health_blocks_an_unapproved_configured_model(tmp_path):
    settings = _settings(tmp_path).model_copy(
        update={"analysis_model": "unapproved-model"}
    )
    app = create_test_app(settings, state_path=tmp_path / "workspace.json")

    with TestClient(app) as client:
        response = client.get("/api/v1/health/analysis")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert "Analysis spend enforcement is unavailable." in response.json()[
        "errors"
    ]


def test_unavailable_run_store_fails_closed_without_breaking_app_lifespan(
    tmp_path,
):
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_run_store=UnavailableAnalysisRunStore(),
    )

    with TestClient(app) as client:
        health = client.get("/api/v1/health/analysis")
        start = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "unavailable-store"},
            json={"target": 1},
        )

    assert health.status_code == 200
    assert health.json()["status"] == "blocked"
    assert start.status_code == 503
    assert start.json()["error"]["code"] == "analysis_authorization_blocked"


def test_analysis_health_rechecks_rate_card_validity_at_request_time(tmp_path):
    current_time = [datetime(2026, 9, 11, 23, 59, tzinfo=timezone.utc)]
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_clock=lambda: current_time[0],
    )

    with TestClient(app) as client:
        before_expiry = client.get("/api/v1/health/analysis")
        current_time[0] = datetime(2026, 9, 12, tzinfo=timezone.utc)
        after_expiry = client.get("/api/v1/health/analysis")
        blocked_start = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "expired-rate-card"},
            json={"target": 1},
        )

    assert before_expiry.json()["status"] == "ready"
    assert after_expiry.json()["status"] == "blocked"
    assert "Analysis spend enforcement is unavailable." in after_expiry.json()[
        "errors"
    ]
    assert blocked_start.status_code == 503
    assert blocked_start.json()["error"]["code"] == (
        "analysis_authorization_blocked"
    )


def test_expired_pricing_does_not_preempt_replay_or_active_conflict(tmp_path):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    current_time = [datetime(2026, 9, 11, 23, 59, tzinfo=timezone.utc)]
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_clock=lambda: current_time[0],
        analysis_worker=DormantWorker(),
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "pricing-precedence"},
            json={"target": 1},
        )
        current_time[0] = datetime(2026, 9, 12, tzinfo=timezone.utc)
        replay = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "pricing-precedence"},
            json={"target": 1},
        )
        conflict = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "pricing-conflict"},
            json={"target": 1},
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["run"]["runId"] == first.json()["run"]["runId"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "analysis_run_active"
    assert conflict.json()["error"]["activeRunId"] == first.json()["run"][
        "runId"
    ]


def test_lost_runtime_configuration_does_not_preempt_durable_start_identity(
    tmp_path,
):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    settings = _settings(tmp_path)
    first_app = create_test_app(
        settings,
        state_path=tmp_path / "workspace.json",
        analysis_worker=DormantWorker(),
    )
    with TestClient(first_app) as client:
        first = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "configuration-precedence"},
            json={"target": 1},
        )
    assert first.status_code == 202

    restarted_without_configuration = create_app(
        Settings(
            export_path=tmp_path / "export-after-restart",
            recovery_journal_path=tmp_path / "recovery-after-restart.json",
            analysis_run_store_path=settings.analysis_run_store_path,
        ),
        analysis_worker=DormantWorker(),
    )
    with TestClient(restarted_without_configuration) as client:
        replay = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "configuration-precedence"},
            json={"target": 1},
        )
        conflict = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "configuration-conflict"},
            json={"target": 1},
        )

    assert replay.status_code == 202
    assert replay.json()["run"]["runId"] == first.json()["run"]["runId"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "analysis_run_active"
    assert conflict.json()["error"]["activeRunId"] == first.json()["run"][
        "runId"
    ]


def test_start_maps_workspace_readiness_block_to_safe_503(tmp_path):
    class BlockedWorkspace(FakeWorkspace):
        async def validate_analysis_workspace(self):
            return WorkspaceReadiness(
                errors=(
                    WorkspaceIssue(
                        database="applications",
                        property="Job Content",
                        message="Job Content is unavailable.",
                    ),
                )
            )

    app = create_test_app(
        _settings(tmp_path),
        workspace=BlockedWorkspace(tmp_path / "workspace.json"),
        state_path=tmp_path / "workspace.json",
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "blocked-start"},
            json={"target": 1},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analysis_authorization_blocked"


def test_start_blocks_when_master_resume_has_no_readable_analysis_evidence(tmp_path):
    class EmptyEvidenceWorkspace(FakeWorkspace):
        async def load_analysis_evidence(self):
            return ()

    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    state_path = tmp_path / "workspace.json"
    app = create_test_app(
        _settings(tmp_path),
        workspace=EmptyEvidenceWorkspace(state_path),
        state_path=state_path,
        analysis_worker=DormantWorker(),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "empty-analysis-evidence"},
            json={"target": 1},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analysis_authorization_blocked"


def test_cancel_before_dispatch_is_durable_and_idempotent(tmp_path):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_worker=DormantWorker(),
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "cancel-start"},
            json={"target": 2},
        )
        run_id = accepted.json()["run"]["runId"]
        first = client.post(
            f"/api/v1/applications/analysis/runs/{run_id}/cancel"
        )
        repeated = client.post(
            f"/api/v1/applications/analysis/runs/{run_id}/cancel"
        )

        assert first.json()["run"]["lifecycle"] == "cancelling"
        assert repeated.json()["run"] == first.json()["run"]
        finished = asyncio.run(app.state.analysis_runs.process_next_run())
        assert finished is not None
        assert finished.outcome.value == "cancelled"
        assert finished.evaluated_count == 0
        assert finished.committed_spend_micros == 0
        after_finished = client.post(
            f"/api/v1/applications/analysis/runs/{run_id}/cancel"
        )
        assert after_finished.json()["run"]["outcome"] == "cancelled"


def test_cancel_during_valid_inflight_call_commits_it_then_stops(tmp_path):
    class BlockingModel:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def prepare(self, application, *, repair_code=None):
            document = {
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "Analyze."},
                    {
                        "role": "user",
                        "content": (application.job_content or "")
                        + (f" Repair {repair_code}" if repair_code else ""),
                    },
                ],
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
                "stream": False,
                "reasoning_effort": "high",
                "thinking": {"type": "enabled"},
            }
            return PreparedAnalysisCall(
                endpoint="https://api.deepseek.com/v1/chat/completions",
                model="deepseek-v4-flash",
                max_output_tokens=8000,
                rendered_request=json.dumps(
                    document, separators=(",", ":")
                ).encode(),
                opaque=None,
            )

        async def transmit(self, _prepared):
            self.started.set()
            await asyncio.to_thread(self.release.wait)
            return AnalysisModelResponse(
                payload={
                    "summary": ["One.", "Two.", "Three."],
                    "skillSignals": [
                        {
                            "name": "React",
                            "category": "framework_library",
                            "importance": "required",
                            "evidence": "React",
                        },
                        {
                            "name": "REST APIs",
                            "category": "api_integration",
                            "importance": "preferred",
                            "evidence": "REST APIs",
                        },
                        {
                            "name": "Automated tests",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated tests",
                        },
                    ],
                },
                call_evidence=AnalysisCallEvidence(
                    transmission_state="sent",
                    finish_reason="stop",
                    model_id="deepseek-v4-flash",
                    request_id="blocking-request",
                    input_tokens=100,
                    output_tokens=200,
                    total_tokens=300,
                    cache_hit_input_tokens=0,
                ),
            )

        async def generate(self, application, *, repair_code=None):
            return await self.transmit(self.prepare(application, repair_code=repair_code))

    model = BlockingModel()
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_model=model,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "inflight-cancel"},
            json={"target": 1},
        )
        run_id = accepted.json()["run"]["runId"]
        assert model.started.wait(timeout=2)

        cancelling = client.post(
            f"/api/v1/applications/analysis/runs/{run_id}/cancel"
        )
        assert cancelling.json()["run"]["lifecycle"] == "cancelling"
        model.release.set()

        finished = _eventually_finished(client, run_id)

    assert finished["outcome"] == "cancelled"
    assert finished["progress"]["completions"] == 1
    assert finished["progress"]["evaluated"] == 1
    assert finished["candidates"][0]["state"] == "analyzed"
    assert finished["candidates"][1]["state"] == "pending"
    assert finished["spend"]["verifiedCostMicros"] > 0


def test_cancel_during_unreconcilable_inflight_call_retains_reservation(tmp_path):
    class IndeterminateError(RuntimeError):
        code = "provider_error"
        retryable = False
        call_evidence = AnalysisCallEvidence(transmission_state="indeterminate")

    class BlockingIndeterminateModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        async def transmit(self, _prepared):
            self.started.set()
            await asyncio.to_thread(self.release.wait)
            raise IndeterminateError("private provider failure")

    model = BlockingIndeterminateModel()
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_model=model,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "indeterminate-cancel"},
            json={"target": 2},
        )
        run_id = accepted.json()["run"]["runId"]
        assert model.started.wait(timeout=2)
        client.post(f"/api/v1/applications/analysis/runs/{run_id}/cancel")
        model.release.set()

        finished = _eventually_finished(client, run_id)

    assert finished["outcome"] == "cancelled"
    assert finished["progress"]["completions"] == 0
    assert finished["progress"]["indeterminate"] == 1
    assert finished["candidates"][0]["state"] == "indeterminate"
    assert finished["candidates"][1]["state"] == "pending"
    assert finished["spend"]["indeterminateReservationMicros"] > 0
    assert (
        finished["spend"]["committedMicros"]
        == finished["spend"]["indeterminateReservationMicros"]
    )


def test_restart_resumes_cancelling_without_scheduling_work(tmp_path):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    settings = _settings(tmp_path)
    state_path = tmp_path / "workspace.json"
    first_app = create_test_app(
        settings,
        state_path=state_path,
        analysis_worker=DormantWorker(),
    )
    with TestClient(first_app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "restart-cancelling"},
            json={"target": 2},
        )
        run_id = accepted.json()["run"]["runId"]
        client.post(f"/api/v1/applications/analysis/runs/{run_id}/cancel")

    fresh_app = create_test_app(settings, state_path=state_path)
    with TestClient(fresh_app) as client:
        finished = _eventually_finished(client, run_id)

    assert finished["outcome"] == "cancelled"
    assert finished["progress"]["evaluated"] == 0
    assert finished["spend"]["committedMicros"] == 0


def test_fresh_app_instance_resumes_same_queued_run_and_candidate_set(tmp_path):
    class DormantWorker:
        def start(self):
            return None

        def wake(self):
            return None

        async def stop(self):
            return None

    settings = _settings(tmp_path)
    state_path = tmp_path / "workspace.json"
    first_app = create_test_app(
        settings,
        state_path=state_path,
        analysis_worker=DormantWorker(),
    )
    with TestClient(first_app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "restart-queued"},
            json={"target": 2},
        ).json()["run"]

    fresh_app = create_test_app(settings, state_path=state_path)
    with TestClient(fresh_app) as client:
        reloaded = client.get(
            f"/api/v1/applications/analysis/runs/{accepted['runId']}"
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert reloaded["runId"] == accepted["runId"]
    assert [item["applicationId"] for item in reloaded["candidates"]] == [
        item["applicationId"] for item in accepted["candidates"]
    ]
    assert finished["outcome"] == "target_met"
    assert finished["progress"]["completions"] == 2


def test_public_run_reports_attempt_budget_exhaustion(tmp_path):
    class TruncatedQueueWorkspace(FakeWorkspace):
        async def load_analysis_queue_snapshot(
            self, *, excluded_application_ids=frozenset()
        ):
            candidates = await super().load_analysis_queue_snapshot(
                excluded_application_ids=excluded_application_ids
            )
            return candidates + (
                dataclass_replace(
                    candidates[-1],
                    id="app-synthetic-extra",
                    url="https://notion.test/app-synthetic-extra",
                    job_url="https://example.test/jobs/synthetic-extra",
                ),
            )

    class InvalidOutputModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.calls = 0

        async def transmit(self, _prepared):
            self.calls += 1
            return AnalysisModelResponse(
                payload={"summary": ["Only one."], "skillSignals": []},
                call_evidence=AnalysisCallEvidence(
                    transmission_state="sent",
                    finish_reason="stop",
                    model_id="deepseek-v4-flash",
                    request_id=f"invalid-{self.calls}",
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
                    cache_hit_input_tokens=0,
                ),
            )

    model = InvalidOutputModel()
    app = create_test_app(
        _settings(tmp_path),
        workspace=TruncatedQueueWorkspace(tmp_path / "workspace.json"),
        state_path=tmp_path / "workspace.json",
        analysis_model=model,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "attempt-budget"},
            json={"target": 1},
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert finished["outcome"] == "attempt_budget_exhausted"
    assert finished["progress"]["failed"] == 2
    assert finished["progress"]["evaluated"] == 2
    assert model.calls == 6


def test_public_run_maps_authorization_spend_and_systemic_failures(tmp_path):
    class OutcomePolicy:
        def __init__(self, outcome):
            self.outcome = outcome

        def estimate(self, **request):
            if self.outcome == "authorization_blocked":
                raise AnalysisAuthorizationBlocked(
                    "model_not_approved", "The model is not approved."
                )
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
                worst_case_micros=(
                    500_001 if self.outcome == "spend_limited" else 10_000
                ),
            )

        def settle(self, _estimate, _receipt):
            return AnalysisSettlement(False, None, "missing")

    class SystemicError(RuntimeError):
        code = "provider_unavailable"
        retryable = True

        def __init__(self):
            super().__init__("private provider failure")
            self.call_evidence = AnalysisCallEvidence(transmission_state="sent")

    class SystemicModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.calls = 0

        async def transmit(self, _prepared):
            self.calls += 1
            raise SystemicError()

    observed = {}
    for expected in ("authorization_blocked", "spend_limited", "failed"):
        case_path = tmp_path / expected
        model = (
            SystemicModel()
            if expected == "failed"
            else FakeApplicationAnalysisModel()
        )
        app = create_test_app(
            _settings(case_path),
            state_path=case_path / "workspace.json",
            analysis_model=model,
            analysis_spend_policy=OutcomePolicy(expected),
        )
        with TestClient(app) as client:
            accepted = client.post(
                "/api/v1/applications/analysis/run",
                headers={"Idempotency-Key": f"outcome-{expected}"},
                json={"target": 1},
            ).json()["run"]
            observed[expected] = _eventually_finished(
                client, accepted["runId"]
            )

    assert set(run["outcome"] for run in observed.values()) == {
        "authorization_blocked",
        "spend_limited",
        "failed",
    }
    assert observed["authorization_blocked"]["spend"]["committedMicros"] == 0
    assert observed["spend_limited"]["spend"]["committedMicros"] == 0
    assert observed["failed"]["spend"]["indeterminateReservationMicros"] > 0


@pytest.mark.parametrize("error_code", ["invalid_request", "provider_error"])
def test_shared_nonretryable_provider_errors_stop_before_the_next_candidate(
    tmp_path, error_code
):
    class SharedProviderError(RuntimeError):
        retryable = False

        def __init__(self):
            super().__init__("private provider failure")
            self.code = error_code
            self.call_evidence = AnalysisCallEvidence(
                transmission_state="sent"
            )

    class SharedFailureModel(FakeApplicationAnalysisModel):
        def __init__(self):
            self.calls = 0

        async def transmit(self, _prepared):
            self.calls += 1
            raise SharedProviderError()

    model = SharedFailureModel()
    app = create_test_app(
        _settings(tmp_path),
        state_path=tmp_path / "workspace.json",
        analysis_model=model,
    )

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": f"shared-{error_code}"},
            json={"target": 2},
        ).json()["run"]
        finished = _eventually_finished(client, accepted["runId"])

    assert finished["outcome"] == "failed"
    assert finished["progress"]["evaluated"] == 1
    assert model.calls == 1
