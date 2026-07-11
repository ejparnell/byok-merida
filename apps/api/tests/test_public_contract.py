import json
from pathlib import Path

from fastapi.testclient import TestClient

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.integrations.demo_workspace import DemoWorkspace


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def make_client(tmp_path, **overrides):
    settings = Settings(
        merida_mode="demo",
        capture_token="test-capture-token",
        demo_state_path=tmp_path / "state.json",
        export_path=tmp_path / "export",
        **overrides,
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
        "mode",
        "checks",
        "validationFailures",
        "errors",
    }


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


def test_unexpected_failures_are_sanitized_and_correlated(tmp_path):
    class ExplodingWorkspace(DemoWorkspace):
        async def run_analysis(self, limit):
            raise RuntimeError("private provider response must not escape")

    settings = Settings(
        merida_mode="demo",
        capture_token="test-capture-token",
        demo_state_path=tmp_path / "state.json",
        export_path=tmp_path / "export",
    )
    workspace = ExplodingWorkspace(settings.demo_state_path, settings.export_path)

    with TestClient(
        create_app(settings, workspace=workspace), raise_server_exceptions=False
    ) as client:
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["requestId"]
    assert response.json()["validationFailures"] == []
    assert "private provider response" not in response.text


def test_demo_reset_is_stable_but_unavailable_in_real_mode(tmp_path):
    settings = Settings(
        merida_mode="real",
        demo_state_path=tmp_path / "state.json",
        export_path=tmp_path / "export",
    )

    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/demo/reset")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "demo_not_active"


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
        ("post", "/api/v1/demo/reset"): ("resetDemo", "ResetDemoResponse"),
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


def test_emitted_openapi_matches_the_accepted_client_contract(tmp_path):
    accepted = json.loads(
        (PROJECT_ROOT / "packages/api-client/openapi.json").read_text()
    )

    with make_client(tmp_path) as client:
        emitted = client.get("/openapi.json").json()

    assert emitted == accepted
