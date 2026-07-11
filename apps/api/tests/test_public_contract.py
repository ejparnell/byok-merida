from fastapi.testclient import TestClient

from merida_api.app import create_app
from merida_api.core.settings import Settings


def make_client(tmp_path):
    settings = Settings(
        merida_mode="demo",
        capture_token="test-capture-token",
        demo_state_path=tmp_path / "state.json",
        export_path=tmp_path / "export",
    )
    return TestClient(create_app(settings))


def test_health_and_operator_settings_are_safe_and_ready_in_demo_mode(tmp_path):
    with make_client(tmp_path) as client:
        health = client.get("/api/v1/health").json()
        settings = client.get("/api/v1/operator/settings").json()

    assert health == {
        "ok": True,
        "status": "ready",
        "service": "merida-api",
        "mode": "demo",
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
        "analysis": "demo-analysis-v1",
        "resumes": "demo-resume-v1",
    }
    assert "captureToken" not in settings
    assert "notionToken" not in settings


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


def test_invalid_cursor_is_a_request_error_not_a_workflow_block(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/applications/analysis/queue",
            params={"limit": 5, "cursor": "not-a-cursor"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


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
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["validationFailures"][0]["field"] == "limit"
