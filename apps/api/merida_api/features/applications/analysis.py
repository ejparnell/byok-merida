from .ports import ApplicationAnalysisModel, ApplicationAnalysisStore
from .schemas import (
    AnalysisQueueItem,
    AnalysisResultItem,
    ApplicationAnalysisBlockedResponse,
    ApplicationAnalysisCompletedResponse,
    ApplicationAnalysisQueueBlockedResponse,
    ApplicationAnalysisQueueReadyResponse,
)
from .workspace import ApplicationAnalysisDocument, ApplicationRecord
from ...shared.schemas import Pagination
from ...shared.workspace import WorkspaceReadiness, workspace_validation_failures
from ...shared.execution import ExecutionCoordinator
from ...matching import EvidenceMatchingEngine


class ApplicationAnalysis:
    def __init__(
        self,
        store: ApplicationAnalysisStore,
        model: ApplicationAnalysisModel,
        coordinator: ExecutionCoordinator,
        matcher: EvidenceMatchingEngine | None = None,
    ):
        self._store = store
        self._model = model
        self._coordinator = coordinator
        self._matcher = matcher or EvidenceMatchingEngine()

    async def get_queue(
        self, limit: int, cursor: str | None
    ) -> ApplicationAnalysisQueueReadyResponse | ApplicationAnalysisQueueBlockedResponse:
        readiness = await self._store.validate_analysis_workspace()
        if not readiness.ready:
            return _blocked_queue(limit, readiness)
        page = await self._store.list_analysis_queue(limit=limit, cursor=cursor)
        return ApplicationAnalysisQueueReadyResponse(
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

    async def run_batch(
        self, limit: int
    ) -> ApplicationAnalysisCompletedResponse | ApplicationAnalysisBlockedResponse:
        async with self._coordinator.exclusive(
            "workflow:application-analysis",
            "Job Posting Analysis is already in progress.",
        ):
            return await self._run_batch(limit)

    async def _run_batch(
        self, limit: int
    ) -> ApplicationAnalysisCompletedResponse | ApplicationAnalysisBlockedResponse:
        readiness = await self._store.validate_analysis_workspace()
        if not readiness.ready:
            return ApplicationAnalysisBlockedResponse(
                ok=False,
                status="blocked",
                result="blocked",
                processed=0,
                succeeded=0,
                failed=0,
                repaired=0,
                items=[],
                validation_failures=workspace_validation_failures(readiness),
                errors=[issue.message for issue in readiness.errors],
            )
        queue = await self._store.list_analysis_queue(limit=limit, cursor=None)
        results = []
        repaired = 0
        failed = 0
        succeeded = 0
        for queued in queue.items:
            application = queued
            try:
                async with self._coordinator.exclusive(
                    f"application:{queued.id}",
                    "This Application is already being updated.",
                ):
                    application = await self._store.load_analysis_input(queued.id)
                    if (
                        application.application_status != "To Apply"
                        or application.analyzed
                        or len((application.job_content or "").strip()) < 20
                    ):
                        results.append(
                            _result_item(
                                application,
                                "skipped",
                                application.match_score,
                                ["Job Posting is no longer eligible for Analysis."],
                            )
                        )
                        continue
                    if application.analysis is not None:
                        repair_score = (
                            application.analysis.match_score
                            if application.analysis.match_score is not None
                            else application.match_score
                        )
                        await self._store.finalize_application_analysis(
                            application.id,
                            match_score=repair_score,
                        )
                        result = "repaired"
                        score = repair_score
                        repaired += 1
                    else:
                        draft = await self._model.analyze(application)
                        evidence = await self._store.load_analysis_evidence()
                        matching = self._matcher.score(draft.skill_signals, evidence)
                        document = ApplicationAnalysisDocument(
                            summary=" ".join(draft.summary),
                            match_score=matching.score,
                            skill_signals=tuple(
                                _persisted_skill_signal(signal)
                                for signal in draft.skill_signals
                            ),
                            heading="Application Analysis",
                        )
                        await self._store.append_application_analysis(
                            application.id, document
                        )
                        await self._store.finalize_application_analysis(
                            application.id, match_score=document.match_score
                        )
                        result = "analyzed"
                        score = document.match_score
                    succeeded += 1
                    results.append(_result_item(application, result, score, []))
            except Exception:
                failed += 1
                results.append(
                    _result_item(
                        application,
                        "failed",
                        None,
                        ["Application Analysis failed for this item."],
                    )
                )
        return ApplicationAnalysisCompletedResponse(
            ok=True,
            result="completed",
            processed=len(results),
            succeeded=succeeded,
            failed=failed,
            repaired=repaired,
            items=results,
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


def _result_item(
    application: ApplicationRecord,
    result: str,
    score: int | None,
    errors: list[str],
) -> AnalysisResultItem:
    return AnalysisResultItem(
        **_queue_item(application).model_dump(),
        result=result,
        match_score=score,
        errors=errors,
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


def _persisted_skill_signal(signal) -> str:
    return (
        f"{signal.category} | {signal.importance} | "
        f"{signal.name} | Evidence: {signal.evidence}"
    )
