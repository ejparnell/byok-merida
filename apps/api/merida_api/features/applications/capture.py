from .ports import CaptureStore
from .schemas import CaptureEvidence, ConfirmedApplicationDraft
from ..job_postings.parser import canonicalize_url, prepare_capture


class ApplicationCapture:
    def __init__(self, store: CaptureStore):
        self._store = store

    async def prepare(self, evidence: CaptureEvidence) -> dict:
        draft, _job_content, errors = prepare_capture(evidence)
        missing_fields = []
        if not draft["companyName"]:
            missing_fields.append("companyName")
        if not draft["role"]:
            missing_fields.append("role")
        if len(_job_content) < 20:
            missing_fields.append("jobContent")
        return {
            "ok": True,
            "result": "prepared" if not errors else "needs_review",
            "draft": draft,
            "needsReview": bool(errors),
            "reviewReasons": errors,
            "missingFields": missing_fields,
            "validationFailures": [],
            "errors": [],
        }

    async def confirm(self, draft: ConfirmedApplicationDraft) -> dict:
        normalized = ConfirmedApplicationDraft(
            jobUrl=canonicalize_url(draft.job_url),
            companyName=draft.company_name.strip(),
            role=draft.role.strip(),
            location=(draft.location or "").strip(),
            jobContent=draft.job_content.strip(),
        )
        return await self._store.confirm_capture(normalized)
