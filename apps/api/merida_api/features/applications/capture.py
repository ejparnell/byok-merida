from .ports import CaptureStore
from .schemas import CaptureEvidence, ConfirmedDraft
from ..job_postings.parser import canonicalize_url, prepare_capture


class ApplicationCapture:
    def __init__(self, store: CaptureStore):
        self._store = store

    async def prepare(self, evidence: CaptureEvidence) -> dict:
        draft, _job_content, errors = prepare_capture(evidence)
        return {
            "ok": not errors,
            "status": "ready" if not errors else "needs_review",
            "result": "prepared" if not errors else "needs_review",
            "draft": draft,
            "needsReview": bool(errors),
            "validationFailures": [],
            "errors": errors,
        }

    async def confirm(self, draft: ConfirmedDraft) -> dict:
        normalized = ConfirmedDraft(
            jobUrl=canonicalize_url(draft.job_url),
            companyName=draft.company_name.strip(),
            role=draft.role.strip(),
            location=draft.location.strip(),
            jobContent=draft.job_content.strip(),
        )
        return await self._store.confirm_capture(normalized)
