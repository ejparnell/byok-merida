from pathlib import Path

from fastapi import FastAPI

from merida_api.app import create_app
from merida_api.core.settings import Settings

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
    return create_app(
        settings,
        workspace=test_workspace,
        analysis_model=analysis_model or FakeApplicationAnalysisModel(),
        resume_builder=resume_builder or FakeResumeDocumentBuilder(),
        **options,
    )
