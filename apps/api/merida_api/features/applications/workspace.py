from dataclasses import dataclass
from datetime import date
from typing import Literal


ApplicationStatus = Literal[
    "To Apply",
    "Applied",
    "Rejected",
    "Not Interested",
    "Archived",
]

SkillSignalCategory = Literal[
    "database",
    "api_integration",
    "framework_library",
    "programming_language",
    "cloud_platform",
    "testing_quality",
    "architecture_systems",
    "devops_tooling",
    "workflow_collaboration",
    "domain_knowledge",
    "other",
]

SkillSignalImportance = Literal["required", "preferred", "signal"]


@dataclass(frozen=True)
class SkillSignal:
    name: str
    category: SkillSignalCategory
    importance: SkillSignalImportance
    evidence: str


@dataclass(frozen=True)
class ApplicationAnalysisDraft:
    summary: tuple[str, str, str]
    skill_signals: tuple[SkillSignal, ...]


@dataclass(frozen=True)
class ApplicationAnalysisDocument:
    summary: str
    match_score: int | None
    skill_signals: tuple[str, ...]
    heading: Literal["Application Analysis", "Job Posting Analysis"]


@dataclass(frozen=True)
class ApplicationRecord:
    id: str
    url: str
    company_name: str
    role: str
    job_url: str
    captured_url: str | None
    location: str | None
    date_found: date
    application_status: ApplicationStatus
    analyzed: bool
    match_score: int | None
    resume_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    job_content: str | None = None
    analysis: ApplicationAnalysisDocument | None = None

    @property
    def title(self) -> str:
        return f"{self.role} at {self.company_name}"
