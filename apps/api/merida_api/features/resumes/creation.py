from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .commit import ResumeArtifactCommitter
from .ports import ResumeCreationStore, ResumeDocumentBuilder
from .resume_builder import (
    ResumeEvidenceError,
    ResumeGenerationError,
    ResumeModelOutputError,
    validate_master_resume_readiness,
)
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
from .workspace import (
    NoteRecord,
    ResumeArtifactBundle,
    ResumeDocument,
    ResumeRecord,
)
from ..applications.workspace import ApplicationRecord
from ...shared.schemas import Pagination
from ...shared.workspace import (
    WorkspaceDataError,
    WorkspaceIssue,
    WorkspaceProviderError,
    WorkspaceReadiness,
    workspace_validation_failures,
)
from ...shared.execution import ExecutionCoordinator, OperationConflict
from ...shared.recovery import EffectJournal
from ...shared.observability import log_workflow_outcome, workflow_timer
from ...matching import SCORING_POLICY_VERSION


ResumeCreationOutcome = (
    ResumeCreatedResponse
    | ResumeAlreadyCreatedResponse
    | ResumeCreationBlockedResponse
    | ResumeCreationFailedResponse
)


class _ResumeCreationState(TypedDict, total=False):
    workflow: str
    application_id: str
    run_id: str
    application: ApplicationRecord
    existing: ResumeRecord | None
    master_resume: ResumeDocument
    bundle: ResumeArtifactBundle
    staged_pdf: Path
    outcome: ResumeCreationOutcome


class ResumeCreationGraph:
    def __init__(
        self,
        store: ResumeCreationStore,
        builder: ResumeDocumentBuilder,
        committer: ResumeArtifactCommitter,
    ):
        self._store = store
        self._builder = builder
        self._committer = committer
        self._graph = self._build_graph()

    async def run(self, application_id: str, run_id: str) -> ResumeCreationOutcome:
        try:
            state = await self._graph.ainvoke(
                {
                    "workflow": "resume_creation",
                    "application_id": application_id,
                    "run_id": run_id,
                }
            )
            return state["outcome"]
        except Exception:
            return _generation_failed()

    def _build_graph(self):
        graph = StateGraph(_ResumeCreationState)
        graph.add_node("load_and_find_existing_resume", self._load_and_find)
        graph.add_node("return_existing_resume", self._return_existing)
        graph.add_node("validate_resume_workspace", self._validate_workspace)
        graph.add_node("load_application_sources", self._load_sources)
        graph.add_node("build_resume_document", self._build_document)
        graph.add_node("stage_pdf", self._stage_pdf)
        graph.add_node("commit_artifacts", self._commit_artifacts)
        graph.add_edge(START, "load_and_find_existing_resume")
        graph.add_conditional_edges(
            "load_and_find_existing_resume",
            self._after_existing,
            {
                "existing": "return_existing_resume",
                "continue": "validate_resume_workspace",
                "terminal": END,
            },
        )
        graph.add_edge("return_existing_resume", END)
        graph.add_conditional_edges(
            "validate_resume_workspace",
            self._terminal_or_continue,
            {"continue": "load_application_sources", "terminal": END},
        )
        graph.add_conditional_edges(
            "load_application_sources",
            self._terminal_or_continue,
            {"continue": "build_resume_document", "terminal": END},
        )
        graph.add_conditional_edges(
            "build_resume_document",
            self._terminal_or_continue,
            {"continue": "stage_pdf", "terminal": END},
        )
        graph.add_conditional_edges(
            "stage_pdf",
            self._terminal_or_continue,
            {"continue": "commit_artifacts", "terminal": END},
        )
        graph.add_edge("commit_artifacts", END)
        return graph.compile()

    async def _load_and_find(self, state: _ResumeCreationState) -> dict:
        try:
            application = await self._store.load_resume_application(
                state["application_id"]
            )
            existing = await self._store.find_completed_resume(application)
            return {"application": application, "existing": existing}
        except WorkspaceDataError as error:
            return {"outcome": _blocked_error(str(error))}
        except WorkspaceProviderError:
            return {"outcome": _blocked_error("Notion could not be reached.")}

    def _after_existing(self, state: _ResumeCreationState) -> str:
        if "outcome" in state:
            return "terminal"
        return "existing" if state.get("existing") is not None else "continue"

    async def _return_existing(self, state: _ResumeCreationState) -> dict:
        application = state["application"]
        existing = state["existing"]
        assert existing is not None
        try:
            note = await self._store.find_resume_fit_note(application.id, existing.id)
        except WorkspaceDataError as error:
            return {"outcome": _blocked_error(str(error))}
        except WorkspaceProviderError:
            return {"outcome": _blocked_error("Notion could not be reached.")}
        return {
            "outcome": _success(
                "already_created",
                application,
                existing,
                note,
                self._committer.pdf_path(existing.id),
            )
        }

    async def _validate_workspace(self, state: _ResumeCreationState) -> dict:
        del state
        try:
            readiness = await self._store.validate_resume_workspace()
        except WorkspaceProviderError:
            return {"outcome": _blocked_error("Notion could not be reached.")}
        return {} if readiness.ready else {"outcome": _blocked(readiness)}

    async def _load_sources(self, state: _ResumeCreationState) -> dict:
        try:
            return {
                "application": await self._store.load_resume_input(
                    state["application_id"]
                ),
                "master_resume": await self._store.load_master_resume(),
            }
        except WorkspaceDataError as error:
            return {"outcome": _blocked_error(str(error))}

    async def _build_document(self, state: _ResumeCreationState) -> dict:
        try:
            return {
                "bundle": await self._builder.build(
                    state["application"],
                    state["master_resume"],
                    run_id=state["run_id"],
                    workflow=state["workflow"],
                )
            }
        except ResumeEvidenceError as error:
            return {"outcome": _blocked_error(str(error))}
        except (ResumeModelOutputError, ResumeGenerationError):
            return {"outcome": _generation_failed()}

    async def _commit_artifacts(self, state: _ResumeCreationState) -> dict:
        application = state["application"]
        committed = await self._committer.commit(
            application,
            state["bundle"],
            run_id=state["run_id"],
            staged_pdf=state["staged_pdf"],
        )
        if committed.committed:
            assert committed.resume is not None
            assert committed.note is not None
            assert committed.pdf_path is not None
            return {
                "outcome": _success(
                    "created",
                    application,
                    committed.resume,
                    committed.note,
                    committed.pdf_path,
                )
            }
        return {
            "outcome": ResumeCreationFailedResponse(
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
        }

    async def _stage_pdf(self, state: _ResumeCreationState) -> dict:
        try:
            return {"staged_pdf": self._committer.stage(state["bundle"])}
        except Exception:
            return {"outcome": _generation_failed()}

    def _terminal_or_continue(self, state: _ResumeCreationState) -> str:
        return "terminal" if "outcome" in state else "continue"


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
        self._creation_graph = ResumeCreationGraph(store, builder, committer)

    async def validate_readiness(self) -> WorkspaceReadiness:
        readiness = await self._store.validate_resume_workspace()
        if not readiness.ready:
            return readiness
        try:
            master_resume = await self._store.load_master_resume()
            validate_master_resume_readiness(master_resume)
        except (WorkspaceDataError, ResumeEvidenceError) as error:
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
        started_at = workflow_timer()
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
                outcome = await self._create(application_id, run.run_id)
                log_workflow_outcome(
                    workflow="resume_creation",
                    record_id=application_id,
                    outcome_code=outcome.result,
                    policy_version=SCORING_POLICY_VERSION,
                    started_at=started_at,
                )
                return outcome

    async def _create(
        self, application_id: str, run_id: str
    ) -> ResumeCreationOutcome:
        return await self._creation_graph.run(application_id, run_id)

    def pdf_path(self, resume_id: str):
        return self._committer.pdf_path(resume_id)

    async def reconcile(self, run_id: str | None = None) -> None:
        if self._journal is None:
            return
        for entry in self._journal.unresolved(workflow="resume_creation"):
            if run_id is not None and entry.run_id != run_id:
                continue
            try:
                application = await self._store.load_resume_application(
                    entry.domain_key
                )
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


def _blocked_error(message: str) -> ResumeCreationBlockedResponse:
    return ResumeCreationBlockedResponse(
        ok=False,
        status="blocked",
        result="blocked",
        cleanup=CleanupSummary(status="not_required", errors=[]),
        validation_failures=[],
        errors=[message],
    )


def _generation_failed() -> ResumeCreationFailedResponse:
    return ResumeCreationFailedResponse(
        ok=False,
        status="failed",
        result="failed",
        cleanup=CleanupSummary(status="not_required", errors=[]),
        validation_failures=[],
        errors=["Resume generation could not be completed."],
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
