from pathlib import Path
from typing import Protocol

from ..applications.workspace import ApplicationRecord
from .workspace import (
    DocumentBlock,
    NoteRecord,
    ResumeArtifactBundle,
    ResumeDocument,
    ResumeRecord,
)
from ...shared.workspace import (
    QueuePage,
    WorkspaceReadiness,
)


class ResumeCreationStore(Protocol):
    async def validate_resume_workspace(self) -> WorkspaceReadiness: ...
    async def list_resume_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage[ApplicationRecord]: ...
    async def load_resume_input(self, application_id: str) -> ApplicationRecord: ...
    async def find_completed_resume(
        self, application: ApplicationRecord
    ) -> ResumeRecord | None: ...
    async def find_resume_fit_note(
        self, application_id: str, resume_id: str
    ) -> NoteRecord | None: ...
    async def load_master_resume(self) -> ResumeDocument: ...
    async def create_resume_draft(
        self, name: str, document: tuple[DocumentBlock, ...]
    ) -> ResumeRecord: ...
    async def create_resume_fit_note(
        self,
        name: str,
        *,
        application_id: str,
        resume_id: str,
        document: tuple[DocumentBlock, ...],
    ) -> NoteRecord: ...
    async def attach_resume_to_application(
        self, resume_id: str, application_id: str
    ) -> ResumeRecord: ...
    async def clear_resume_application(self, resume_id: str) -> None: ...
    async def archive_note(self, note_id: str) -> None: ...
    async def archive_resume(self, resume_id: str) -> None: ...
    async def verify_recovery_artifacts(
        self,
        *,
        application_id: str,
        resume_id: str | None,
        note_id: str | None,
    ) -> bool: ...


class ResumeDocumentBuilder(Protocol):
    async def build(
        self, application: ApplicationRecord, master_resume: ResumeDocument
    ) -> ResumeArtifactBundle: ...


class ResumePdfArtifacts(Protocol):
    def save(self, resume_id: str, lines: tuple[str, ...]) -> Path: ...
    def remove(self, resume_id: str) -> None: ...
    def path(self, resume_id: str) -> Path | None: ...
