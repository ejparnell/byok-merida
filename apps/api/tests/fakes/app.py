from pathlib import Path

from fastapi import FastAPI

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.features.applications.analysis_run_store import (
    SqliteAnalysisRunStore,
)
from merida_api.features.resumes.run_store import SqliteResumeRunStore
from merida_api.features.resumes.checkpoint_vault import ResumeCheckpointVault

from .models import FakeApplicationAnalysisModel, FakeResumeDocumentBuilder
from .workspace import FakeWorkspace


def create_test_app(
    settings: Settings,
    *,
    state_path: Path | None = None,
    workspace=None,
    analysis_model=None,
    resume_builder=None,
    **options,
) -> FastAPI:
    """Compose the product ASGI surface with test-owned boundary fakes."""
    test_workspace = workspace or FakeWorkspace(
        state_path or settings.export_path.parent / "test-workspace.json"
    )
    state_path = state_path or settings.export_path.parent / "test-workspace.json"
    options.setdefault(
        "analysis_run_store",
        SqliteAnalysisRunStore(state_path.parent / "analysis-runs.sqlite3"),
    )
    options.setdefault(
        "resume_run_store",
        SqliteResumeRunStore(state_path.parent / "resume-runs.sqlite3"),
    )
    settings = settings.model_copy(
        update={
            "resume_checkpoint_key": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
            "resume_checkpoint_key_version": "test-key-1",
        }
    )
    return create_app(
        settings,
        workspace=test_workspace,
        analysis_model=analysis_model or FakeApplicationAnalysisModel(),
        resume_builder=resume_builder or FakeResumeDocumentBuilder(),
        **options,
    )
