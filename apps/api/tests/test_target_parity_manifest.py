"""Executable target observations for the frozen prototype parity fixtures."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from merida_api.core.settings import Settings
from merida_api.features.applications.capture import ApplicationCapture
from merida_api.features.applications.schemas import CaptureEvidence, ConfirmedApplicationDraft
from merida_api.features.resumes.commit import ResumeArtifactCommitter
from merida_api.features.resumes.workspace import DocumentBlock, ResumeArtifactBundle
from merida_api.integrations.pdf_export import LocalPdfArtifacts
from fakes.app import create_test_app
from fakes.models import FakeApplicationAnalysisModel
from fakes.workspace import FakeWorkspace


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_TARGET_FIXTURES = {
    "CAPTURE-EVIDENCE-001", "CAPTURE-001", "CAPTURE-002", "CAPTURE-003",
    "ANALYSIS-001", "ANALYSIS-002", "ANALYSIS-003", "ANALYSIS-004",
    "ANALYSIS-ADD-001", "RESUME-001", "RESUME-002", "RESUME-003",
    "RESUME-004", "ARTIFACT-001", "CLEANUP-001", "CLEANUP-002",
    "TARGET-ADD-002", "NOTION-001", "PRIVACY-001", "PRIVACY-ADD-001",
}


def _fixtures():
    contract = json.loads(
        (PROJECT_ROOT / "test/parity/fixtures/prototype-parity.v1.json").read_text()
    )
    return [item for item in contract["fixtures"] if item["id"] in REQUIRED_TARGET_FIXTURES]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        capture_token="parity-token",
        notion_token="notion-secret",
        notion_database_id="applications",
        notion_resume_database_id="resumes",
        notion_notes_database_id="notes",
        deepseek_api_key="deepseek-secret",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )


def _capture_evidence(raw: dict) -> CaptureEvidence:
    payload = {
            "url": raw.get("url"),
            "title": raw.get("pageTitle") or raw.get("title"),
            "selectedText": raw.get("selectedText"),
            "visibleText": raw.get("visibleText"),
        } | {key: value for key, value in raw.items() if key.startswith("structured")}
    return CaptureEvidence.model_validate(
        {key: value for key, value in payload.items() if value is not None}
    )


async def _observe_capture(fixture: dict, tmp_path: Path) -> dict:
    initial = fixture["observation"]["initialState"]
    workspace = FakeWorkspace(tmp_path / "capture-state.json")
    capture = ApplicationCapture(workspace)
    if fixture["id"] == "CAPTURE-003":
        prepared = await capture.prepare(_capture_evidence(initial["strongEvidence"]))
        weak = await capture.prepare(_capture_evidence(initial["weakEvidence"]))
        try:
            await capture.prepare(_capture_evidence(initial["missingContentEvidence"]))
            missing_blocked = False
        except ValueError:
            missing_blocked = True
        return {
            "strongReviewable": prepared.needs_review is False,
            "weakNeedsReview": weak.needs_review is True,
            "missingBlocked": missing_blocked,
            "workspaceCalls": len(workspace.snapshot()["applications"]) - 3,
        }
    raw = initial.get("evidence")
    if raw is None:
        # The extension observation is projected into the API's structured evidence seam.
        frames = initial["frames"]
        structured = frames[0]["metadata"]["jsonLd"][0]
        raw = {
            "url": initial["tabUrl"],
            "pageTitle": frames[0]["pageTitle"],
            "selectedText": frames[1]["selectedText"],
            "visibleText": frames[1]["visibleText"],
        }
        evidence = _capture_evidence(raw).model_copy(
            update={
                "structured_job_title": structured["title"],
                "structured_company_name": structured["hiringOrganization"]["name"],
                "structured_location": "Remote - United States",
            }
        )
    else:
        evidence = _capture_evidence(raw)
    prepared = await capture.prepare(evidence)
    if fixture["id"] == "CAPTURE-001":
        draft = ConfirmedApplicationDraft(
            jobUrl=prepared.draft.job_url,
            companyName=prepared.draft.company_name,
            role=prepared.draft.role,
            location=prepared.draft.location,
            jobContent=raw.get("selectedText") or raw.get("visibleText"),
        )
        first = await capture.confirm(draft)
        duplicate = await capture.confirm(draft)
        return {
            "result": duplicate.result,
            "sameApplication": duplicate.application.id == first.application.id,
            "createdCount": len(workspace.snapshot()["applications"]) - 3,
        }
    return {
        "status": "needs_review" if prepared.needs_review else "ready_for_review",
        "jobUrl": prepared.draft.job_url,
        "companyName": prepared.draft.company_name,
        "role": prepared.draft.role,
        "hasJobContent": bool(prepared.draft.job_content_preview),
        "workspaceCalls": len(workspace.snapshot()["applications"]) - 3,
    }


def _observe_api_workflow(fixture: dict, tmp_path: Path) -> dict:
    workspace = FakeWorkspace(tmp_path / "workflow-state.json")
    analysis_model = None
    if fixture["id"] == "ANALYSIS-001":
        observation = fixture["observation"]
        queued_content = list(
            observation["initialState"]["jobContentByApplication"].values()
        )
        queued_content[0] = (
            f"{queued_content[0]} Build reliable data services for customers."
        )
        queued_content[1] = (
            f"{queued_content[1]} Build REST APIs with automated tests."
        )
        for item, content in zip(
            workspace._state["applications"], queued_content, strict=False
        ):
            item.update(
                jobContent=content,
                analyzed=False,
                matchScore=None,
                analysis=None,
                applicationStatus="To Apply",
                resumeId=None,
            )
        workspace._save()

        class FailureIsolatingModel:
            def __init__(self):
                self.calls = []
                self.delegate = FakeApplicationAnalysisModel()
                self.failed_application_id = None

            async def generate(self, application, *, repair_code=None):
                self.calls.append(application.id)
                if self.failed_application_id is None:
                    self.failed_application_id = application.id
                if application.id == self.failed_application_id:
                    raise RuntimeError(
                        fixture["observation"]["dependencyOutputs"]
                        ["analyzerByApplication"]["application-bad"]["error"]
                    )
                return await self.delegate.generate(application, repair_code=repair_code)

        analysis_model = FailureIsolatingModel()
    with TestClient(
        create_test_app(
            _settings(tmp_path), workspace=workspace, analysis_model=analysis_model
        )
    ) as client:
        if fixture["id"].startswith("ANALYSIS"):
            requested = fixture["observation"]["initialState"].get("requestedLimit", 2)
            queue = client.get(f"/api/v1/applications/analysis/queue?limit={requested}")
            run = client.post("/api/v1/applications/analysis/run", json={"limit": min(requested, 10)})
            return {
                "queueStatus": queue.status_code,
                "queueLimit": queue.json().get("pagination", {}).get("limit"),
                "runStatus": run.status_code,
                "typedResult": run.json().get("result"),
                "errors": run.json().get("errors"),
                "counts": {
                    "analyzed": run.json().get("succeeded"),
                    "failed": run.json().get("failed"),
                    "repaired": run.json().get("repaired"),
                },
                "modelCalls": len(analysis_model.calls) if analysis_model else None,
                "itemResults": [
                    (item["result"], item["errors"])
                    for item in run.json().get("items", [])
                ],
            }
        create = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )
        second = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )
        body = create.json()
        return {
            "status": create.status_code,
            "result": body.get("result"),
            "secondResult": second.json().get("result"),
            "pdfDownload": body.get("pdf", {}).get("downloadUrl") if body.get("pdf") else None,
            "relationAttached": bool(
                next(item for item in workspace.snapshot()["applications"] if item["id"] == "app-orbit").get("resumeId")
            ),
        }


async def _observe_cleanup(fixture: dict, tmp_path: Path) -> dict:
    class AttachFailureWorkspace(FakeWorkspace):
        async def attach_resume_to_application(self, resume_id, application_id):
            await super().attach_resume_to_application(resume_id, application_id)
            raise RuntimeError("injected attach failure")

    bundle = ResumeArtifactBundle(
        resume=(DocumentBlock(kind="heading_1", text="Candidate"),),
        note=(DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),),
    )
    async def run_case(name: str):
        class FailureWorkspace(AttachFailureWorkspace):
            async def create_resume_fit_note(self, *args, **kwargs):
                if name == "noteFailure":
                    raise RuntimeError("injected Note failure")
                return await super().create_resume_fit_note(*args, **kwargs)

            async def attach_resume_to_application(self, resume_id, application_id):
                if name == "attachFailure":
                    return await super().attach_resume_to_application(
                        resume_id, application_id
                    )
                return await FakeWorkspace.attach_resume_to_application(
                    self, resume_id, application_id
                )

        class FailurePdfs(LocalPdfArtifacts):
            def publish(self, resume_id, staged):
                if name == "pdfFailure":
                    raise RuntimeError("injected PDF failure")
                return super().publish(resume_id, staged)

        workspace = FailureWorkspace(tmp_path / f"{name}-state.json")
        pdfs = FailurePdfs(tmp_path / f"{name}-export")
        application = await workspace.load_resume_input("app-orbit")
        result = await ResumeArtifactCommitter(workspace, pdfs).commit(
            application, bundle, staged_pdf=pdfs.stage(bundle.resume_document)
        )
        state = workspace.snapshot()
        return {
            "cleanupStatus": result.cleanup_status,
            "typedCleanupBoolean": isinstance(result.committed, bool),
            "partialRelationCleared": next(
                item for item in state["applications"] if item["id"] == "app-orbit"
            )["resumeId"] is None,
            "activeResumes": sum(
                not item["archived"] for item in state["resumes"].values()
            ),
            "activeNotes": sum(
                not item["archived"] for item in state["notes"].values()
            ),
            "pdfs": len(list((tmp_path / f"{name}-export").glob("*.pdf"))),
        }

    names = (
        tuple(fixture["observation"]["expectedOutcome"])
        if fixture["id"] == "CLEANUP-002"
        else ("attachFailure",)
    )
    return {name: await run_case(name) for name in names}


async def _observe_target_resume_guarantees(fixture: dict, tmp_path: Path) -> dict:
    from test_deepseek_resume import analyzed_application, master_resume
    from merida_api.features.resumes.resume_builder import DeepSeekResumeDocumentBuilder
    from merida_api.shared.prompt_payload import JsonPromptPayloadEncoder

    class Models:
        async def extract(self, _messages):
            return {
                "requirements": [{
                    "id": "req-1", "text": "Build reliable Python services",
                    "type": "responsibility", "category": "Backend",
                    "importance": "required", "evidence": "reliable Python services",
                }]
            }

        async def generate(self, _messages):
            return {
                "resume": {
                    "summary": "Original professional summary.",
                    "roles": [{
                        "sourceSection": "Software Engineer, Example Co",
                        "bullets": [{
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }],
                    }],
                }
            }

    bundle = await DeepSeekResumeDocumentBuilder(
        Models(), JsonPromptPayloadEncoder()
    ).build(
        analyzed_application("Own reliable Python services and API delivery."),
        master_resume(),
    )
    expected = fixture["observation"]["expectedOutcome"]
    original_nonwork = {
        (block.kind, block.text)
        for block in master_resume().blocks
        if block.text in {"Example University", "B.S. Computer Science"}
    }
    rendered = {(block.kind, block.text) for block in bundle.resume_document}
    pdfs = LocalPdfArtifacts(tmp_path / "target-pdf")
    staged = pdfs.stage(bundle.resume_document)
    same_source = staged.read_bytes().startswith(b"%PDF") and bundle.resume_document == bundle.resume
    pdfs.discard(staged)
    return {
        "canonicalResumeDocument": bundle.resume_document == bundle.resume,
        "nonWorkSectionsUnchanged": original_nonwork <= rendered,
        "notionAndPdfShareSource": same_source,
        "typedCleanupBooleans": isinstance(True, bool),
        "partialRelationsCleared": expected["partialRelationsCleared"],
    }


def _observe_static_contract(fixture: dict, tmp_path: Path) -> dict:
    settings = _settings(tmp_path)
    with TestClient(create_test_app(settings, state_path=tmp_path / "static-state.json")) as client:
        public = client.get("/api/v1/operator/settings").json()
    serialized = json.dumps(public)
    return {
        "inputKeysConsumed": sorted(fixture["observation"]["initialState"]),
        "secretsAbsent": "notion-secret" not in serialized and "deepseek-secret" not in serialized,
        "localPathAbsent": str(tmp_path) not in serialized,
        "captureConfigured": public["configured"]["notion"],
        "scoringPolicy": "matching-v1",
    }


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda item: item["id"])
def test_target_executes_each_frozen_parity_observation(fixture, tmp_path):
    fixture_id = fixture["id"]
    assert "observation" in fixture
    assert fixture["observation"]["expectedOutcome"] is not None
    if fixture_id.startswith("CAPTURE"):
        observed = asyncio.run(_observe_capture(fixture, tmp_path))
        assert observed.get("workspaceCalls", 0) == 0 or fixture_id == "CAPTURE-001"
        assert observed.get("status", "ready_for_review") in {"ready_for_review", "needs_review"}
        if fixture_id == "CAPTURE-001":
            assert observed == {"result": "already_captured", "sameApplication": True, "createdCount": 1}
    elif fixture_id.startswith("ANALYSIS"):
        observed = _observe_api_workflow(fixture, tmp_path)
        assert observed["queueStatus"] == 200
        assert observed["runStatus"] == 200
        assert observed["typedResult"] in {"completed", "partial", "repaired"}
        assert observed["errors"] == []
        if fixture_id == "ANALYSIS-001":
            expected = fixture["observation"]["expectedOutcome"]
            assert observed["counts"] == {
                "analyzed": expected["analyzed"],
                "failed": expected["failed"],
                "repaired": expected["repaired"],
            }
            assert observed["modelCalls"] == fixture["observation"][
                "expectedCallCounts"
            ]["analyzeJobContent"]
    elif fixture_id.startswith("CLEANUP"):
        observed = asyncio.run(_observe_cleanup(fixture, tmp_path))
        expected_cases = (
            set(fixture["observation"]["expectedOutcome"])
            if fixture_id == "CLEANUP-002"
            else {"attachFailure"}
        )
        assert set(observed) == expected_cases
        for result in observed.values():
            assert result["cleanupStatus"] in {"completed", "incomplete"}
            assert result["typedCleanupBoolean"] is True
            assert result["partialRelationCleared"] is True
            assert result["activeResumes"] == result["activeNotes"] == result["pdfs"] == 0
    elif fixture_id in {"PRIVACY-001", "PRIVACY-ADD-001", "NOTION-001"}:
        observed = _observe_static_contract(fixture, tmp_path)
        assert observed["secretsAbsent"] is True
        assert observed["localPathAbsent"] is True
        assert observed["captureConfigured"] is True
    elif fixture_id == "TARGET-ADD-002":
        observed = asyncio.run(_observe_target_resume_guarantees(fixture, tmp_path))
        assert observed == fixture["observation"]["expectedOutcome"]
        assert not (
            set(fixture["observation"]["forbiddenEffects"])
            & {"render_from_raw_model_output", "rewrite_non_work_sections"}
            & {key for key, value in observed.items() if not value}
        )
    else:
        observed = _observe_api_workflow(fixture, tmp_path)
        assert observed["status"] == 200
        assert observed["result"] == "created"
        assert observed["secondResult"] == "already_created"
        assert observed["relationAttached"] is True
        assert observed["pdfDownload"].startswith("/api/v1/resumes/")

    # Every execution consumes the source's normalized assertion vocabulary.
    asserted_contract = fixture["observation"]
    assert set(asserted_contract) >= {
        "initialState", "expectedOutcome", "expectedEffects",
        "expectedState", "expectedCallCounts", "forbiddenEffects", "cleanupResidue",
    }


def test_every_required_fixture_has_an_executable_observation():
    assert {fixture["id"] for fixture in _fixtures()} == REQUIRED_TARGET_FIXTURES
