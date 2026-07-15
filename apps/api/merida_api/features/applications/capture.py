from datetime import datetime, timezone

from .ports import CaptureStore
from .capture_matches import find_capture_matches
from .schemas import (
    ApplicationAlreadyCapturedResponse,
    ApplicationCaptureBlockedResponse,
    ApplicationCreatedResponse,
    ApplicationNeedsReviewResponse,
    CaptureEvidence,
    CapturedApplication,
    ConfirmedApplicationDraft,
    PreparedApplicationDraft,
    PreparedApplicationResponse,
)
from .workspace import ApplicationRecord
from ..job_postings.parser import canonicalize_url, prepare_capture
from ...shared.workspace import workspace_validation_failures
from ...shared.execution import ExecutionCoordinator, OperationConflict
from ...shared.recovery import EffectJournal


class ApplicationCapture:
    def __init__(
        self,
        store: CaptureStore,
        coordinator: ExecutionCoordinator | None = None,
        journal: EffectJournal | None = None,
    ):
        self._store = store
        self._coordinator = coordinator or ExecutionCoordinator()
        self._journal = journal
        self._pending_metadata: dict[str, tuple[str, tuple[str, ...]]] = {}

    async def validate_readiness(self):
        return await self._store.validate_capture_workspace()

    async def find_matches(
        self, company_name: str, role: str
    ) -> tuple[ApplicationRecord, ...]:
        return find_capture_matches(
            await self._store.list_active_applications(), company_name, role
        )

    async def prepare(
        self, evidence: CaptureEvidence
    ) -> PreparedApplicationResponse | ApplicationNeedsReviewResponse:
        draft, _job_content, errors = prepare_capture(evidence)
        if draft["jobUrl"]:
            canonical_url = canonicalize_url(draft["jobUrl"])
            self._pending_metadata[canonical_url] = (evidence.url, tuple(errors))
            while len(self._pending_metadata) > 20:
                self._pending_metadata.pop(next(iter(self._pending_metadata)))
        missing_fields = []
        if not draft["companyName"]:
            missing_fields.append("companyName")
        if not draft["role"]:
            missing_fields.append("role")
        if len(_job_content) < 20:
            missing_fields.append("jobContent")
        response_type = (
            ApplicationNeedsReviewResponse if errors else PreparedApplicationResponse
        )
        return response_type(
            ok=True,
            result="needs_review" if errors else "prepared",
            draft=PreparedApplicationDraft.model_validate(draft),
            needs_review=bool(errors),
            review_reasons=errors,
            missing_fields=missing_fields,
            validation_failures=[],
            errors=[],
        )

    async def confirm(
        self, draft: ConfirmedApplicationDraft
    ) -> (
        ApplicationCreatedResponse
        | ApplicationAlreadyCapturedResponse
        | ApplicationCaptureBlockedResponse
    ):
        if self._journal is not None and not self._journal.available:
            return ApplicationCaptureBlockedResponse(
                ok=False,
                status="blocked",
                result="blocked",
                validation_failures=[],
                errors=[self._journal.error or "Recovery journal is unavailable."],
            )
        normalized = ConfirmedApplicationDraft(
            jobUrl=canonicalize_url(draft.job_url),
            companyName=draft.company_name.strip(),
            role=draft.role.strip(),
            location=(draft.location or "").strip(),
            jobContent=draft.job_content.strip(),
        )
        async with self._coordinator.exclusive(
            f"capture:{normalized.job_url}",
            "Application Capture is already in progress for this Job URL.",
        ) as run:
            readiness = await self._store.validate_capture_workspace()
            if not readiness.ready:
                return ApplicationCaptureBlockedResponse(
                    ok=False,
                    status="blocked",
                    result="blocked",
                    validation_failures=workspace_validation_failures(readiness),
                    errors=[issue.message for issue in readiness.errors],
                )
            existing = await self._store.find_application_by_job_url(normalized.job_url)
            unresolved = (
                self._journal.unresolved(
                    workflow="capture", domain_key=normalized.job_url
                )
                if self._journal
                else ()
            )
            if existing is not None:
                complete = await self._store.capture_is_complete(existing.id)
                if complete:
                    for entry in unresolved:
                        self._journal.resolve(entry.run_id, resolution="completed")
                    self._pending_metadata.pop(normalized.job_url, None)
                    return _capture_result("already_captured", existing)
                owned = any(
                    entry.application_id == existing.id for entry in unresolved
                )
                if not owned:
                    raise OperationConflict(
                        "An incomplete Application requires manual recovery."
                    )
                await self._store.archive_application(existing.id)
                for entry in unresolved:
                    self._journal.resolve(
                        entry.run_id,
                        resolution="cleaned",
                        cleanup_status="completed",
                    )
            for entry in unresolved:
                self._journal.resolve(
                    entry.run_id,
                    resolution="cleaned",
                    cleanup_status="completed",
                )
            captured_url, parsing_notes = self._pending_metadata.pop(
                normalized.job_url, (normalized.job_url, ())
            )
            if self._journal:
                self._journal.start(
                    workflow="capture",
                    domain_key=normalized.job_url,
                    run_id=run.run_id,
                )

            def record_created(application: ApplicationRecord) -> None:
                if self._journal:
                    self._journal.advance(
                        run.run_id,
                        phase="application_created",
                        application_id=application.id,
                    )

            created = await self._store.create_application(
                normalized,
                captured_at=datetime.now(timezone.utc),
                captured_url=captured_url,
                parsing_notes=parsing_notes,
                on_created=record_created,
            )
            if self._journal:
                self._journal.resolve(run.run_id, resolution="completed")
            return _capture_result("created", created)

    async def reconcile(self, run_id: str | None = None) -> None:
        if self._journal is None:
            return
        entries = self._journal.unresolved(workflow="capture")
        for entry in entries:
            if run_id is not None and entry.run_id != run_id:
                continue
            try:
                existing = await self._store.find_application_by_job_url(
                    entry.domain_key
                )
                if existing is None:
                    self._journal.resolve(
                        entry.run_id,
                        resolution="cleaned",
                        cleanup_status="completed",
                    )
                    continue
                if await self._store.capture_is_complete(existing.id):
                    self._journal.resolve(entry.run_id, resolution="completed")
                    continue
                if entry.application_id == existing.id:
                    await self._store.archive_application(existing.id)
                    self._journal.resolve(
                        entry.run_id,
                        resolution="cleaned",
                        cleanup_status="completed",
                    )
                    continue
                self._journal.resolve(
                    entry.run_id,
                    resolution="active",
                    cleanup_status="incomplete",
                    cleanup_errors=(
                        "Incomplete Application ownership requires manual recovery.",
                    ),
                )
            except Exception:
                continue


def _capture_result(
    result: str, application: ApplicationRecord
) -> ApplicationCreatedResponse | ApplicationAlreadyCapturedResponse:
    captured = CapturedApplication(
        id=application.id,
        title=application.title,
        company_name=application.company_name,
        role=application.role,
        location=application.location,
        job_url=application.job_url,
        application_status="To Apply",
        url=application.url,
    )
    if result == "already_captured":
        return ApplicationAlreadyCapturedResponse(
            ok=True,
            result="already_captured",
            application=captured,
            validation_failures=[],
            errors=[],
        )
    return ApplicationCreatedResponse(
        ok=True,
        result="created",
        application=captured,
        validation_failures=[],
        errors=[],
    )
