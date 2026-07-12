from pathlib import Path
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..applications.workspace import ApplicationAnalysisDocument, ApplicationRecord
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
    async def load_resume_application(
        self, application_id: str
    ) -> ApplicationRecord: ...
    async def load_resume_input(self, application_id: str) -> ApplicationRecord: ...
    async def find_completed_resume(
        self, application: ApplicationRecord
    ) -> ResumeRecord | None: ...
    async def find_resume_fit_note(
        self, application_id: str, resume_id: str
    ) -> NoteRecord | None: ...
    async def load_master_resume(self) -> ResumeDocument: ...
    async def create_resume_draft(
        self,
        name: str,
        document: tuple[DocumentBlock, ...],
        *,
        on_created: Callable[[ResumeRecord], None] | None = None,
    ) -> ResumeRecord: ...
    async def create_resume_fit_note(
        self,
        name: str,
        *,
        application_id: str,
        resume_id: str,
        document: tuple[DocumentBlock, ...],
        on_created: Callable[[NoteRecord], None] | None = None,
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
        self,
        application: ApplicationRecord,
        master_resume: ResumeDocument,
        *,
        run_id: str | None = None,
        workflow: str = "resume_creation",
    ) -> ResumeArtifactBundle: ...


class FitRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)
    type: Literal[
        "responsibility",
        "required skill",
        "preferred skill",
        "tool/technology",
        "seniority signal",
        "domain signal",
        "work-style signal",
        "qualification",
    ]
    category: str = Field(min_length=1, max_length=120)
    importance: Literal["required", "preferred", "signal"]
    evidence: str = Field(min_length=1, max_length=500)

    @property
    def name(self) -> str:
        return self.text


class FitRequirementsProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[FitRequirement] = Field(min_length=1, max_length=40)


class GeneratedBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(alias="evidenceIds", min_length=1, max_length=3)
    requirement_ids: list[str] = Field(alias="requirementIds", max_length=3)


class GeneratedRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_section: str = Field(alias="sourceSection", min_length=1, max_length=180)
    bullets: list[GeneratedBullet] = Field(min_length=1, max_length=7)


class GeneratedResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=900)
    roles: list[GeneratedRole] = Field(min_length=1, max_length=30)


class GeneratedResumeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume: GeneratedResume


class PromptEvidenceItem(BaseModel):
    id: str
    text: str
    source_section: str = Field(alias="sourceSection")


class PromptRoleTarget(BaseModel):
    source_section: str = Field(alias="sourceSection")
    evidence_ids: list[str] = Field(alias="evidenceIds")
    minimum_bullets: int = Field(alias="minimumBullets")
    preferred_bullets: int = Field(alias="preferredBullets")
    maximum_bullets: int = Field(alias="maximumBullets")


class PromptRequirement(BaseModel):
    id: str
    text: str
    type: str
    category: str
    importance: str
    evidence: str
    strength: str
    evidence_ids: list[str] = Field(alias="evidenceIds")


class PromptCategoryCoverage(BaseModel):
    category: str
    score: int
    requirement_count: int = Field(alias="requirementCount")


class ResumeDraftInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target: str
    supported_requirements: list[PromptRequirement] = Field(
        alias="supportedRequirements"
    )
    fit_score: int = Field(alias="fitScore")
    category_coverage: list[PromptCategoryCoverage] = Field(alias="categoryCoverage")
    role_targets: list[PromptRoleTarget] = Field(alias="roleTargets")
    evidence_items: list[PromptEvidenceItem] = Field(alias="evidenceItems")


class FitRequirementModel(Protocol):
    async def extract(
        self,
        job_content: str,
        analysis: ApplicationAnalysisDocument,
        *,
        repair_code: str | None = None,
    ) -> FitRequirementsProposal: ...


class ResumeDraftModel(Protocol):
    async def generate(
        self,
        input: ResumeDraftInput,
        *,
        repair_code: str | None = None,
    ) -> GeneratedResumeProposal: ...


class ResumePdfArtifacts(Protocol):
    def stage(self, document: tuple[DocumentBlock, ...]) -> Path: ...
    def publish(self, resume_id: str, staged: Path) -> Path: ...
    def discard(self, staged: Path) -> None: ...
    def save(
        self, resume_id: str, document: tuple[DocumentBlock, ...]
    ) -> Path: ...
    def remove(self, resume_id: str) -> None: ...
    def path(self, resume_id: str) -> Path | None: ...
