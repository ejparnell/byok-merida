import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import Response

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.features.applications.workspace import AnalysisModelResponse
from merida_api.features.applications.schemas import ConfirmedApplicationDraft
from merida_api.shared.workspace import (
    WorkspaceIssue,
    WorkspaceProviderError,
    WorkspaceReadiness,
)
from fakes.app import create_test_app
from fakes.models import FakeApplicationAnalysisModel
from fakes.workspace import FakeWorkspace, initial_test_state


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def make_client(tmp_path, **overrides):
    settings = Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
        **overrides,
    )
    return TestClient(create_test_app(settings, state_path=tmp_path / "state.json"))


def _start_analysis_run(
    client: TestClient, *, target: int, idempotency_key: str
) -> tuple[Response, dict]:
    response = client.post(
        "/api/v1/applications/analysis/run",
        headers={"Idempotency-Key": idempotency_key},
        json={"target": target},
    )
    assert response.status_code == 202
    return response, response.json()["run"]


def _eventually_finished_analysis_run(
    client: TestClient, run_id: str
) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/applications/analysis/runs/{run_id}"
        )
        assert response.status_code == 200
        run = response.json()["run"]
        if run["lifecycle"] == "finished":
            return run
        time.sleep(0.005)
    raise AssertionError("Analysis Run did not finish within five seconds.")


def test_health_and_operator_settings_are_safe_and_ready(tmp_path):
    with make_client(tmp_path) as client:
        health = client.get("/api/v1/health").json()
        settings = client.get("/api/v1/operator/settings").json()

    assert health == {
        "ok": True,
        "status": "ready",
        "service": "merida-api",
        "checks": {
            "settings": "ready",
            "notion": "ready",
            "analysis": "ready",
            "resumes": "ready",
        },
        "validationFailures": [],
        "errors": [],
    }
    assert settings["models"] == {
        "analysis": "deepseek-v4-flash",
        "resumes": "deepseek-v4-pro",
    }
    assert "captureToken" not in settings
    assert "notionToken" not in settings


@pytest.mark.parametrize("user_name", ["", "YourName", "!!!"])
def test_missing_user_name_blocks_resume_creation_readiness(tmp_path, user_name):
    with make_client(tmp_path, user_name=user_name) as client:
        health = client.get("/api/v1/health").json()
        created = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        ).json()

    assert health["checks"]["resumes"] == "blocked"
    assert "USER_NAME is not configured." in health["errors"]
    assert created["result"] == "blocked"
    assert created["errors"] == ["USER_NAME is not configured."]


def test_health_openapi_uses_a_named_discriminated_response(tmp_path):
    with make_client(tmp_path) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/health"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]

    assert operation["operationId"] == "getHealth"
    assert response_schema == {"$ref": "#/components/schemas/HealthResponse"}
    health_schema = schema["components"]["schemas"]["HealthResponse"]
    assert set(health_schema["required"]) == {
        "ok",
        "status",
        "service",
        "checks",
        "validationFailures",
        "errors",
    }


def test_public_contract_has_one_real_runtime_and_no_demo_surface(tmp_path):
    with make_client(tmp_path) as client:
        health = client.get("/api/v1/health").json()
        operator_settings = client.get("/api/v1/operator/settings").json()
        schema = client.get("/openapi.json").json()
        removed_reset = client.post("/api/v1/demo/reset")

    assert "mode" not in health
    assert "mode" not in operator_settings
    assert "workspace" not in operator_settings
    assert "/api/v1/demo/reset" not in schema["paths"]
    assert "ResetDemoResponse" not in schema["components"]["schemas"]
    assert "demo_not_active" not in schema["components"]["schemas"][
        "ApiErrorDetail"
    ]["properties"]["code"]["enum"]
    assert removed_reset.status_code == 404
    assert removed_reset.json()["error"]["code"] == "not_found"


def test_resume_schema_failure_does_not_block_capture_or_analysis(tmp_path):
    class IncompatibleWorkspace(FakeWorkspace):
        async def validate_resume_workspace(self):
            return WorkspaceReadiness(
                errors=(
                    WorkspaceIssue(
                        database="resumes",
                        property="Job Posting",
                        message="Required relation property is missing.",
                    ),
                )
            )

    settings = Settings(
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(
        settings,
        workspace=IncompatibleWorkspace(tmp_path / "state.json"),
    )

    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()

    assert health["status"] == "blocked"
    assert health["checks"]["notion"] == "ready"
    assert health["checks"]["analysis"] == "ready"
    assert health["checks"]["resumes"] == "blocked"
    assert health["validationFailures"] == [
        {
            "kind": "workspace_schema",
            "database": "resumes",
            "property": "Job Posting",
            "message": "Required relation property is missing.",
        }
    ]


def test_runtime_rejects_non_loopback_api_hosts():
    with pytest.raises(ValueError, match="loopback"):
        Settings(api_host="0.0.0.0")


def test_default_capture_token_is_not_treated_as_configured(tmp_path):
    settings = Settings(
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, state_path=tmp_path / "state.json")) as client:
        response = client.post(
            "/api/v1/applications/prepare",
            headers={"X-Capture-Token": "local-capture-token"},
            json={
                "evidence": {
                    "url": "https://example.test/jobs/1",
                    "visibleText": "Build reliable Python services and React interfaces.",
                }
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_capture_token"


def test_documented_capture_token_placeholders_are_not_configured():
    for token in (
        "local-capture-token",
        "choose-a-local-shared-token",
        "your-capture-token",
    ):
        assert Settings(capture_token=token).capture_token_configured is False


def test_provider_outages_return_typed_workflow_blocks(tmp_path):
    class UnavailableWorkspace(FakeWorkspace):
        async def validate_capture_workspace(self):
            raise WorkspaceProviderError("Notion could not be reached.")

        async def list_active_applications(self):
            raise WorkspaceProviderError("Notion could not be reached.")

        async def validate_analysis_workspace(self):
            raise WorkspaceProviderError("Notion could not be reached.")

        async def validate_resume_workspace(self):
            raise WorkspaceProviderError("Notion could not be reached.")

    settings = Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(
        settings,
        workspace=UnavailableWorkspace(tmp_path / "state.json"),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        blocked_responses = (
            client.get(
                "/api/v1/applications/capture-matches",
                params={"companyName": "Example", "role": "Engineer"},
                headers={"X-Capture-Token": "test-capture-token"},
            ),
            client.post(
                "/api/v1/applications/confirm",
                headers={"X-Capture-Token": "test-capture-token"},
                json={
                    "draft": {
                        "jobUrl": "https://example.test/jobs/unavailable",
                        "companyName": "Example",
                        "role": "Engineer",
                        "location": None,
                        "jobContent": "Build reliable Python services and React interfaces.",
                    }
                },
            ),
            client.get("/api/v1/applications/analysis/queue"),
            client.get("/api/v1/resumes/queue"),
            client.post(
                "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
            ),
        )
        analysis_start = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "provider-outage"},
            json={"target": 1},
        )

    for response in blocked_responses:
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"
        assert response.json()["errors"] == ["Notion could not be reached."]
    assert analysis_start.status_code == 503
    assert (
        analysis_start.json()["error"]["code"]
        == "analysis_authorization_blocked"
    )
    assert "Notion could not be reached." not in analysis_start.text


def test_legacy_demo_settings_cannot_create_product_state(tmp_path):
    legacy_state_path = tmp_path / "demo" / "state.json"
    settings = Settings(
        merida_mode="demo",
        demo_state_path=legacy_state_path,
        demo_fixture_path=tmp_path / "demo" / "fixture.json",
        notion_token="",
        notion_database_id="",
        notion_resume_database_id="",
        notion_notes_database_id="",
        deepseek_api_key="",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").json()["status"] == "blocked"

    assert not legacy_state_path.exists()
    assert not legacy_state_path.parent.exists()


def test_capture_is_review_first_protected_and_idempotent(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}
    evidence = {
        "evidence": {
            "url": "https://example.com/jobs/42?utm_source=newsletter",
            "title": "Staff Frontend Engineer at Acme",
            "selectedText": "Acme is hiring a Staff Frontend Engineer. React and REST APIs are required.",
            "visibleText": "fallback page text",
        }
    }

    with make_client(tmp_path) as client:
        assert client.post("/api/v1/applications/prepare", json=evidence).status_code == 401
        prepared = client.post(
            "/api/v1/applications/prepare", json=evidence, headers=headers
        ).json()
        assert prepared["result"] == "prepared"
        assert prepared["draft"]["jobUrl"] == "https://example.com/jobs/42"
        assert "jobContent" not in prepared["draft"]

        confirm_payload = {
            "draft": {
                "jobUrl": prepared["draft"]["jobUrl"],
                "companyName": prepared["draft"]["companyName"],
                "role": prepared["draft"]["role"],
                "location": prepared["draft"]["location"],
                "jobContent": evidence["evidence"]["selectedText"],
            }
        }
        created = client.post(
            "/api/v1/applications/confirm", json=confirm_payload, headers=headers
        ).json()
        duplicate = client.post(
            "/api/v1/applications/confirm", json=confirm_payload, headers=headers
        ).json()

    assert created["result"] == "created"
    assert created["application"]["applicationStatus"] == "To Apply"
    assert duplicate["result"] == "already_captured"
    assert duplicate["application"]["id"] == created["application"]["id"]


def test_capture_matches_are_protected_typed_and_advisory(tmp_path):
    state_path = tmp_path / "state.json"
    workspace = FakeWorkspace(state_path)
    created = asyncio.run(
        workspace.create_application(
            ConfirmedApplicationDraft(
                jobUrl="https://jobs.example.test/acme/senior-engineer",
                companyName="Acme, Inc.",
                role="Senior Engineer",
                location=None,
                jobContent="Build reliable Python services and accessible React interfaces.",
            ),
            captured_at=datetime(2026, 7, 15),
        )
    )
    settings = Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(settings, workspace=workspace)
    params = {"companyName": "ACME LLC", "role": "Sr. Engineer"}

    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/applications/capture-matches", params=params)
        matched = client.get(
            "/api/v1/applications/capture-matches",
            params=params,
            headers={"X-Capture-Token": "test-capture-token"},
        )
        unmatched = client.get(
            "/api/v1/applications/capture-matches",
            params={"companyName": "New Company", "role": "Engineer"},
            headers={"X-Capture-Token": "test-capture-token"},
        )

    assert unauthorized.status_code == 401
    assert matched.status_code == 200
    assert matched.json() == {
        "ok": True,
        "result": "matched",
        "matches": [
            {
                "id": created.id,
                "title": "Senior Engineer at Acme, Inc.",
                "companyName": "Acme, Inc.",
                "role": "Senior Engineer",
                "applicationStatus": "To Apply",
                "url": created.url,
            }
        ],
        "validationFailures": [],
        "errors": [],
    }
    assert unmatched.json() == {
        "ok": True,
        "result": "unmatched",
        "matches": [],
        "validationFailures": [],
        "errors": [],
    }


def test_capture_matches_block_on_capture_workspace_validation_failures(tmp_path):
    class IncompatibleWorkspace(FakeWorkspace):
        async def validate_capture_workspace(self):
            return WorkspaceReadiness(
                errors=(
                    WorkspaceIssue(
                        database="applications",
                        property="Company Name",
                        message="Required title property is missing.",
                    ),
                )
            )

    settings = Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    app = create_test_app(
        settings,
        workspace=IncompatibleWorkspace(tmp_path / "state.json"),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/applications/capture-matches",
            params={"companyName": "Acme", "role": "Engineer"},
            headers={"X-Capture-Token": "test-capture-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "status": "blocked",
        "result": "blocked",
        "matches": [],
        "validationFailures": [
            {
                "kind": "workspace_schema",
                "database": "applications",
                "property": "Company Name",
                "message": "Required title property is missing.",
            }
        ],
        "errors": ["Required title property is missing."],
    }


def test_capture_contract_is_named_reviewable_and_safe(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}
    incomplete = {
        "evidence": {
            "url": "https://example.com/jobs/42",
            "title": "Staff Engineer",
            "visibleText": "Build reliable systems with Python and React.",
        }
    }

    with make_client(tmp_path) as client:
        schema = client.get("/openapi.json").json()
        response = client.post(
            "/api/v1/applications/prepare", json=incomplete, headers=headers
        )

    prepare_operation = schema["paths"]["/api/v1/applications/prepare"]["post"]
    confirm_operation = schema["paths"]["/api/v1/applications/confirm"]["post"]
    prepare_schema = prepare_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    confirm_schema = confirm_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert prepare_schema == {
        "$ref": "#/components/schemas/PrepareApplicationResponse"
    }
    assert confirm_schema == {
        "$ref": "#/components/schemas/ConfirmApplicationResponse"
    }
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": "needs_review",
        "draft": {
            "jobUrl": "https://example.com/jobs/42",
            "companyName": None,
            "role": "Staff Engineer",
            "location": None,
            "jobContentPreview": "Build reliable systems with Python and React.",
        },
        "needsReview": True,
        "reviewReasons": ["Company Name could not be parsed with enough confidence."],
        "missingFields": ["companyName"],
        "validationFailures": [],
        "errors": [],
    }


def test_analysis_and_resume_workflows_move_items_between_eligible_queues(tmp_path):
    with make_client(tmp_path) as client:
        analysis_queue = client.get(
            "/api/v1/applications/analysis/queue", params={"limit": 1}
        ).json()
        assert analysis_queue["queueCount"] >= 2
        assert len(analysis_queue["items"]) == 1
        assert analysis_queue["pagination"]["nextCursor"]

        next_page = client.get(
            "/api/v1/applications/analysis/queue",
            params={"limit": 1, "cursor": analysis_queue["pagination"]["nextCursor"]},
        ).json()
        assert next_page["items"][0]["applicationId"] != analysis_queue["items"][0]["applicationId"]

        accepted, initial = _start_analysis_run(
            client,
            target=1,
            idempotency_key="queue-movement",
        )
        run = _eventually_finished_analysis_run(client, initial["runId"])
        assert accepted.status_code == 202
        assert run["outcome"] == "target_met"
        assert run["progress"]["completions"] == 1
        assert run["progress"]["evaluated"] == 1
        assert run["candidates"][0]["state"] == "analyzed"

        resume_queue = client.get("/api/v1/resumes/queue", params={"limit": 10}).json()
        analyzed_id = run["candidates"][0]["applicationId"]
        assert analyzed_id in {item["applicationId"] for item in resume_queue["items"]}

        created = client.post(
            "/api/v1/resumes/create", json={"applicationId": analyzed_id}
        ).json()
        duplicate = client.post(
            "/api/v1/resumes/create", json={"applicationId": analyzed_id}
        ).json()
        assert created["result"] == "created"
        assert created["resume"]["url"]
        assert created["note"]["url"]
        assert created["pdf"]["downloadUrl"].startswith("/api/v1/resumes/")
        assert duplicate["result"] == "already_created"
        assert duplicate["resume"]["id"] == created["resume"]["id"]

        refreshed = client.get("/api/v1/resumes/queue", params={"limit": 10}).json()
        assert analyzed_id not in {item["applicationId"] for item in refreshed["items"]}


def test_already_created_resume_reports_a_missing_historical_pdf_as_null(tmp_path):
    with make_client(tmp_path) as client:
        resume_queue = client.get("/api/v1/resumes/queue", params={"limit": 1}).json()
        application_id = resume_queue["items"][0]["applicationId"]
        created = client.post(
            "/api/v1/resumes/create", json={"applicationId": application_id}
        ).json()
        download = client.get(created["pdf"]["downloadUrl"])
        (tmp_path / "export" / created["pdf"]["filename"]).unlink()
        missing_download = client.get(created["pdf"]["downloadUrl"])

        existing = client.post(
            "/api/v1/resumes/create", json={"applicationId": application_id}
        ).json()

    assert existing["result"] == "already_created"
    assert existing["pdf"] is None
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")
    assert missing_download.status_code == 404
    assert missing_download.json()["error"]["code"] == "pdf_not_found"


def test_created_resume_pdf_is_named_for_company_and_configured_user(tmp_path):
    with make_client(tmp_path, user_name="Elizabeth Parnell") as client:
        queue = client.get("/api/v1/resumes/queue", params={"limit": 10}).json()
        application = next(
            item for item in queue["items"] if item["companyName"] == "Orbit Works"
        )

        created = client.post(
            "/api/v1/resumes/create",
            json={"applicationId": application["applicationId"]},
        ).json()
        download = client.get(created["pdf"]["downloadUrl"])

    assert created["pdf"]["filename"] == "Orbit-Works-Elizabeth-Parnell.pdf"
    assert (tmp_path / "export" / created["pdf"]["filename"]).is_file()
    assert "Orbit-Works-Elizabeth-Parnell.pdf" in download.headers[
        "content-disposition"
    ]
    assert download.content.startswith(b"%PDF")


def test_already_created_resume_allows_missing_historical_note_and_pdf(tmp_path):
    state = initial_test_state()
    application = next(item for item in state["applications"] if item["id"] == "app-orbit")
    application["resumeId"] = "resume-historical"
    state["resumes"]["resume-historical"] = {
        "id": "resume-historical",
        "title": "Platform Engineer at Orbit Works",
        "url": "https://www.notion.so/test/resume-historical",
        "filename": "missing.pdf",
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, state_path=state_path)) as client:
        existing = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        ).json()

    assert existing["result"] == "already_created"
    assert existing["note"] is None
    assert existing["pdf"] is None


def test_existing_resume_is_returned_before_schema_or_eligibility_checks(tmp_path):
    class ExistingFirstWorkspace(FakeWorkspace):
        async def validate_resume_workspace(self):
            return WorkspaceReadiness(
                errors=(
                    WorkspaceIssue(
                        database="notes",
                        property="Resume",
                        message="Unrelated Notes schema defect.",
                    ),
                )
            )

        async def load_resume_input(self, application_id):
            raise AssertionError("eligibility must not run for an existing Resume")

    state = initial_test_state()
    application = next(item for item in state["applications"] if item["id"] == "app-orbit")
    application["applicationStatus"] = "Applied"
    application["resumeId"] = "resume-existing"
    state["resumes"]["resume-existing"] = {
        "id": "resume-existing",
        "title": "Platform Engineer at Orbit Works",
        "url": "https://www.notion.so/test/resume-existing",
        "applicationId": "app-orbit",
        "document": [],
        "archived": False,
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    workspace = ExistingFirstWorkspace(state_path)
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        response = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert response.status_code == 200
    assert response.json()["result"] == "already_created"
    assert response.json()["resume"]["id"] == "resume-existing"


def test_unconfigured_real_runtime_exposes_typed_blocked_outcomes(tmp_path):
    settings = Settings(
        capture_token="test-capture-token",
        notion_token="",
        notion_database_id="",
        notion_resume_database_id="",
        notion_notes_database_id="",
        deepseek_api_key="",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_app(settings)) as client:
        health = client.get("/api/v1/health")
        analysis_queue = client.get("/api/v1/applications/analysis/queue")
        analysis_run = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "unconfigured-runtime"},
            json={"target": 1},
        )
        confirm = client.post(
            "/api/v1/applications/confirm",
            headers={"X-Capture-Token": "test-capture-token"},
            json={
                "draft": {
                    "jobUrl": "https://example.test/job",
                    "companyName": "Example",
                    "role": "Engineer",
                    "location": None,
                    "jobContent": "Build reliable Python services and React interfaces.",
                }
            },
        )
        resume_queue = client.get("/api/v1/resumes/queue")
        resume = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert health.status_code == 200
    assert health.json()["status"] == "blocked"
    for queue in (analysis_queue, resume_queue):
        assert queue.status_code == 200
        assert queue.json()["status"] == "blocked"
        assert queue.json()["items"] == []
    assert analysis_run.status_code == 503
    assert analysis_run.json()["error"]["code"] == (
        "analysis_authorization_blocked"
    )
    assert confirm.status_code == 200
    assert confirm.json()["result"] == "blocked"
    assert resume.status_code == 200
    assert resume.json()["result"] == "blocked"
    assert resume.json()["cleanup"]["status"] == "not_required"


def test_analysis_repairs_existing_findings_without_rerunning_work(tmp_path):
    state = initial_test_state()
    application = next(item for item in state["applications"] if item["id"] == "app-northstar")
    application["analysis"] = {"summary": "Existing findings", "skillSignals": ["React"]}
    application["matchScore"] = 77
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, state_path=state_path)) as client:
        response, initial = _start_analysis_run(
            client,
            target=1,
            idempotency_key="repair-existing-findings",
        )
        run = _eventually_finished_analysis_run(client, initial["runId"])

    assert response.status_code == 202
    assert run["outcome"] == "target_met"
    assert run["candidates"][0]["state"] == "repaired"
    assert run["progress"]["repaired"] == 1
    assert run["progress"]["completions"] == 1


def test_analysis_recomputes_a_missing_legacy_match_score_deterministically(tmp_path):
    state = initial_test_state()
    application = next(item for item in state["applications"] if item["id"] == "app-northstar")
    application["analysis"] = {
        "summary": "Existing findings",
        "skillSignals": ["REST APIs"],
    }
    application["matchScore"] = None
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_test_app(settings, state_path=state_path)) as client:
        _response, initial = _start_analysis_run(
            client,
            target=1,
            idempotency_key="repair-missing-match-score",
        )
        run = _eventually_finished_analysis_run(client, initial["runId"])

    repaired = next(
        item
        for item in run["candidates"]
        if item["applicationId"] == "app-northstar"
    )
    persisted = next(
        item
        for item in json.loads(state_path.read_text())["applications"]
        if item["id"] == "app-northstar"
    )
    assert repaired["state"] == "repaired"
    assert isinstance(persisted["matchScore"], int)


def test_public_seam_serializes_partial_analysis_and_failed_resume_outcomes(tmp_path):
    class OutcomeWorkspace(FakeWorkspace):
        async def create_resume_fit_note(self, *args, **kwargs):
            raise RuntimeError("injected Note failure")

        async def archive_resume(self, resume_id):
            raise RuntimeError("injected cleanup failure")

    class CandidateFailureAnalysisModel(FakeApplicationAnalysisModel):
        async def transmit(self, prepared):
            response = await super().transmit(prepared)
            application, _repair_code = prepared.opaque
            if application.id != "app-lantern":
                return response
            return AnalysisModelResponse(
                payload={
                    "summary": ["Malformed candidate-specific output."],
                    "skillSignals": [],
                },
                call_evidence=response.call_evidence,
            )

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = OutcomeWorkspace(tmp_path / "state.json")

    with TestClient(
        create_test_app(
            settings,
            workspace=workspace,
            analysis_model=CandidateFailureAnalysisModel(),
        )
    ) as client:
        analysis, initial = _start_analysis_run(
            client,
            target=2,
            idempotency_key="partial-analysis",
        )
        finished = _eventually_finished_analysis_run(
            client, initial["runId"]
        )
        resume = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert analysis.status_code == 202
    assert finished["outcome"] == "queue_exhausted"
    assert finished["progress"]["completions"] == 1
    assert finished["progress"]["failed"] == 1
    assert {item["state"] for item in finished["candidates"]} == {
        "analyzed",
        "failed",
    }
    assert resume.status_code == 200
    assert resume.json()["result"] == "failed"
    assert resume.json()["cleanup"]["status"] == "incomplete"


def test_resume_generation_failure_is_logged_with_its_cause(tmp_path, caplog):
    class FailingResumeBuilder:
        async def build(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("injected resume builder failure")

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with caplog.at_level("ERROR"):
        with TestClient(
            create_test_app(settings, resume_builder=FailingResumeBuilder())
        ) as client:
            response = client.post(
                "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
            )

    assert response.status_code == 200
    assert response.json()["errors"] == [
        "Resume generation could not be completed."
    ]
    assert "resume_generation_failed" in caplog.text
    assert "application_id=app-orbit" in caplog.text
    assert "injected resume builder failure" in caplog.text


def test_invalid_json_and_conflict_use_the_locked_technical_envelope(tmp_path):
    class ConflictWorkspace(FakeWorkspace):
        async def load_analysis_queue_snapshot(
            self, *, excluded_application_ids=frozenset()
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "conflict",
                    "message": "Application Analysis is already running.",
                },
            )

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = ConflictWorkspace(tmp_path / "state.json")

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        invalid_json = client.post(
            "/api/v1/applications/analysis/run",
            content="{",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "invalid-json",
            },
        )
        conflict = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "workspace-conflict"},
            json={"target": 1},
        )

    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"]["code"] == "invalid_request"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"


def test_invalid_cursor_is_a_request_error_not_a_workflow_block(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/applications/analysis/queue",
            params={"limit": 5, "cursor": "not-a-cursor"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_queue_cursors_are_context_bound_and_expire_after_queue_changes(tmp_path):
    with make_client(tmp_path) as client:
        first_page = client.get(
            "/api/v1/applications/analysis/queue", params={"limit": 1}
        ).json()
        cursor = first_page["pagination"]["nextCursor"]

        wrong_queue = client.get(
            "/api/v1/resumes/queue", params={"limit": 1, "cursor": cursor}
        )
        _accepted, initial = _start_analysis_run(
            client,
            target=1,
            idempotency_key="expire-analysis-cursor",
        )
        _eventually_finished_analysis_run(client, initial["runId"])
        stale_queue = client.get(
            "/api/v1/applications/analysis/queue",
            params={"limit": 1, "cursor": cursor},
        )

    assert wrong_queue.status_code == 400
    assert wrong_queue.json()["error"]["code"] == "invalid_cursor"
    assert stale_queue.status_code == 400
    assert stale_queue.json()["error"]["code"] == "invalid_cursor"


def test_built_react_dashboard_is_served_by_the_fastapi_app(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_analysis_start_rejects_legacy_limit_and_missing_idempotency_key(
    tmp_path,
):
    with make_client(tmp_path) as client:
        legacy_limit = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "legacy-limit"},
            json={"limit": 5},
        )
        missing_key = client.post(
            "/api/v1/applications/analysis/run",
            json={"target": 5},
        )
        invalid_target = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "invalid-target"},
            json={"target": 11},
        )

    assert legacy_limit.status_code == 400
    assert legacy_limit.json() == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "Request validation failed.",
            "requestId": None,
        },
        "validationFailures": [
            {
                "kind": "request",
                "field": "limit",
                "message": "Extra inputs are not permitted",
            }
        ],
        "errors": ["Request validation failed."],
    }
    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "invalid_request"
    assert missing_key.json()["validationFailures"] == [
        {
            "kind": "request",
            "field": "header.Idempotency-Key",
            "message": "Field required",
        }
    ]
    assert invalid_target.status_code == 400
    assert invalid_target.json()["validationFailures"] == [
        {
            "kind": "request",
            "field": "target",
            "message": "Input should be less than or equal to 10",
        }
    ]


def test_requests_reject_extra_fields_and_whitespace_only_capture_values(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}

    with make_client(tmp_path) as client:
        extra = client.post(
            "/api/v1/resumes/create",
            json={"applicationId": "app-orbit", "model": "other", "prompt": "x"},
        )
        whitespace = client.post(
            "/api/v1/applications/confirm",
            headers=headers,
            json={
                "draft": {
                    "jobUrl": "https://example.com/jobs/42",
                    "companyName": "   ",
                    "role": "Engineer",
                    "location": None,
                    "jobContent": " " * 25,
                }
            },
        )

    assert extra.status_code == 400
    assert {failure["field"] for failure in extra.json()["validationFailures"]} == {
        "model",
        "prompt",
    }
    assert whitespace.status_code == 400
    assert whitespace.json()["error"]["code"] == "invalid_request"


def test_capture_authentication_uses_the_same_safe_error_envelope(tmp_path):
    request = {
        "evidence": {
            "url": "https://example.com/jobs/42",
            "visibleText": "Readable job content for a safe request.",
        }
    }

    with make_client(tmp_path) as client:
        missing = client.post("/api/v1/applications/prepare", json=request)
        invalid = client.post(
            "/api/v1/applications/prepare",
            json=request,
            headers={"X-Capture-Token": "wrong"},
        )

    expected = {
        "ok": False,
        "error": {
            "code": "invalid_capture_token",
            "message": "A valid X-Capture-Token header is required.",
            "requestId": None,
        },
        "validationFailures": [],
        "errors": ["A valid X-Capture-Token header is required."],
    }
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == expected
    assert invalid.json() == expected


def test_framework_and_media_type_failures_use_public_error_codes(tmp_path):
    with make_client(tmp_path) as client:
        missing = client.get("/api/v1/not-a-route")
        wrong_method = client.get("/api/v1/applications/prepare")
        wrong_media_type = client.post(
            "/api/v1/applications/analysis/run",
            content="target=5",
            headers={"Content-Type": "text/plain"},
        )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"
    assert wrong_media_type.status_code == 415
    assert wrong_media_type.json()["error"]["code"] == "unsupported_media_type"
    for response in (missing, wrong_method, wrong_media_type):
        assert response.json()["validationFailures"] == []
        assert response.json()["error"]["requestId"] is None


def test_capture_rejects_oversized_evidence_without_echoing_it(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}
    request = {
        "evidence": {
            "url": "https://example.com/jobs/42",
            "visibleText": "x" * 120_001,
        }
    }

    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/applications/prepare", json=request, headers=headers
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert "x" * 100 not in response.text


def test_capture_rejects_a_request_body_larger_than_one_mebibyte(tmp_path):
    headers = {
        "X-Capture-Token": "test-capture-token",
        "Content-Type": "application/json",
    }
    request_body = '{"evidence":{"url":"https://example.com/jobs/42","visibleText":"' + (
        "x" * (1024 * 1024)
    ) + '"}}'

    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/applications/prepare", content=request_body, headers=headers
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_capture_can_prepare_readable_semantic_html_without_echoing_markup(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}
    request = {
        "evidence": {
            "url": "https://example.com/jobs/42",
            "title": "Engineer at Example",
            "semanticHtml": "<article><h1>Engineer</h1><p>Build reliable Python services.</p></article>",
        }
    }

    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/applications/prepare", json=request, headers=headers
        )

    assert response.status_code == 200
    assert response.json()["result"] == "prepared"
    assert response.json()["draft"]["jobContentPreview"] == (
        "Engineer Build reliable Python services."
    )
    assert "<article>" not in response.text


def test_capture_prefers_structured_job_metadata_over_ambiguous_page_title(tmp_path):
    headers = {"X-Capture-Token": "test-capture-token"}
    request = {
        "evidence": {
            "url": "https://example.com/jobs/42",
            "title": "Careers | Example",
            "visibleText": "Build reliable Python services for customers.",
            "structuredJobTitle": "Platform Engineer",
            "structuredCompanyName": "Example",
            "structuredLocation": "Remote",
        }
    }

    with make_client(tmp_path) as client:
        prepared = client.post(
            "/api/v1/applications/prepare", json=request, headers=headers
        ).json()

    assert prepared["result"] == "prepared"
    assert prepared["draft"]["role"] == "Platform Engineer"
    assert prepared["draft"]["companyName"] == "Example"
    assert prepared["draft"]["location"] == "Remote"


def test_cors_allows_only_configured_browser_origins_and_headers(tmp_path):
    extension_origin = "chrome-extension://abcdefghijklmnop"
    preflight_headers = {
        "Origin": extension_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": (
            "content-type,x-capture-token,idempotency-key"
        ),
    }

    with make_client(tmp_path, extension_origin=extension_origin) as client:
        allowed = client.options(
            "/api/v1/applications/prepare", headers=preflight_headers
        )
        rejected = client.options(
            "/api/v1/applications/prepare",
            headers={**preflight_headers, "Origin": "https://attacker.example"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == extension_origin
    assert "X-Capture-Token" in allowed.headers["access-control-allow-headers"]
    assert "Idempotency-Key" in allowed.headers["access-control-allow-headers"]
    assert "POST" in allowed.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in allowed.headers
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_unexpected_failures_are_sanitized_and_correlated(tmp_path, caplog):
    class ExplodingWorkspace(FakeWorkspace):
        async def validate_analysis_workspace(self):
            raise RuntimeError("private provider response must not escape")

    settings = Settings(
        capture_token="test-capture-token",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = ExplodingWorkspace(tmp_path / "state.json")

    with TestClient(
        create_test_app(settings, workspace=workspace), raise_server_exceptions=False
    ) as client:
        response = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "unexpected-workspace-failure"},
            json={"target": 1},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["requestId"]
    assert response.json()["validationFailures"] == []
    assert "private provider response" not in response.text
    assert "private provider response" not in caplog.text


def test_resume_artifact_quarantine_worklist_uses_its_contract_page_sizes(tmp_path):
    with make_client(tmp_path) as client:
        default_page = client.get("/api/v1/resumes/artifact-quarantines")
        maximum_page = client.get(
            "/api/v1/resumes/artifact-quarantines", params={"limit": 50}
        )
        oversized_page = client.get(
            "/api/v1/resumes/artifact-quarantines", params={"limit": 51}
        )

    assert default_page.status_code == 200
    assert default_page.json()["pagination"] == {
        "limit": 20,
        "nextCursor": None,
        "hasMore": False,
    }
    assert maximum_page.status_code == 200
    assert maximum_page.json()["pagination"]["limit"] == 50
    assert oversized_page.status_code == 400
    assert oversized_page.json()["validationFailures"] == [
        {
            "kind": "request",
            "field": "query.limit",
            "message": "Input should be less than or equal to 50",
        }
    ]


def test_completed_workflow_logs_only_safe_metadata(tmp_path, caplog):
    private_values = (
        "Own Python platform services",
        "test-deepseek-key",
        str(tmp_path / "export"),
    )
    caplog.set_level("INFO", logger="merida.workflow")

    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert response.status_code == 200
    assert response.json()["result"] == "created"
    for field in ("record_id", "outcome_code", "policy_version", "duration_ms"):
        assert f"{field}=" in caplog.text
    for private_value in private_values:
        assert private_value not in response.text
        assert private_value not in caplog.text


def test_openapi_locks_the_public_route_inventory_and_named_responses(tmp_path):
    expected = {
        ("get", "/api/v1/health"): ("getHealth", "HealthResponse", "200"),
        ("get", "/api/v1/health/notion"): (
            "getNotionHealth",
            "NotionHealthResponse",
            "200",
        ),
        ("get", "/api/v1/health/analysis"): (
            "getApplicationAnalysisHealth",
            "ApplicationAnalysisHealthResponse",
            "200",
        ),
        ("get", "/api/v1/health/resumes"): (
            "getResumeCreationHealth",
            "ResumeCreationHealthResponse",
            "200",
        ),
        ("get", "/api/v1/operator/settings"): (
            "getOperatorSettings",
            "OperatorSettingsResponse",
            "200",
        ),
        ("post", "/api/v1/applications/prepare"): (
            "prepareApplication",
            "PrepareApplicationResponse",
            "200",
        ),
        ("post", "/api/v1/applications/confirm"): (
            "confirmApplication",
            "ConfirmApplicationResponse",
            "200",
        ),
        ("get", "/api/v1/applications/capture-matches"): (
            "getApplicationCaptureMatches",
            "CaptureMatchesResponse",
            "200",
        ),
        ("get", "/api/v1/applications/analysis/queue"): (
            "getApplicationAnalysisQueue",
            "GetApplicationAnalysisQueueResponse",
            "200",
        ),
        ("post", "/api/v1/applications/analysis/run"): (
            "runApplicationAnalysis",
            "AnalysisRunResponse",
            "202",
        ),
        ("get", "/api/v1/applications/analysis/runs/active"): (
            "getActiveApplicationAnalysisRun",
            "ActiveAnalysisRunResponse",
            "200",
        ),
        ("get", "/api/v1/applications/analysis/runs/{runId}"): (
            "getApplicationAnalysisRun",
            "AnalysisRunResponse",
            "200",
        ),
        ("post", "/api/v1/applications/analysis/runs/{runId}/cancel"): (
            "cancelApplicationAnalysisRun",
            "AnalysisRunResponse",
            "200",
        ),
        ("get", "/api/v1/resumes/queue"): (
            "getResumeCreationQueue",
            "GetResumeCreationQueueResponse",
            "200",
        ),
        ("post", "/api/v1/resumes/runs"): ("startResumeRun", "ResumeRunResponse", "202"),
        ("get", "/api/v1/resumes/runs/active"): ("getActiveResumeRun", "ResumeRunLookupResponse", "200"),
        ("get", "/api/v1/resumes/runs/latest"): ("getLatestResumeRun", "ResumeRunLookupResponse", "200"),
        ("get", "/api/v1/resumes/runs/{runId}"): ("getResumeRun", "ResumeRunResponse", "200"),
        ("post", "/api/v1/resumes/runs/{runId}/cancel"): ("cancelResumeRun", "ResumeRunResponse", "200"),
        ("get", "/api/v1/resumes/artifact-quarantines"): ("listResumeArtifactQuarantines", "ResumeArtifactQuarantineListResponse", "200"),
        ("get", "/api/v1/resumes/artifact-sets/{artifactSetId}"): ("getResumeArtifactSet", "ResumeArtifactSetResponse", "200"),
        ("post", "/api/v1/resumes/artifact-sets/{artifactSetId}/reconcile"): ("reconcileResumeArtifactSet", "ResumeArtifactSetResponse", "202"),
        ("post", "/api/v1/resumes/artifact-sets/{artifactSetId}/compensate"): ("compensateResumeArtifactSet", "ResumeArtifactSetResponse", "202"),
    }

    with make_client(tmp_path) as client:
        schema = client.get("/openapi.json").json()

    api_operations = {
        (method, path)
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1/")
        for method in path_item
        if method in {"get", "post"}
    }
    assert api_operations == {
        *expected,
        ("get", "/api/v1/resumes/artifact-sets/{artifactSetId}/pdf"),
    }
    for (method, path), (
        operation_id,
        response_name,
        success_status,
    ) in expected.items():
        operation = schema["paths"][path][method]
        response_schema = operation["responses"][success_status]["content"][
            "application/json"
        ]["schema"]
        assert operation["operationId"] == operation_id
        assert response_schema == {
            "$ref": f"#/components/schemas/{response_name}"
        }
        assert "422" not in operation["responses"]

    pdf = schema["paths"]["/api/v1/resumes/artifact-sets/{artifactSetId}/pdf"]["get"]
    assert pdf["operationId"] == "downloadResumeArtifactSetPdf"
    assert "application/pdf" in pdf["responses"]["200"]["content"]

    prepare_responses = schema["paths"]["/api/v1/applications/prepare"]["post"][
        "responses"
    ]
    for status in ("400", "401", "413", "415", "500"):
        assert prepare_responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ApiErrorResponse"
        }

    for method, path in (
        ("get", "/api/v1/applications/analysis/runs/active"),
        ("get", "/api/v1/applications/analysis/runs/{runId}"),
        ("post", "/api/v1/applications/analysis/runs/{runId}/cancel"),
    ):
        assert schema["paths"][path][method]["responses"]["503"]["content"][
            "application/json"
        ]["schema"] == {"$ref": "#/components/schemas/ApiErrorResponse"}

    component_names = set(schema["components"]["schemas"])
    assert {
        "PrepareApplicationRequest",
        "ConfirmApplicationRequest",
        "RunApplicationAnalysisRequest",
        "StartResumeRunRequest",
    } <= component_names
    assert not {
        "PrepareCaptureRequest",
        "ConfirmCaptureRequest",
        "AnalysisRunRequest",
        "RunApplicationAnalysisResponse",
    } & component_names
    capture_header = next(
        parameter
        for parameter in schema["paths"]["/api/v1/applications/prepare"]["post"][
            "parameters"
        ]
        if parameter["name"] == "X-Capture-Token"
    )
    assert capture_header["required"] is True
    start_operation = schema["paths"][
        "/api/v1/applications/analysis/run"
    ]["post"]
    idempotency_header = next(
        parameter
        for parameter in start_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["required"] is True
    start_request = schema["components"]["schemas"][
        "RunApplicationAnalysisRequest"
    ]
    assert set(start_request["properties"]) == {"target"}
    assert start_request["properties"]["target"]["default"] == 5
    assert set(schema["components"]["schemas"]["ApiErrorDetail"]["properties"]["code"]["enum"]) == {
        "invalid_request",
        "invalid_cursor",
        "invalid_capture_token",
        "not_found",
        "pdf_not_found",
        "method_not_allowed",
        "conflict",
            "analysis_run_active",
            "resume_run_active",
            "idempotency_conflict",
            "analysis_authorization_blocked",
            "resume_authorization_blocked",
            "resume_artifact_state_changed",
            "resume_artifact_action_active",
            "resume_artifact_action_unavailable",
        "payload_too_large",
        "unsupported_media_type",
        "internal_error",
    }


def test_emitted_openapi_matches_the_accepted_client_contract(tmp_path):
    accepted = json.loads(
        (PROJECT_ROOT / "packages/api-client/openapi.json").read_text()
    )

    with make_client(tmp_path) as client:
        emitted = client.get("/openapi.json").json()

    assert emitted == accepted


def test_production_start_rejects_a_missing_dashboard_build(tmp_path):
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with pytest.raises(RuntimeError, match="dashboard build is missing"):
        create_app(
            settings,
            dashboard_dist=tmp_path / "missing-dashboard",
            require_dashboard=True,
        )


def test_dashboard_history_fallback_serves_the_built_app(tmp_path):
    dashboard_dist = tmp_path / "dashboard"
    dashboard_dist.mkdir()
    dashboard_dist.joinpath("index.html").write_text("<main>Merida dashboard</main>")
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(create_app(settings, dashboard_dist=dashboard_dist)) as client:
        response = client.get("/dashboard/application-analysis")

    assert response.status_code == 200
    assert response.text == "<main>Merida dashboard</main>"
