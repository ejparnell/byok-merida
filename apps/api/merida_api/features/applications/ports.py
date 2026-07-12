from datetime import datetime
from typing import Callable, Protocol

from .schemas import ConfirmedApplicationDraft
from .workspace import AnalysisModelResponse, ApplicationAnalysisDocument, ApplicationRecord
from ...shared.workspace import (
    QueuePage,
    WorkspaceReadiness,
)
from ...matching import EvidenceItem


class CaptureStore(Protocol):
    async def validate_capture_workspace(self) -> WorkspaceReadiness: ...
    async def find_application_by_job_url(
        self, job_url: str
    ) -> ApplicationRecord | None: ...
    async def create_application(
        self,
        draft: ConfirmedApplicationDraft,
        *,
        captured_at: datetime,
        captured_url: str | None = None,
        parsing_notes: tuple[str, ...] = (),
        on_created: Callable[[ApplicationRecord], None] | None = None,
    ) -> ApplicationRecord: ...
    async def capture_is_complete(self, application_id: str) -> bool: ...
    async def archive_application(self, application_id: str) -> None: ...


class ApplicationAnalysisStore(Protocol):
    async def validate_analysis_workspace(self) -> WorkspaceReadiness: ...
    async def list_analysis_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage[ApplicationRecord]: ...
    async def load_analysis_input(self, application_id: str) -> ApplicationRecord: ...
    async def load_analysis_evidence(self) -> tuple[EvidenceItem, ...]: ...
    async def append_application_analysis(
        self, application_id: str, document: ApplicationAnalysisDocument
    ) -> None: ...
    async def finalize_application_analysis(
        self, application_id: str, *, match_score: int | None
    ) -> None: ...


class ApplicationAnalysisModel(Protocol):
    async def generate(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> AnalysisModelResponse: ...
