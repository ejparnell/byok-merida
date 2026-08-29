import asyncio
from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient

from merida_api.core.settings import Settings
from merida_api.features.resumes.checkpoint_vault import (
    CheckpointAuthorityError,
    CheckpointBinding,
    EncryptedCheckpoint,
    ResumeCheckpointVault,
)
from merida_api.features.resumes.pdf_filename import resume_pdf_filename
from merida_api.features.resumes.resume_spend import ResumeRateCard, ResumeSpendPolicy
from merida_api.features.resumes.run_store import (
    ResumeSpendLimitReached,
    SqliteResumeRunStore,
)
from fakes.app import create_test_app


def test_resume_spend_approves_both_exact_stage_envelopes():
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    policy = ResumeSpendPolicy(ResumeRateCard.load(clock=lambda: now))

    def request(model: str, maximum: int, content: str) -> bytes:
        return json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": content},
            ],
            "max_tokens": maximum,
            "response_format": {"type": "json_object"},
            "stream": False,
            "reasoning_effort": "high",
            "thinking": {"type": "enabled"},
        }, ensure_ascii=False, separators=(",", ":")).encode()

    requirements = policy.estimate(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-flash",
        rendered_request=request("deepseek-v4-flash", 8_000, "Python café"),
        max_output_tokens=8_000,
    )
    draft = policy.estimate(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-pro",
        rendered_request=request("deepseek-v4-pro", 16_000, "Evidence"),
        max_output_tokens=16_000,
    )

    assert requirements.worst_case_micros >= 2_240
    assert draft.worst_case_micros >= 13_920
    assert requirements.approval_fingerprint != draft.approval_fingerprint


def test_resume_ledger_admits_exact_remaining_budget_and_persists(tmp_path):
    path = tmp_path / "resume-runs.sqlite3"
    store = SqliteResumeRunStore(path)
    store.start(
        run_id="run-1",
        idempotency_key="start-1",
        target=1,
        candidates=[("app-1", "Engineer at Example")],
        queue_exhausted=True,
    )
    store.begin("run-1")
    store.reserve_call(
        call_id="call-1", run_id="run-1", application_id="app-1",
        stage="requirements", attempt=1, reservation_micros=1_000_000,
        approval_fingerprint="approval", request_fingerprint="request",
        authorization={"model": "deepseek-v4-flash"},
    )
    with pytest.raises(ResumeSpendLimitReached):
        store.reserve_call(
            call_id="call-2", run_id="run-1", application_id="app-1",
            stage="requirements", attempt=2, reservation_micros=1,
            approval_fingerprint="approval", request_fingerprint="request-2",
            authorization={"model": "deepseek-v4-flash"},
        )

    reloaded = SqliteResumeRunStore(path).get("run-1")
    assert reloaded["spend"]["committedMicros"] == 1_000_000
    assert reloaded["spend"]["remainingAuthorizedMicros"] == 0
    assert "Python café" not in path.read_bytes().decode("utf-8", errors="ignore")


def test_resume_run_public_seam_is_durable_and_legacy_writer_is_removed(tmp_path):
    settings = Settings(
        user_name="Test User",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
        resume_run_store_path=tmp_path / "resume-runs.sqlite3",
    )
    with TestClient(create_test_app(settings, state_path=tmp_path / "workspace.json")) as client:
        accepted = client.post(
            "/api/v1/resumes/runs",
            headers={"Idempotency-Key": "resume-start-1"},
            json={"target": 1},
        )
        run_id = accepted.json()["run"]["runId"]
        for _ in range(100):
            observed = client.get(f"/api/v1/resumes/runs/{run_id}").json()["run"]
            if observed["lifecycle"] == "finished":
                break
            asyncio.run(asyncio.sleep(0))

        assert accepted.status_code == 202
        assert observed["outcome"] == "target_met"
        assert observed["progress"]["completions"] == 1
        assert observed["spend"]["ceilingMicros"] == 1_000_000
        assert client.post("/api/v1/resumes/create", json={"applicationId": "app-orbit"}).status_code == 404
        artifact = observed["candidates"][0]["completion"]
        pdf = client.get(artifact["pdf"]["downloadUrl"])
        assert pdf.status_code == 200
        assert pdf.headers["cache-control"] == "no-store"


def test_resume_pdf_filename_normalizes_and_bounds_components():
    assert resume_pdf_filename(" Acme, Inc. ", "Senior / Engineer", "Élise") == (
        "Acme-Inc-Senior-Engineer-Élise.pdf"
    )
    assert len(resume_pdf_filename("界" * 40, "Role", "User").encode()) <= 198


def test_resume_checkpoint_vault_authenticates_identity_and_tampering():
    vault = ResumeCheckpointVault({"key-1": b"x" * 32}, current_key_version="key-1")
    binding = CheckpointBinding(
        kind="master_source", schema_version=1, run_id="run-1", source_proof="proof-1"
    )
    sealed = vault.seal(binding, {"private": "Master Resume content"})

    assert len(sealed.nonce) == 12
    assert b"Master Resume content" not in sealed.ciphertext
    assert vault.open(binding, sealed) == {"private": "Master Resume content"}

    with pytest.raises(CheckpointAuthorityError):
        vault.open(
            CheckpointBinding(
                kind="master_source",
                schema_version=1,
                run_id="run-2",
                source_proof="proof-1",
            ),
            sealed,
        )
    with pytest.raises(CheckpointAuthorityError):
        vault.open(
            binding,
            EncryptedCheckpoint(
                sealed.key_version, sealed.nonce, sealed.ciphertext[:-1] + b"0"
            ),
        )
