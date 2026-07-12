import asyncio
import threading
import json

from fastapi.testclient import TestClient

from merida_api.core.settings import Settings
from merida_api.integrations.pdf_export import LocalPdfArtifacts
from merida_api.features.resumes.workspace import DocumentBlock
from merida_api.shared.recovery import JsonEffectJournal
from merida_api.cli import run_recovery_command
from fakes.app import create_test_app
from fakes.models import FakeApplicationAnalysisModel, FakeResumeDocumentBuilder
from fakes.workspace import FakeWorkspace, initial_test_state


class BlockingAnalysisModel:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self._delegate = FakeApplicationAnalysisModel()

    async def analyze(self, application):
        self.started.set()
        assert await asyncio.to_thread(self.release.wait, 5)
        return await self._delegate.analyze(application)


class BlockingResumeBuilder:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self._delegate = FakeResumeDocumentBuilder()

    async def build(self, application, master_resume):
        self.started.set()
        assert await asyncio.to_thread(self.release.wait, 5)
        return await self._delegate.build(application, master_resume)


def test_overlapping_analysis_run_fails_fast_with_conflict(tmp_path):
    model = BlockingAnalysisModel()
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(
        settings, state_path=tmp_path / "state.json", analysis_model=model
    )
    first_result = {}

    with TestClient(app) as client:
        thread = threading.Thread(
            target=lambda: first_result.update(
                response=client.post(
                    "/api/v1/applications/analysis/run", json={"limit": 1}
                )
            )
        )
        thread.start()
        assert model.started.wait(timeout=5)

        overlapping = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )
        model.release.set()
        thread.join(timeout=5)

    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "conflict"
    assert overlapping.json()["error"]["message"] == (
        "Job Posting Analysis is already in progress."
    )
    assert first_result["response"].status_code == 200
    assert first_result["response"].json()["result"] == "completed"


def test_effect_journal_persists_only_recovery_metadata_atomically(tmp_path):
    path = tmp_path / "effects.json"
    journal = JsonEffectJournal(path)

    entry = journal.start(
        workflow="resume_creation",
        domain_key="app-orbit",
        run_id="run-1",
    )
    journal.advance(entry.run_id, phase="resume_created", resume_id="resume-1")

    reloaded = JsonEffectJournal(path).unresolved(
        workflow="resume_creation", domain_key="app-orbit"
    )
    serialized = path.read_text()

    assert len(reloaded) == 1
    assert reloaded[0].phase == "resume_created"
    assert reloaded[0].resume_id == "resume-1"
    assert json.loads(serialized)["schemaVersion"] == 1
    assert "Job Content" not in serialized
    assert not path.with_suffix(".json.tmp").exists()


def test_overlapping_resume_creation_fails_fast_without_duplicate_artifacts(tmp_path):
    builder = BlockingResumeBuilder()
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(
        settings, state_path=tmp_path / "state.json", resume_builder=builder
    )
    first_result = {}

    with TestClient(app) as client:
        thread = threading.Thread(
            target=lambda: first_result.update(
                response=client.post(
                    "/api/v1/resumes/create",
                    json={"applicationId": "app-orbit"},
                )
            )
        )
        thread.start()
        assert builder.started.wait(timeout=5)
        overlapping = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )
        builder.release.set()
        thread.join(timeout=5)

    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "conflict"
    assert first_result["response"].json()["result"] == "created"


def test_restart_reconciles_unfinished_resume_effects_before_retry(tmp_path):
    state_path = tmp_path / "state.json"
    export_path = tmp_path / "export"
    journal_path = tmp_path / "recovery.json"
    workspace = FakeWorkspace(state_path)
    document = (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),)

    async def create_interrupted_effects():
        resume = await workspace.create_resume_draft(
            "Platform Engineer at Orbit Works", document
        )
        note = await workspace.create_resume_fit_note(
            "Resume Fit Analysis - Platform Engineer at Orbit Works",
            application_id="app-orbit",
            resume_id=resume.id,
            document=document,
        )
        return resume, note

    resume, note = asyncio.run(create_interrupted_effects())
    LocalPdfArtifacts(export_path).save(resume.id, ("Interrupted PDF",))
    journal = JsonEffectJournal(journal_path)
    journal.start(
        workflow="resume_creation", domain_key="app-orbit", run_id="run-crashed"
    )
    journal.advance(
        "run-crashed",
        phase="note_created",
        application_id="app-orbit",
        resume_id=resume.id,
        note_id=note.id,
        pdf_id=resume.id,
    )
    settings = Settings(
        export_path=export_path,
        recovery_journal_path=journal_path,
    )

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        retried = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert retried.status_code == 200
    assert retried.json()["result"] == "created"
    assert retried.json()["resume"]["id"] != resume.id
    assert not JsonEffectJournal(journal_path).unresolved(
        workflow="resume_creation", domain_key="app-orbit"
    )
    assert LocalPdfArtifacts(export_path).path(resume.id) is None


def test_retry_after_uncertain_capture_result_returns_existing_application(tmp_path):
    class LostCaptureResponseWorkspace(FakeWorkspace):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lose_response = True

        async def create_application(self, *args, **kwargs):
            created = await super().create_application(*args, **kwargs)
            if self.lose_response:
                self.lose_response = False
                raise RuntimeError("response was lost after the write")
            return created

    state_path = tmp_path / "state.json"
    journal_path = tmp_path / "recovery.json"
    settings = Settings(
        capture_token="capture-token",
        export_path=tmp_path / "export",
        recovery_journal_path=journal_path,
    )
    workspace = LostCaptureResponseWorkspace(state_path)
    payload = {
        "draft": {
            "jobUrl": "https://example.test/jobs/recovery",
            "companyName": "Recovery Labs",
            "role": "Platform Engineer",
            "location": None,
            "jobContent": "Build reliable Python services and React interfaces.",
        }
    }
    headers = {"X-Capture-Token": "capture-token"}

    with TestClient(
        create_test_app(settings, workspace=workspace),
        raise_server_exceptions=False,
    ) as client:
        uncertain = client.post(
            "/api/v1/applications/confirm", json=payload, headers=headers
        )
        retried = client.post(
            "/api/v1/applications/confirm", json=payload, headers=headers
        )

    assert uncertain.status_code == 500
    assert retried.status_code == 200
    assert retried.json()["result"] == "already_captured"
    assert not JsonEffectJournal(journal_path).unresolved(
        workflow="capture", domain_key="https://example.test/jobs/recovery"
    )


def test_analysis_skips_an_application_that_becomes_ineligible_after_selection(tmp_path):
    class EligibilityChangesWorkspace(FakeWorkspace):
        async def list_analysis_queue(self, *, limit, cursor):
            page = await super().list_analysis_queue(limit=limit, cursor=cursor)
            selected = page.items[0]
            application = await self._mutable_application(selected.id)
            application["applicationStatus"] = "Applied"
            self._save()
            return page

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = EligibilityChangesWorkspace(tmp_path / "state.json")

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )

    assert response.status_code == 200
    assert response.json()["processed"] == 1
    assert response.json()["succeeded"] == 0
    assert response.json()["failed"] == 0
    assert response.json()["items"][0]["result"] == "skipped"


def test_recovery_command_inspects_and_requires_confirmation_to_acknowledge(
    tmp_path, capsys
):
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    journal = JsonEffectJournal(settings.recovery_journal_path)
    journal.start(
        workflow="resume_creation", domain_key="app-orbit", run_id="run-manual"
    )

    assert run_recovery_command(settings, "inspect") == 0
    inspection = capsys.readouterr().out
    assert "run-manual" in inspection
    assert "resume_creation" in inspection
    assert run_recovery_command(
        settings, "acknowledge", run_id="run-manual", confirmed=False
    ) == 2
    assert JsonEffectJournal(settings.recovery_journal_path).unresolved()

    assert run_recovery_command(
        settings, "acknowledge", run_id="run-manual", confirmed=True
    ) == 0
    assert not JsonEffectJournal(settings.recovery_journal_path).unresolved()


def test_restart_keeps_an_ambiguous_resume_create_window_for_manual_recovery(
    tmp_path,
):
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    journal = JsonEffectJournal(settings.recovery_journal_path)
    journal.start(
        workflow="resume_creation",
        domain_key="app-orbit",
        run_id="run-ambiguous",
    )

    with TestClient(
        create_test_app(settings, state_path=tmp_path / "state.json")
    ) as client:
        response = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    unresolved = JsonEffectJournal(settings.recovery_journal_path).unresolved(
        workflow="resume_creation", domain_key="app-orbit"
    )
    assert unresolved[0].cleanup_status == "incomplete"


def test_incomplete_unjournaled_capture_is_a_manual_recovery_conflict(tmp_path):
    state = initial_test_state()
    application = state["applications"][0]
    application["jobUrl"] = "https://example.test/jobs/incomplete"
    application["jobContent"] = "partial"
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    settings = Settings(
        capture_token="capture-token",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, state_path=state_path)) as client:
        response = client.post(
            "/api/v1/applications/confirm",
            headers={"X-Capture-Token": "capture-token"},
            json={
                "draft": {
                    "jobUrl": "https://example.test/jobs/incomplete",
                    "companyName": "Example",
                    "role": "Engineer",
                    "location": None,
                    "jobContent": "Build reliable Python services and React interfaces.",
                }
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_unverified_resume_artifacts_remain_blocked_for_manual_recovery(tmp_path):
    class UnverifiedWorkspace(FakeWorkspace):
        async def verify_recovery_artifacts(self, **_kwargs):
            return False

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    journal = JsonEffectJournal(settings.recovery_journal_path)
    journal.start(
        workflow="resume_creation",
        domain_key="app-orbit",
        run_id="run-unverified",
    )
    journal.advance(
        "run-unverified", phase="resume_created", resume_id="resume-unknown"
    )
    workspace = UnverifiedWorkspace(tmp_path / "state.json")

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        response = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert response.status_code == 409
    unresolved = JsonEffectJournal(settings.recovery_journal_path).unresolved()
    assert unresolved[0].cleanup_status == "incomplete"


def test_corrupt_recovery_journal_keeps_health_available_and_blocks_mutations(
    tmp_path,
):
    journal_path = tmp_path / "recovery.json"
    journal_path.write_text("{")
    settings = Settings(
        capture_token="capture-token",
        export_path=tmp_path / "export",
        recovery_journal_path=journal_path,
    )

    with TestClient(
        create_test_app(settings, state_path=tmp_path / "state.json")
    ) as client:
        health = client.get("/api/v1/health")
        capture = client.post(
            "/api/v1/applications/confirm",
            headers={"X-Capture-Token": "capture-token"},
            json={
                "draft": {
                    "jobUrl": "https://example.test/jobs/blocked",
                    "companyName": "Example",
                    "role": "Engineer",
                    "location": None,
                    "jobContent": "Build reliable Python services and React interfaces.",
                }
            },
        )
        resume = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert health.status_code == 200
    assert health.json()["status"] == "blocked"
    assert capture.status_code == 200
    assert capture.json()["result"] == "blocked"
    assert resume.status_code == 200
    assert resume.json()["result"] == "blocked"
    assert journal_path.read_text() == "{"
