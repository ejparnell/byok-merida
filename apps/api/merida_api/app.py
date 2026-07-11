from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .core.auth import capture_token_dependency
from .core.settings import Settings
from .features.applications import ApplicationAnalysis, ApplicationCapture
from .features.applications.schemas import (
    AnalysisRunRequest,
    ConfirmCaptureRequest,
    PrepareCaptureRequest,
)
from .features.resumes import ResumeCreation
from .features.resumes.schemas import CreateResumeRequest
from .integrations.demo_workspace import DemoWorkspace
from .shared.pagination import InvalidCursor


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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    workspace = DemoWorkspace(settings.demo_state_path, settings.export_path)
    capture = ApplicationCapture(workspace)
    analysis = ApplicationAnalysis(workspace)
    resumes = ResumeCreation(workspace)
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

    @app.exception_handler(InvalidCursor)
    async def invalid_cursor_handler(_request: Request, exc: InvalidCursor):
        return JSONResponse(status_code=400, content={"ok": False, "error": {"code": "invalid_cursor", "message": str(exc)}, "errors": [str(exc)]})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": detail, "errors": [detail.get("message", "Request failed.")]})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_request: Request, exc: RequestValidationError):
        failures = [
            {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {"code": "invalid_request", "message": "Request validation failed."},
                "validationFailures": failures,
                "errors": ["Request validation failed."],
            },
        )

    @app.get("/api/v1/health", operation_id="getHealth")
    async def get_health():
        return _health(settings)

    @app.get("/api/v1/health/notion", operation_id="getNotionHealth")
    async def get_notion_health():
        health = _health(settings)
        ready = health["checks"]["notion"] == "ready"
        return {"ok": ready, "status": "ready" if ready else "blocked", "workspace": "demo" if settings.merida_mode == "demo" else "notion", "databases": {"applications": health["checks"]["notion"], "resumes": health["checks"]["notion"], "notes": health["checks"]["notion"]}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/analysis", operation_id="getApplicationAnalysisHealth")
    async def get_analysis_health():
        health = _health(settings)
        ready = health["checks"]["analysis"] == "ready"
        return {"ok": ready, "status": "ready" if ready else "blocked", "workflow": "application_analysis", "checks": {"workspace": health["checks"]["notion"], "model": health["checks"]["analysis"], "evidenceMatcher": health["checks"]["analysis"]}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/health/resumes", operation_id="getResumeCreationHealth")
    async def get_resume_health():
        health = _health(settings)
        ready = health["checks"]["resumes"] == "ready"
        return {"ok": ready, "status": "ready" if ready else "blocked", "workflow": "resume_creation", "checks": {"workspace": health["checks"]["notion"], "model": health["checks"]["resumes"], "fitAnalysis": health["checks"]["resumes"], "pdfExport": health["checks"]["resumes"]}, "validationFailures": health["validationFailures"], "errors": [] if ready else health["errors"]}

    @app.get("/api/v1/operator/settings", operation_id="getOperatorSettings")
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
            "errors": [],
        }

    @app.post("/api/v1/applications/prepare", dependencies=[Depends(require_capture_token)], operation_id="prepareApplication")
    async def prepare_application(request: PrepareCaptureRequest):
        return await capture.prepare(request.evidence)

    @app.post("/api/v1/applications/confirm", dependencies=[Depends(require_capture_token)], operation_id="confirmApplication")
    async def confirm_application(request: ConfirmCaptureRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "validationFailures": [], "errors": ["Real workspace writes are not enabled in this build."]}
        return await capture.confirm(request.draft)

    @app.get("/api/v1/applications/analysis/queue", operation_id="getApplicationAnalysisQueue")
    async def get_analysis_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "queueCount": 0, "items": [], "pagination": {"limit": limit, "nextCursor": None, "hasMore": False}, "errors": ["Real Application Analysis is not enabled in this build."]}
        return await analysis.get_queue(limit, cursor)

    @app.post("/api/v1/applications/analysis/run", operation_id="runApplicationAnalysis")
    async def run_application_analysis(request: AnalysisRunRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "processed": 0, "succeeded": 0, "failed": 0, "repaired": 0, "items": [], "errors": ["Real Application Analysis is not enabled in this build."]}
        return await analysis.run_batch(request.limit)

    @app.get("/api/v1/resumes/queue", operation_id="getResumeCreationQueue")
    async def get_resume_queue(limit: int = Query(default=5, ge=1, le=10), cursor: str | None = None):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "queueCount": 0, "items": [], "pagination": {"limit": limit, "nextCursor": None, "hasMore": False}, "errors": ["Real Resume Creation is not enabled in this build."]}
        return await resumes.get_queue(limit, cursor)

    @app.post("/api/v1/resumes/create", operation_id="createResume")
    async def create_resume(request: CreateResumeRequest):
        if settings.merida_mode != "demo":
            return {"ok": False, "status": "blocked", "result": "blocked", "cleanup": {}, "validationFailures": [], "errors": ["Real Resume Creation is not enabled in this build."]}
        return await resumes.create(request.application_id)

    @app.get("/api/v1/resumes/{resume_id}/pdf", operation_id="downloadResumePdf")
    async def download_resume_pdf(resume_id: str):
        if settings.merida_mode != "demo":
            raise HTTPException(status_code=404, detail={"code": "pdf_not_found", "message": "Resume PDF was not found."})
        path = resumes.pdf_path(resume_id)
        if path is None:
            raise HTTPException(status_code=404, detail={"code": "pdf_not_found", "message": "Resume PDF was not found."})
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/api/v1/demo/reset", operation_id="resetDemo")
    async def reset_demo():
        if settings.merida_mode != "demo":
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Demo mode is not active."})
        return await workspace.reset()

    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.exists():
        assets = web_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

        @app.get("/dashboard", include_in_schema=False)
        async def dashboard():
            return FileResponse(web_dist / "index.html")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/dashboard" if web_dist.exists() else "/docs")

    return app
