from contextlib import asynccontextmanager
from dataclasses import dataclass
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
from .integrations.notion_workspace import NotionWorkspace
from .features.applications.analysis_model import create_deepseek_analysis_model
from .integrations.pdf_export import LocalPdfArtifacts
from .integrations.deepseek_resume import create_deepseek_resume_builder
from .shared.pagination import InvalidCursor
from .shared.execution import ExecutionCoordinator, OperationConflict
from .shared.recovery import (
    JsonEffectJournal,
    RecoveryJournalError,
    UnavailableEffectJournal,
)
from .shared.workspace import (
    WorkspaceProviderError,
    WorkspaceReadiness,
    workspace_validation_failures,
)
from .shared.schemas import (
    ApiErrorResponse,
    ApiErrorCode,
    ApplicationAnalysisHealthResponse,
    HealthResponse,
    NotionHealthResponse,
    OperatorSettingsResponse,
    ResumeCreationHealthResponse,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeCapabilities:
    capture_workspace_configured: bool
    analysis_workspace_configured: bool
    resume_workspace_configured: bool
    analysis_model_available: bool
    resume_builder_available: bool


def _api_error_responses(*status_codes: int) -> dict[int, dict]:
    return {
        status_code: {"model": ApiErrorResponse, "description": "Technical error"}
        for status_code in status_codes
    }


def _health(
    settings: Settings,
    capabilities: RuntimeCapabilities,
    recovery_error: str | None = None,
    *,
    workflow_readiness: dict[str, WorkspaceReadiness] | None = None,
    workflow_provider_errors: dict[str, str] | None = None,
) -> dict:
    workflow_readiness = workflow_readiness or {}
    workflow_provider_errors = workflow_provider_errors or {}
    errors = []
    capture_ready = bool(
        capabilities.capture_workspace_configured
        and workflow_readiness.get("capture")
        and workflow_readiness["capture"].ready
        and "capture" not in workflow_provider_errors
    )
    analysis_workspace_ready = bool(
        capabilities.analysis_workspace_configured
        and workflow_readiness.get("analysis")
        and workflow_readiness["analysis"].ready
        and "analysis" not in workflow_provider_errors
    )
    resume_workspace_ready = bool(
        capabilities.resume_workspace_configured
        and workflow_readiness.get("resumes")
        and workflow_readiness["resumes"].ready
        and "resumes" not in workflow_provider_errors
    )
    notion = "ready" if capture_ready else "blocked"
    analysis = (
        "ready"
        if analysis_workspace_ready and capabilities.analysis_model_available
        else "blocked"
    )
    resumes = (
        "ready"
        if (
            resume_workspace_ready
            and capabilities.resume_builder_available
            and settings.user_name_configured
        )
        else "blocked"
    )
    if not capabilities.capture_workspace_configured:
        errors.append("Applications database configuration is incomplete.")
    if not capabilities.resume_workspace_configured:
        errors.append("Resume and Notes database configuration is incomplete.")
    if not settings.capture_token_configured:
        errors.append("CAPTURE_TOKEN is not configured.")
    if not settings.deepseek_configured:
        errors.append("DEEPSEEK_API_KEY is not configured.")
    if not settings.user_name_configured:
        errors.append("USER_NAME is not configured.")
    errors.extend(workflow_provider_errors.values())
    for readiness in workflow_readiness.values():
        errors.extend(issue.message for issue in readiness.errors)
    if (
        not capabilities.analysis_model_available
        or not capabilities.resume_builder_available
    ):
        errors.append("Real DeepSeek workflow adapters are not enabled in this build.")
    if recovery_error:
        errors.append(recovery_error)
        notion = resumes = "blocked"
    settings_state = "ready" if settings.capture_token_configured else "blocked"
    ready = settings_state == notion == analysis == resumes == "ready"
    return {
        "ok": ready,
        "status": "ready" if ready else "blocked",
        "service": "merida-api",
        "checks": {"settings": settings_state, "notion": notion, "analysis": analysis, "resumes": resumes},
        "validationFailures": [
            failure.model_dump(by_alias=True)
            for failure in workspace_validation_failures(
                WorkspaceReadiness(
                    errors=tuple(
                        dict.fromkeys(
                            issue
                            for readiness in workflow_readiness.values()
                            for issue in readiness.errors
                        )
                    )
                )
            )
        ],
        "errors": [] if ready else list(dict.fromkeys(errors)),
    }


async def _validate_workspace(
    capture,
    analysis,
    resumes,
) -> tuple[dict[str, WorkspaceReadiness], dict[str, str]]:
    readiness: dict[str, WorkspaceReadiness] = {}
    provider_errors: dict[str, str] = {}
    validators = {
        "capture": capture.validate_readiness,
        "analysis": analysis.validate_readiness,
        "resumes": resumes.validate_readiness,
    }
    for workflow, validate in validators.items():
        try:
            readiness[workflow] = await validate()
        except WorkspaceProviderError as error:
            provider_errors[workflow] = str(error)
    return readiness, provider_errors


def _blocked_queue(limit: int, message: str) -> dict:
    return {
        "ok": False,
        "status": "blocked",
        "queueCount": 0,
        "items": [],
        "pagination": {"limit": limit, "nextCursor": None, "hasMore": False},
        "validationFailures": [],
        "errors": [message],
    }


def _blocked_capture(message: str) -> dict:
    return {
        "ok": False,
        "status": "blocked",
        "result": "blocked",
        "validationFailures": [],
        "errors": [message],
    }


def _blocked_analysis_run(message: str) -> dict:
    return {
        "ok": False,
        "status": "blocked",
        "result": "blocked",
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "repaired": 0,
        "items": [],
        "validationFailures": [],
        "errors": [message],
    }


def _blocked_resume_creation(message: str) -> dict:
    return {
        "ok": False,
        "status": "blocked",
        "result": "blocked",
        "cleanup": {"status": "not_required", "errors": []},
        "validationFailures": [],
        "errors": [message],
    }


async def _block_provider_error(operation, blocked_response):
    try:
        return await operation
    except WorkspaceProviderError as error:
        return blocked_response(str(error))


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
    analysis_model=None,
    resume_builder=None,
    coordinator: ExecutionCoordinator | None = None,
) -> FastAPI:
    settings = settings or Settings()
    workspace_injected = workspace is not None
    if analysis_model is None and settings.deepseek_configured:
        analysis_model = create_deepseek_analysis_model(
            api_key=settings.deepseek_api_key,
            model=settings.analysis_model,
        )
    if resume_builder is None and settings.deepseek_configured:
        resume_builder = create_deepseek_resume_builder(
            api_key=settings.deepseek_api_key,
            model=settings.resume_model,
        )
    analysis_model_ready = analysis_model is not None
    resume_builder_ready = resume_builder is not None
    if workspace is None:
        workspace = NotionWorkspace(
            token=settings.notion_token,
            application_database_id=settings.notion_database_id,
            resume_database_id=settings.notion_resume_database_id,
            notes_database_id=settings.notion_notes_database_id,
        )
    capabilities = RuntimeCapabilities(
        capture_workspace_configured=(
            workspace_injected or settings.notion_applications_configured
        ),
        analysis_workspace_configured=(
            workspace_injected or settings.notion_analysis_configured
        ),
        resume_workspace_configured=(
            workspace_injected or settings.notion_resume_configured
        ),
        analysis_model_available=analysis_model_ready,
        resume_builder_available=resume_builder_ready,
    )
    coordinator = coordinator or ExecutionCoordinator()
    recovery_path = settings.recovery_journal_path
    try:
        journal = JsonEffectJournal(recovery_path)
        recovery_error = None
    except RecoveryJournalError:
        recovery_error = (
            "Recovery journal requires operator inspection before mutations."
        )
        journal = UnavailableEffectJournal(recovery_error)
    capture = ApplicationCapture(workspace, coordinator, journal)
    analysis = ApplicationAnalysis(workspace, analysis_model, coordinator)
    pdf_artifacts = LocalPdfArtifacts(
        settings.export_path, user_name=settings.user_name
    )
    resumes = ResumeCreation(
        workspace,
        resume_builder,
        ResumeArtifactCommitter(workspace, pdf_artifacts, journal),
        coordinator,
        journal,
    )
    require_capture_token = capture_token_dependency(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.export_path.mkdir(parents=True, exist_ok=True)
        await capture.reconcile()
        await resumes.reconcile()
        journal.compact()
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
    app.state.capture = capture
    app.state.resumes = resumes
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

    @app.exception_handler(OperationConflict)
    async def operation_conflict_handler(_request: Request, exc: OperationConflict):
        return _error_response(
            409,
            "conflict",
            str(exc),
            request_id=uuid4().hex,
        )

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
        workflow_readiness = {}
        workflow_provider_errors = {}
        if any(
            (
                capabilities.capture_workspace_configured,
                capabilities.analysis_workspace_configured,
                capabilities.resume_workspace_configured,
            )
        ):
            workflow_readiness, workflow_provider_errors = await _validate_workspace(
                capture, analysis, resumes
            )
        return _health(
            settings,
            capabilities,
            recovery_error,
            workflow_readiness=workflow_readiness,
            workflow_provider_errors=workflow_provider_errors,
        )

    @app.get("/api/v1/health/notion", operation_id="getNotionHealth", response_model=NotionHealthResponse, responses=_api_error_responses(500))
    async def get_notion_health():
        health = await get_health()
        ready = health["checks"]["notion"] == "ready"
        return {"ok": ready, "status": "ready" if ready else "blocked", "databases": {"applications": health["checks"]["notion"], "resumes": health["checks"]["notion"], "notes": health["checks"]["notion"]}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/analysis", operation_id="getApplicationAnalysisHealth", response_model=ApplicationAnalysisHealthResponse, responses=_api_error_responses(500))
    async def get_analysis_health():
        health = await get_health()
        ready = health["checks"]["analysis"] == "ready"
        state = "ready" if ready else "blocked"
        return {"ok": ready, "status": state, "workflow": "application_analysis", "checks": {"deepseek": state, "applicationsDatabase": health["checks"]["notion"], "jobContentAccess": health["checks"]["notion"], "masterResumeEvidence": state, "evidenceMatcher": state}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/resumes", operation_id="getResumeCreationHealth", response_model=ResumeCreationHealthResponse, responses=_api_error_responses(500))
    async def get_resume_health():
        health = await get_health()
        ready = health["checks"]["resumes"] == "ready"
        state = "ready" if ready else "blocked"
        return {"ok": ready, "status": state, "workflow": "resume_creation", "checks": {"deepseek": state, "notion": health["checks"]["notion"], "fitAnalysis": state, "masterResume": state, "pdfExport": state}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/operator/settings", operation_id="getOperatorSettings", response_model=OperatorSettingsResponse, responses=_api_error_responses(500))
    async def get_operator_settings():
        return {
            "ok": True,
            "models": {
                "analysis": settings.analysis_model,
                "resumes": settings.resume_model,
            },
            "configured": {"notion": settings.notion_configured, "deepseek": settings.deepseek_configured},
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
        if not capabilities.capture_workspace_configured:
            return _blocked_capture("Applications database configuration is incomplete.")
        return await _block_provider_error(
            capture.confirm(request.draft), _blocked_capture
        )

    @app.get("/api/v1/applications/analysis/queue", operation_id="getApplicationAnalysisQueue", response_model=GetApplicationAnalysisQueueResponse, responses=_api_error_responses(400, 500))
    async def get_analysis_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if not capabilities.analysis_workspace_configured:
            return _blocked_queue(limit, "Applications database configuration is incomplete.")
        return await _block_provider_error(
            analysis.get_queue(limit, cursor),
            lambda message: _blocked_queue(limit, message),
        )

    @app.post("/api/v1/applications/analysis/run", operation_id="runApplicationAnalysis", response_model=RunApplicationAnalysisResponse, responses=_api_error_responses(400, 409, 415, 500))
    async def run_application_analysis(request: RunApplicationAnalysisRequest):
        if not capabilities.analysis_workspace_configured:
            return _blocked_analysis_run(
                "Applications and Master Resume database configuration is incomplete."
            )
        if not capabilities.analysis_model_available:
            return _blocked_analysis_run(
                "Real Application Analysis is not enabled in this build."
            )
        return await _block_provider_error(
            analysis.run_batch(request.limit), _blocked_analysis_run
        )

    @app.get("/api/v1/resumes/queue", operation_id="getResumeCreationQueue", response_model=GetResumeCreationQueueResponse, responses=_api_error_responses(400, 500))
    async def get_resume_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if not capabilities.resume_workspace_configured:
            return _blocked_queue(limit, "Resume and Notes database configuration is incomplete.")
        return await _block_provider_error(
            resumes.get_queue(limit, cursor),
            lambda message: _blocked_queue(limit, message),
        )

    @app.post("/api/v1/resumes/create", operation_id="createResume", response_model=CreateResumeResponse, responses=_api_error_responses(400, 409, 415, 500))
    async def create_resume(request: CreateResumeRequest):
        if not capabilities.resume_workspace_configured:
            return _blocked_resume_creation(
                "Resume and Notes database configuration is incomplete."
            )
        if not capabilities.resume_builder_available:
            return _blocked_resume_creation(
                "Real Resume Creation is not enabled in this build."
            )
        if not settings.user_name_configured:
            return _blocked_resume_creation("USER_NAME is not configured.")
        return await _block_provider_error(
            resumes.create(request.application_id), _blocked_resume_creation
        )

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
        path = resumes.pdf_path(resume_id)
        if path is None:
            raise HTTPException(status_code=404, detail={"code": "pdf_not_found", "message": "Resume PDF was not found."})
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    web_dist = dashboard_dist or Path(__file__).resolve().parents[2] / "web" / "dist"
    dashboard_index = web_dist / "index.html"
    if require_dashboard and not dashboard_index.is_file():
        raise RuntimeError(
            "The dashboard build is missing. Run `npm run build` before `npm start`."
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
