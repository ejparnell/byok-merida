from .commit import ResumeArtifactCommitter
from .ports import ResumeCreationStore, ResumeDocumentBuilder
from .schemas import (
    CleanupSummary,
    PdfArtifactSummary,
    ResumeAlreadyCreatedResponse,
    ResumeApplicationSummary,
    ResumeArtifactSummary,
    ResumeCreatedResponse,
    ResumeCreationBlockedResponse,
    ResumeCreationFailedResponse,
    ResumeCreationQueueBlockedResponse,
    ResumeCreationQueueReadyResponse,
    ResumeQueueItem,
)
from .workspace import NoteRecord, ResumeRecord
from ..applications.workspace import ApplicationRecord
from ...shared.schemas import Pagination
from ...shared.workspace import (
    WorkspaceDataError,
    WorkspaceProviderError,
    WorkspaceReadiness,
    workspace_validation_failures,
)
from ...shared.execution import ExecutionCoordinator, OperationConflict
from ...shared.recovery import EffectJournal


class ResumeCreation:
    def __init__(
        self,
        store: ResumeCreationStore,
        builder: ResumeDocumentBuilder,
        committer: ResumeArtifactCommitter,
        coordinator: ExecutionCoordinator,
        journal: EffectJournal | None = None,
    ):
        self._store = store
        self._builder = builder
        self._committer = committer
        self._coordinator = coordinator
        self._journal = journal

    async def get_queue(
        self, limit: int, cursor: str | None
    ) -> ResumeCreationQueueReadyResponse | ResumeCreationQueueBlockedResponse:
        readiness = await self._store.validate_resume_workspace()
        if not readiness.ready:
            return _blocked_queue(limit, readiness)
        page = await self._store.list_resume_queue(limit=limit, cursor=cursor)
        return ResumeCreationQueueReadyResponse(
            ok=True,
            queue_count=page.total,
            items=[_queue_item(item) for item in page.items],
            pagination=Pagination(
                limit=page.limit,
                next_cursor=page.next_cursor,
                has_more=page.has_more,
            ),
            validation_failures=[],
            errors=[],
        )

    async def create(
        self, application_id: str
    ) -> (
        ResumeCreatedResponse
        | ResumeAlreadyCreatedResponse
        | ResumeCreationBlockedResponse
        | ResumeCreationFailedResponse
    ):
        if self._journal is not None and not self._journal.available:
            return ResumeCreationBlockedResponse(
                ok=False,
                status="blocked",
                result="blocked",
                cleanup=CleanupSummary(status="not_required", errors=[]),
                validation_failures=[],
                errors=[self._journal.error or "Recovery journal is unavailable."],
            )
        async with self._coordinator.exclusive(
            "workflow:resume-creation",
            "Resume Creation is already in progress.",
        ) as run:
            async with self._coordinator.exclusive(
                f"application:{application_id}",
                "This Application is already being updated.",
            ):
                if self._journal and self._journal.unresolved(
                    workflow="resume_creation", domain_key=application_id
                ):
                    raise OperationConflict(
                        "Resume Creation requires recovery for this Application."
                    )
                return await self._create(application_id, run.run_id)

    async def _create(
        self, application_id: str, run_id: str
    ) -> (
        ResumeCreatedResponse
        | ResumeAlreadyCreatedResponse
        | ResumeCreationBlockedResponse
        | ResumeCreationFailedResponse
    ):
        try:
            readiness = await self._store.validate_resume_workspace()
            if not readiness.ready:
                return _blocked(readiness)
            application = await self._store.load_resume_input(application_id)
            existing = await self._store.find_completed_resume(application)
            if existing is not None:
                note = await self._store.find_resume_fit_note(
                    application.id, existing.id
                )
                return _success(
                    "already_created",
                    application,
                    existing,
                    note,
                    self._committer.pdf_path(existing.id),
                )
            master_resume = await self._store.load_master_resume()
            bundle = await self._builder.build(application, master_resume)
        except (WorkspaceDataError, WorkspaceProviderError) as exc:
            return ResumeCreationBlockedResponse(
                ok=False,
                status="blocked",
                result="blocked",
                cleanup=CleanupSummary(status="not_required", errors=[]),
                validation_failures=[],
                errors=[str(exc)],
            )

        committed = await self._committer.commit(
            application, bundle, run_id=run_id
        )
        if committed.committed:
            assert committed.resume is not None
            assert committed.note is not None
            assert committed.pdf_path is not None
            return _success(
                "created",
                application,
                committed.resume,
                committed.note,
                committed.pdf_path,
            )
        return ResumeCreationFailedResponse(
            ok=False,
            status="failed",
            result="failed",
            cleanup=CleanupSummary(
                status=committed.cleanup_status,
                errors=list(committed.cleanup_errors),
            ),
            validation_failures=[],
            errors=["Resume artifacts could not be committed."],
        )

    def pdf_path(self, resume_id: str):
        return self._committer.pdf_path(resume_id)

    async def reconcile(self, run_id: str | None = None) -> None:
        if self._journal is None:
            return
        for entry in self._journal.unresolved(workflow="resume_creation"):
            if run_id is not None and entry.run_id != run_id:
                continue
            try:
                application = await self._store.load_resume_input(entry.domain_key)
                completed = await self._store.find_completed_resume(application)
            except Exception:
                continue
            if completed is not None and completed.id == entry.resume_id:
                self._journal.resolve(entry.run_id, resolution="completed")
                continue
            if completed is not None:
                self._journal.resolve(
                    entry.run_id,
                    resolution="active",
                    cleanup_status="incomplete",
                    cleanup_errors=(
                        "A different completed Resume relation requires manual recovery.",
                    ),
                )
                continue
            status, errors = await self._committer.reconcile(entry)
            self._journal.resolve(
                entry.run_id,
                resolution="cleaned" if status == "completed" else "active",
                cleanup_status=status,
                cleanup_errors=errors,
            )


def _queue_item(application: ApplicationRecord) -> ResumeQueueItem:
    assert application.match_score is not None
    return ResumeQueueItem(
        application_id=application.id,
        title=application.title,
        company_name=application.company_name,
        role=application.role,
        application_status="To Apply",
        job_url=application.job_url,
        match_score=application.match_score,
        analyzed=True,
        has_resume=False,
    )


def _success(
    result: str,
    application: ApplicationRecord,
    resume: ResumeRecord,
    note: NoteRecord | None,
    pdf_path,
) -> ResumeCreatedResponse | ResumeAlreadyCreatedResponse:
    application_summary = ResumeApplicationSummary(
        id=application.id,
        title=application.title,
        company_name=application.company_name,
        role=application.role,
    )
    pdf = (
        PdfArtifactSummary(
            filename=pdf_path.name,
            download_url=f"/api/v1/resumes/{resume.id}/pdf",
        )
        if pdf_path
        else None
    )
    if result == "already_created":
        return ResumeAlreadyCreatedResponse(
            ok=True,
            result="already_created",
            application=application_summary,
            resume=_artifact(resume, application),
            note=_artifact(note, application) if note else None,
            pdf=pdf,
            validation_failures=[],
            errors=[],
        )
    assert note is not None
    assert pdf is not None
    return ResumeCreatedResponse(
        ok=True,
        result="created",
        application=application_summary,
        resume=_artifact(resume, application),
        note=_artifact(note, application),
        pdf=pdf,
        validation_failures=[],
        errors=[],
    )


def _artifact(record, application: ApplicationRecord) -> ResumeArtifactSummary:
    return ResumeArtifactSummary(
        id=record.id,
        title=record.name,
        company_name=application.company_name,
        role=application.role,
        url=record.url,
    )


def _blocked(readiness: WorkspaceReadiness) -> ResumeCreationBlockedResponse:
    return ResumeCreationBlockedResponse(
        ok=False,
        status="blocked",
        result="blocked",
        cleanup=CleanupSummary(status="not_required", errors=[]),
        validation_failures=workspace_validation_failures(readiness),
        errors=[issue.message for issue in readiness.errors],
    )


def _blocked_queue(
    limit: int, readiness: WorkspaceReadiness
) -> ResumeCreationQueueBlockedResponse:
    return ResumeCreationQueueBlockedResponse(
        ok=False,
        status="blocked",
        queue_count=0,
        items=[],
        pagination=Pagination(limit=limit, next_cursor=None, has_more=False),
        validation_failures=workspace_validation_failures(readiness),
        errors=[issue.message for issue in readiness.errors],
    )
