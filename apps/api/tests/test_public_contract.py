import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.shared.workspace import (
    WorkspaceIssue,
    WorkspaceProviderError,
    WorkspaceReadiness,
)
from fakes.app import create_test_app
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


def test_provider_outages_return_typed_workflow_blocks(tmp_path):
    class UnavailableWorkspace(FakeWorkspace):
        async def validate_capture_workspace(self):
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

    with TestClient(app) as client:
        responses = (
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
            client.post("/api/v1/applications/analysis/run", json={"limit": 1}),
            client.get("/api/v1/resumes/queue"),
            client.post(
                "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
            ),
        )

    for response in responses:
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"
        assert response.json()["errors"] == ["Notion could not be reached."]


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

        run = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        ).json()
        assert run["result"] == "completed"
        assert run["processed"] == 1
        assert run["succeeded"] == 1
        assert run["items"][0]["result"] == "analyzed"

        resume_queue = client.get("/api/v1/resumes/queue", params={"limit": 10}).json()
        analyzed_id = run["items"][0]["applicationId"]
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
            "/api/v1/applications/analysis/run", json={"limit": 1}
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
    assert analysis_run.status_code == 200
    assert analysis_run.json()["result"] == "blocked"
    assert analysis_run.json()["processed"] == 0
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
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["result"] == "repaired"
    assert response.json()["repaired"] == 1


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
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        ).json()

    repaired = next(item for item in response["items"] if item["applicationId"] == "app-northstar")
    assert repaired["result"] == "repaired"
    assert isinstance(repaired["matchScore"], int)


def test_public_seam_serializes_partial_analysis_and_failed_resume_outcomes(tmp_path):
    class OutcomeWorkspace(FakeWorkspace):
        async def append_application_analysis(self, application_id, document):
            if application_id == "app-lantern":
                raise WorkspaceProviderError("Notion could not be reached.")
            await super().append_application_analysis(application_id, document)

        async def create_resume_fit_note(self, *args, **kwargs):
            raise RuntimeError("injected Note failure")

        async def archive_resume(self, resume_id):
            raise RuntimeError("injected cleanup failure")

    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = OutcomeWorkspace(tmp_path / "state.json")

    with TestClient(create_test_app(settings, workspace=workspace)) as client:
        analysis = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 2}
        )
        resume = client.post(
            "/api/v1/resumes/create", json={"applicationId": "app-orbit"}
        )

    assert analysis.status_code == 200
    assert analysis.json()["failed"] == 1
    assert {item["result"] for item in analysis.json()["items"]} == {
        "analyzed",
        "failed",
    }
    assert resume.status_code == 200
    assert resume.json()["result"] == "failed"
    assert resume.json()["cleanup"]["status"] == "incomplete"


def test_invalid_json_and_conflict_use_the_locked_technical_envelope(tmp_path):
    class ConflictWorkspace(FakeWorkspace):
        async def list_analysis_queue(self, *, limit, cursor):
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
            headers={"Content-Type": "application/json"},
        )
        conflict = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
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
        client.post("/api/v1/applications/analysis/run", json={"limit": 1})
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


def test_request_validation_uses_the_public_error_envelope(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 11}
        )

    assert response.status_code == 400
    assert response.json() == {
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
                "message": "Input should be less than or equal to 10",
            }
        ],
        "errors": ["Request validation failed."],
    }


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
            content="limit=5",
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
        "Access-Control-Request-Headers": "content-type,x-capture-token",
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
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["requestId"]
    assert response.json()["validationFailures"] == []
    assert "private provider response" not in response.text
    assert "private provider response" not in caplog.text


def test_openapi_locks_the_public_route_inventory_and_named_responses(tmp_path):
    expected = {
        ("get", "/api/v1/health"): ("getHealth", "HealthResponse"),
        ("get", "/api/v1/health/notion"): (
            "getNotionHealth",
            "NotionHealthResponse",
        ),
        ("get", "/api/v1/health/analysis"): (
            "getApplicationAnalysisHealth",
            "ApplicationAnalysisHealthResponse",
        ),
        ("get", "/api/v1/health/resumes"): (
            "getResumeCreationHealth",
            "ResumeCreationHealthResponse",
        ),
        ("get", "/api/v1/operator/settings"): (
            "getOperatorSettings",
            "OperatorSettingsResponse",
        ),
        ("post", "/api/v1/applications/prepare"): (
            "prepareApplication",
            "PrepareApplicationResponse",
        ),
        ("post", "/api/v1/applications/confirm"): (
            "confirmApplication",
            "ConfirmApplicationResponse",
        ),
        ("get", "/api/v1/applications/analysis/queue"): (
            "getApplicationAnalysisQueue",
            "GetApplicationAnalysisQueueResponse",
        ),
        ("post", "/api/v1/applications/analysis/run"): (
            "runApplicationAnalysis",
            "RunApplicationAnalysisResponse",
        ),
        ("get", "/api/v1/resumes/queue"): (
            "getResumeCreationQueue",
            "GetResumeCreationQueueResponse",
        ),
        ("post", "/api/v1/resumes/create"): (
            "createResume",
            "CreateResumeResponse",
        ),
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
        ("get", "/api/v1/resumes/{resumeId}/pdf"),
    }
    for (method, path), (operation_id, response_name) in expected.items():
        operation = schema["paths"][path][method]
        response_schema = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert operation["operationId"] == operation_id
        assert response_schema == {
            "$ref": f"#/components/schemas/{response_name}"
        }
        assert "422" not in operation["responses"]

    pdf = schema["paths"]["/api/v1/resumes/{resumeId}/pdf"]["get"]
    assert pdf["operationId"] == "downloadResumePdf"
    assert "application/pdf" in pdf["responses"]["200"]["content"]

    prepare_responses = schema["paths"]["/api/v1/applications/prepare"]["post"][
        "responses"
    ]
    for status in ("400", "401", "413", "415", "500"):
        assert prepare_responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ApiErrorResponse"
        }

    component_names = set(schema["components"]["schemas"])
    assert {
        "PrepareApplicationRequest",
        "ConfirmApplicationRequest",
        "RunApplicationAnalysisRequest",
        "CreateResumeRequest",
    } <= component_names
    assert not {
        "PrepareCaptureRequest",
        "ConfirmCaptureRequest",
        "AnalysisRunRequest",
    } & component_names
    capture_header = next(
        parameter
        for parameter in schema["paths"]["/api/v1/applications/prepare"]["post"][
            "parameters"
        ]
        if parameter["name"] == "X-Capture-Token"
    )
    assert capture_header["required"] is True
    assert set(schema["components"]["schemas"]["ApiErrorDetail"]["properties"]["code"]["enum"]) == {
        "invalid_request",
        "invalid_cursor",
        "invalid_capture_token",
        "not_found",
        "pdf_not_found",
        "method_not_allowed",
        "conflict",
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
