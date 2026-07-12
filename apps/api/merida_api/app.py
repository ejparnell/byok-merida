from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import cast, get_args
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core.auth import capture_token_dependency
from .core.settings import Settings
from .features.applications import ApplicationAnalysis, ApplicationCapture
from .features.applications.schemas import (
    RunApplicationAnalysisRequest,
    ConfirmApplicationResponse,
    ConfirmApplicationRequest,
    GetApplicationAnalysisQueueResponse,
    PrepareApplicationResponse,
    PrepareApplicationRequest,
    RunApplicationAnalysisResponse,
)
from .features.resumes import ResumeCreation
from .features.resumes.commit import ResumeArtifactCommitter
from .features.resumes.schemas import (
    CreateResumeRequest,
    CreateResumeResponse,
    GetResumeCreationQueueResponse,
)
from .integrations.demo_workspace import DemoWorkspace
from .integrations.demo_models import (
    DemoApplicationAnalysisModel,
    DemoResumeDocumentBuilder,
)
from .integrations.notion_workspace import NotionWorkspace
from .integrations.pdf_export import LocalPdfArtifacts
from .shared.pagination import InvalidCursor
from .shared.schemas import (
    ApiErrorResponse,
    ApiErrorCode,
    ApplicationAnalysisHealthResponse,
    HealthResponse,
    NotionHealthResponse,
    OperatorSettingsResponse,
    ResetDemoResponse,
    ResumeCreationHealthResponse,
)


logger = logging.getLogger(__name__)


def _api_error_responses(*status_codes: int) -> dict[int, dict]:
    return {
        status_code: {"model": ApiErrorResponse, "description": "Technical error"}
        for status_code in status_codes
    }


def _health(settings: Settings) -> dict:
    if settings.merida_mode == "demo":
        checks = {"settings": "ready", "notion": "ready", "analysis": "ready", "resumes": "ready"}
        return {"ok": True, "status": "ready", "service": "merida-api", "mode": "demo", "checks": checks, "validationFailures": [], "errors": []}

    errors = []
    notion = "ready" if settings.notion_configured else "blocked"
    analysis = "ready" if settings.notion_configured and settings.deepseek_configured else "blocked"
    resumes = analysis
    if not settings.notion_configured:
        errors.append("Notion configuration is incomplete.")
    if not settings.deepseek_configured:
        errors.append("DEEPSEEK_API_KEY is not configured.")
    if settings.notion_configured:
        errors.append("The real Notion adapter has not been enabled in this build; use MERIDA_MODE=demo.")
        notion = analysis = resumes = "blocked"
    return {
        "ok": False,
        "status": "blocked",
        "service": "merida-api",
        "mode": "real",
        "checks": {"settings": "ready", "notion": notion, "analysis": analysis, "resumes": resumes},
        "validationFailures": [],
        "errors": errors,
    }


def _error_response(
    status_code: int,
    code: ApiErrorCode,
    message: str,
    *,
    validation_failures: list[dict] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id,
            },
            "validationFailures": validation_failures or [],
            "errors": [message],
        },
    )


def _public_error_code(value: object, status_code: int) -> ApiErrorCode:
    if value in get_args(ApiErrorCode):
        return cast(ApiErrorCode, value)
    return "internal_error" if status_code >= 500 else "invalid_request"


def create_app(
    settings: Settings | None = None,
    *,
    workspace=None,
    dashboard_dist: Path | None = None,
    require_dashboard: bool = False,
) -> FastAPI:
    settings = settings or Settings()
    if workspace is None:
        workspace = (
            DemoWorkspace(
                settings.demo_state_path,
                settings.export_path,
                fixture_path=settings.demo_fixture_path,
            )
            if settings.merida_mode == "demo"
            else NotionWorkspace(
                token=settings.notion_token,
                application_database_id=settings.notion_database_id,
                resume_database_id=settings.notion_resume_database_id,
                notes_database_id=settings.notion_notes_database_id,
            )
        )
    capture = ApplicationCapture(workspace)
    analysis = ApplicationAnalysis(workspace, DemoApplicationAnalysisModel())
    pdf_artifacts = LocalPdfArtifacts(settings.export_path)
    resumes = ResumeCreation(
        workspace,
        DemoResumeDocumentBuilder(),
        ResumeArtifactCommitter(workspace, pdf_artifacts),
    )
    require_capture_token = capture_token_dependency(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.export_path.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(
        title="Merida API",
        version="1.0.0",
        description="Local-first Application Capture, Analysis, and Resume Creation.",
        lifespan=lifespan,
    )

    def locked_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        for path_item in schema["paths"].values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation.get("responses", {}).pop("422", None)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = locked_openapi
    app.state.settings = settings
    app.state.workspace = workspace
    origins = [settings.web_origin, "http://localhost:5173", "http://127.0.0.1:5173"]
    if settings.extension_origin:
        origins.append(settings.extension_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(origins)),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Capture-Token"],
    )

    json_body_routes = {
        "/api/v1/applications/prepare",
        "/api/v1/applications/confirm",
        "/api/v1/applications/analysis/run",
        "/api/v1/resumes/create",
    }

    @app.middleware("http")
    async def require_json_media_type(request: Request, call_next):
        if request.method == "POST" and request.url.path in json_body_routes:
            media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
            if media_type != "application/json":
                return _error_response(
                    415,
                    "unsupported_media_type",
                    "Content-Type must be application/json.",
                )
        return await call_next(request)

    capture_body_routes = {
        "/api/v1/applications/prepare",
        "/api/v1/applications/confirm",
    }

    @app.middleware("http")
    async def limit_capture_request_body(request: Request, call_next):
        if request.method == "POST" and request.url.path in capture_body_routes:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 1024 * 1024:
                return _error_response(
                    413, "payload_too_large", "Capture request is too large."
                )
            body = await request.body()
            if len(body) > 1024 * 1024:
                return _error_response(
                    413, "payload_too_large", "Capture request is too large."
                )
        return await call_next(request)

    @app.exception_handler(InvalidCursor)
    async def invalid_cursor_handler(_request: Request, exc: InvalidCursor):
        return _error_response(400, "invalid_cursor", str(exc))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"message": str(exc.detail)}
        )
        return _error_response(
            exc.status_code,
            _public_error_code(detail.get("code"), exc.status_code),
            detail.get("message", "Request failed."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ):
        framework_errors = {
            404: ("not_found", "Resource was not found."),
            405: ("method_not_allowed", "Method is not allowed for this resource."),
            415: ("unsupported_media_type", "Content-Type is not supported."),
        }
        code, message = framework_errors.get(
            exc.status_code,
            ("internal_error", "An unexpected backend error occurred."),
        )
        return _error_response(
            exc.status_code,
            code,
            message,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_request: Request, exc: RequestValidationError):
        if any(
            error["type"] == "missing"
            and tuple(error["loc"]) == ("header", "X-Capture-Token")
            for error in exc.errors()
        ):
            return _error_response(
                401,
                "invalid_capture_token",
                "A valid X-Capture-Token header is required.",
            )
        if any(
            error["type"] in {"string_too_long", "payload_too_large"}
            for error in exc.errors()
        ):
            return _error_response(
                413, "payload_too_large", "Request payload is too large."
            )
        failures = [
            {"kind": "request", "field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
            for error in exc.errors()
        ]
        return _error_response(
            400,
            "invalid_request",
            "Request validation failed.",
            validation_failures=failures,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception):
        request_id = uuid4().hex
        logger.error(
            "Unhandled API failure request_id=%s error_type=%s",
            request_id,
            type(exc).__name__,
        )
        return _error_response(
            500,
            "internal_error",
            "An unexpected backend error occurred.",
            request_id=request_id,
        )

    @app.get(
        "/api/v1/health",
        operation_id="getHealth",
        response_model=HealthResponse,
        responses=_api_error_responses(500),
    )
    async def get_health():
        return _health(settings)

    @app.get("/api/v1/health/notion", operation_id="getNotionHealth", response_model=NotionHealthResponse, responses=_api_error_responses(500))
    async def get_notion_health():
        health = _health(settings)
        ready = health["checks"]["notion"] == "ready"
        return {"ok": ready, "status": "ready" if ready else "blocked", "workspace": "demo" if settings.merida_mode == "demo" else "notion", "databases": {"applications": health["checks"]["notion"], "resumes": health["checks"]["notion"], "notes": health["checks"]["notion"]}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/analysis", operation_id="getApplicationAnalysisHealth", response_model=ApplicationAnalysisHealthResponse, responses=_api_error_responses(500))
    async def get_analysis_health():
        health = _health(settings)
        ready = health["checks"]["analysis"] == "ready"
        state = "ready" if ready else "blocked"
        return {"ok": ready, "status": state, "workflow": "application_analysis", "checks": {"deepseek": state, "applicationsDatabase": health["checks"]["notion"], "jobContentAccess": health["checks"]["notion"], "masterResumeEvidence": state, "evidenceMatcher": state}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/resumes", operation_id="getResumeCreationHealth", response_model=ResumeCreationHealthResponse, responses=_api_error_responses(500))
    async def get_resume_health():
        health = _health(settings)
        ready = health["checks"]["resumes"] == "ready"
        state = "ready" if ready else "blocked"
        return {"ok": ready, "status": state, "workflow": "resume_creation", "checks": {"deepseek": state, "notion": health["checks"]["notion"], "fitAnalysis": state, "masterResume": state, "pdfExport": state}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/operator/settings", operation_id="getOperatorSettings", response_model=OperatorSettingsResponse, responses=_api_error_responses(500))
    async def get_operator_settings():
        demo = settings.merida_mode == "demo"
        return {
            "ok": True,
            "mode": settings.merida_mode,
            "workspace": "demo" if demo else "notion",
            "models": {
                "analysis": "demo-analysis-v1" if demo else settings.analysis_model,
                "resumes": "demo-resume-v1" if demo else settings.resume_model,
            },
            "configured": {"notion": demo or settings.notion_configured, "deepseek": demo or settings.deepseek_configured},
            "validationFailures": [],
            "errors": [],
        }

    @app.post(
        "/api/v1/applications/prepare",
        dependencies=[Depends(require_capture_token)],
        operation_id="prepareApplication",
        response_model=PrepareApplicationResponse,
        responses=_api_error_responses(400, 401, 413, 415, 500),
    )
    async def prepare_application(request: PrepareApplicationRequest):
        return await capture.prepare(request.evidence)

    @app.post(
        "/api/v1/applications/confirm",
        dependencies=[Depends(require_capture_token)],
        operation_id="confirmApplication",
        response_model=ConfirmApplicationResponse,
        responses=_api_error_responses(400, 401, 413, 415, 500),
    )
    async def confirm_application(request: ConfirmApplicationRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "validationFailures": [], "errors": ["Real workspace writes are not enabled in this build."]}
        return await capture.confirm(request.draft)

    @app.get("/api/v1/applications/analysis/queue", operation_id="getApplicationAnalysisQueue", response_model=GetApplicationAnalysisQueueResponse, responses=_api_error_responses(400, 500))
    async def get_analysis_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "queueCount": 0, "items": [], "pagination": {"limit": limit, "nextCursor": None, "hasMore": False}, "validationFailures": [], "errors": ["Real Application Analysis is not enabled in this build."]}
        return await analysis.get_queue(limit, cursor)

    @app.post("/api/v1/applications/analysis/run", operation_id="runApplicationAnalysis", response_model=RunApplicationAnalysisResponse, responses=_api_error_responses(400, 409, 415, 500))
    async def run_application_analysis(request: RunApplicationAnalysisRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "processed": 0, "succeeded": 0, "failed": 0, "repaired": 0, "items": [], "validationFailures": [], "errors": ["Real Application Analysis is not enabled in this build."]}
        return await analysis.run_batch(request.limit)

    @app.get("/api/v1/resumes/queue", operation_id="getResumeCreationQueue", response_model=GetResumeCreationQueueResponse, responses=_api_error_responses(400, 500))
    async def get_resume_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "queueCount": 0, "items": [], "pagination": {"limit": limit, "nextCursor": None, "hasMore": False}, "validationFailures": [], "errors": ["Real Resume Creation is not enabled in this build."]}
        return await resumes.get_queue(limit, cursor)

    @app.post("/api/v1/resumes/create", operation_id="createResume", response_model=CreateResumeResponse, responses=_api_error_responses(400, 409, 415, 500))
    async def create_resume(request: CreateResumeRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "cleanup": {"status": "not_required", "errors": []}, "validationFailures": [], "errors": ["Real Resume Creation is not enabled in this build."]}
        return await resumes.create(request.application_id)

    @app.get(
        "/api/v1/resumes/{resumeId}/pdf",
        operation_id="downloadResumePdf",
        response_class=FileResponse,
        responses={
            200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
            **_api_error_responses(404, 500),
        },
    )
    async def download_resume_pdf(resume_id: str = ApiPath(alias="resumeId")):
        if settings.merida_mode != "demo":
            raise HTTPException(status_code=404, detail={"code": "pdf_not_found", "message": "Resume PDF was not found."})
        path = resumes.pdf_path(resume_id)
        if path is None:
            raise HTTPException(status_code=404, detail={"code": "pdf_not_found", "message": "Resume PDF was not found."})
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/api/v1/demo/reset", operation_id="resetDemo", response_model=ResetDemoResponse, responses=_api_error_responses(404, 500))
    async def reset_demo():
        if settings.merida_mode != "demo":
            raise HTTPException(status_code=404, detail={"code": "demo_not_active", "message": "Demo mode is not active."})
        return await workspace.reset()

    web_dist = dashboard_dist or Path(__file__).resolve().parents[2] / "web" / "dist"
    dashboard_index = web_dist / "index.html"
    if require_dashboard and not dashboard_index.is_file():
        raise RuntimeError(
            "The dashboard build is missing. Run `npm run final:build` before `npm run final:start`."
        )
    if dashboard_index.is_file():
        assets = web_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

        @app.get("/dashboard", include_in_schema=False)
        async def dashboard():
            return FileResponse(dashboard_index)

        @app.get("/dashboard/{client_path:path}", include_in_schema=False)
        async def dashboard_history_fallback(client_path: str):
            del client_path
            return FileResponse(dashboard_index)

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/dashboard" if dashboard_index.is_file() else "/docs")

    return app
