from dataclasses import dataclass
from typing import Generic, Literal, TypeVar


QueueItem = TypeVar("QueueItem")


@dataclass(frozen=True)
class WorkspaceIssue:
    database: Literal["applications", "resumes", "notes"]
    property: str | None
    message: str


@dataclass(frozen=True)
class WorkspaceReadiness:
    errors: tuple[WorkspaceIssue, ...] = ()
    warnings: tuple[WorkspaceIssue, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class QueuePage(Generic[QueueItem]):
    items: tuple[QueueItem, ...]
    total: int
    limit: int
    next_cursor: str | None
    has_more: bool


class WorkspaceDataError(RuntimeError):
    """A safe, record-level workspace error."""


class WorkspaceDataConflict(WorkspaceDataError):
    """The workspace contains more than one record for a unique domain key."""


class WorkspaceProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable


def workspace_validation_failures(
    readiness: WorkspaceReadiness,
):
    from .schemas import WorkspaceSchemaValidationFailure

    return [
        WorkspaceSchemaValidationFailure(
            kind="workspace_schema",
            database=issue.database,
            property=issue.property,
            message=issue.message,
        )
        for issue in readiness.errors
    ]
