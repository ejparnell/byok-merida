from dataclasses import dataclass
from datetime import date
from typing import Any, Literal


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
class AnalysisModelResponse:
    payload: dict[str, Any] | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class PersistedSkillSignal:
    text: str
    name: str

    @classmethod
    def from_signal(cls, signal: SkillSignal) -> "PersistedSkillSignal":
        return cls(
            text=(
                f"{signal.category} | {signal.importance} | "
                f"{signal.name} | Evidence: {signal.evidence}"
            ),
            name=signal.name,
        )

    @classmethod
    def from_text(cls, text: str) -> "PersistedSkillSignal":
        value = str(text).strip()
        name = value
        if " | " in value:
            fields = value.split(" | ")
            if len(fields) >= 3:
                name = fields[2]
        elif ":" in value:
            name = value.split(":", 1)[1].strip()
        return cls(text=value, name=name)


@dataclass(frozen=True)
class ApplicationAnalysisDocument:
    summary: str
    match_score: int | None
    skill_signals: tuple[PersistedSkillSignal, ...]
    heading: Literal["Application Analysis", "Job Posting Analysis"]

    def __post_init__(self):
        object.__setattr__(
            self,
            "skill_signals",
            tuple(
                PersistedSkillSignal.from_text(signal)
                if isinstance(signal, str)
                else signal
                for signal in self.skill_signals
            ),
        )


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
