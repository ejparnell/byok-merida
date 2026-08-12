import hashlib

from .ports import ApplicationAnalysisStore
from .schemas import (
    AnalysisQueueItem,
    ApplicationAnalysisQueueBlockedResponse,
    ApplicationAnalysisQueueReadyResponse,
)
from .workspace import ApplicationRecord
from ...shared.schemas import Pagination
from ...shared.pagination import InvalidCursor, decode_cursor, encode_cursor
from ...shared.workspace import (
    WorkspaceDataError,
    WorkspaceIssue,
    WorkspaceProviderError,
    WorkspaceReadiness,
    workspace_validation_failures,
)


class ApplicationAnalysis:
    def __init__(self, store: ApplicationAnalysisStore, *, run_store=None):
        self._store = store
        self._run_store = run_store

    async def validate_readiness(self) -> WorkspaceReadiness:
        readiness = await self._store.validate_analysis_workspace()
        if not readiness.ready:
            return readiness
        try:
            evidence = await self._store.load_analysis_evidence()
            if not evidence:
                raise WorkspaceDataError(
                    "Master Resume must contain readable evidence."
                )
        except WorkspaceDataError as error:
            return WorkspaceReadiness(
                errors=(
                    WorkspaceIssue(
                        database="resumes",
                        property="Master Resume",
                        message=str(error),
                    ),
                )
            )
        return readiness

    async def get_queue(
        self, limit: int, cursor: str | None
    ) -> ApplicationAnalysisQueueReadyResponse | ApplicationAnalysisQueueBlockedResponse:
        readiness = await self._store.validate_analysis_workspace()
        if not readiness.ready:
            return _blocked_queue(limit, readiness)
        quarantined = (
            set()
            if self._run_store is None
            else set(self._run_store.list_commit_quarantines())
        )
        if self._run_store is not None:
            for application_id in tuple(quarantined):
                try:
                    application = await self._store.load_analysis_input(
                        application_id
                    )
                except (WorkspaceDataError, WorkspaceProviderError):
                    continue
                if application.analysis is not None:
                    self._run_store.clear_commit_quarantine(application_id)
                    quarantined.remove(application_id)
        all_items = [
            item
            for item in await self._store.load_analysis_queue_snapshot(
                excluded_application_ids=frozenset(quarantined)
            )
            if item.id not in quarantined
        ]
        fingerprint = hashlib.sha256(
            "\n".join(item.id for item in all_items).encode()
        ).hexdigest()[:16]
        offset = decode_cursor(
            cursor, "application_analysis_visible", fingerprint
        )
        if offset > len(all_items):
            raise InvalidCursor("Cursor is invalid or expired.")
        items = all_items[offset : offset + limit]
        next_offset = offset + len(items)
        has_more = next_offset < len(all_items)
        return ApplicationAnalysisQueueReadyResponse(
            ok=True,
            queue_count=len(all_items),
            items=[_queue_item(item) for item in items],
            pagination=Pagination(
                limit=limit,
                next_cursor=(
                    encode_cursor(
                        next_offset,
                        "application_analysis_visible",
                        fingerprint,
                    )
                    if has_more
                    else None
                ),
                has_more=has_more,
            ),
            validation_failures=[],
            errors=[],
        )

def _queue_item(application: ApplicationRecord) -> AnalysisQueueItem:
    return AnalysisQueueItem(
        application_id=application.id,
        title=application.title,
        company_name=application.company_name,
        role=application.role,
        application_status="To Apply",
        job_url=application.job_url,
    )

def _blocked_queue(
    limit: int, readiness: WorkspaceReadiness
) -> ApplicationAnalysisQueueBlockedResponse:
    return ApplicationAnalysisQueueBlockedResponse(
        ok=False,
        status="blocked",
        queue_count=0,
        items=[],
        pagination=Pagination(limit=limit, next_cursor=None, has_more=False),
        validation_failures=workspace_validation_failures(readiness),
        errors=[issue.message for issue in readiness.errors],
    )
