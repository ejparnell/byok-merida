from datetime import datetime, timezone

from .ports import CaptureStore
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


class ApplicationCapture:
    def __init__(self, store: CaptureStore):
        self._store = store
        self._pending_metadata: dict[str, tuple[str, tuple[str, ...]]] = {}

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
        normalized = ConfirmedApplicationDraft(
            jobUrl=canonicalize_url(draft.job_url),
            companyName=draft.company_name.strip(),
            role=draft.role.strip(),
            location=(draft.location or "").strip(),
            jobContent=draft.job_content.strip(),
        )
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
        if existing is not None:
            self._pending_metadata.pop(normalized.job_url, None)
            return _capture_result("already_captured", existing)
        captured_url, parsing_notes = self._pending_metadata.pop(
            normalized.job_url, (normalized.job_url, ())
        )
        created = await self._store.create_application(
            normalized,
            captured_at=datetime.now(timezone.utc),
            captured_url=captured_url,
            parsing_notes=parsing_notes,
        )
        return _capture_result("created", created)


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
