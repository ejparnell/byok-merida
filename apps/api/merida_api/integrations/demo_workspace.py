import asyncio
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from ..features.applications.schemas import ConfirmedApplicationDraft
from ..features.applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
)
from ..features.resumes.workspace import (
    DocumentBlock,
    NoteRecord,
    ResumeDocument,
    ResumeRecord,
)
from ..shared.pagination import InvalidCursor, decode_cursor, encode_cursor
from ..shared.workspace import (
    QueuePage,
    WorkspaceDataConflict,
    WorkspaceDataError,
    WorkspaceReadiness,
)


def initial_demo_state() -> dict:
    return {
        "applications": [
            {
                "id": "app-northstar",
                "companyName": "Northstar Labs",
                "role": "Senior Frontend Engineer",
                "jobUrl": "https://jobs.example.test/northstar/frontend",
                "jobContent": "Build accessible React interfaces, REST APIs, design systems, and reliable automated tests.",
                "applicationStatus": "To Apply",
                "dateFound": "2026-07-01",
                "analyzed": False,
                "matchScore": None,
                "analysis": None,
                "resumeId": None,
            },
            {
                "id": "app-lantern",
                "companyName": "Lantern Health",
                "role": "Full Stack Engineer",
                "jobUrl": "https://jobs.example.test/lantern/full-stack",
                "jobContent": "Develop Python services, REST APIs, React workflows, PostgreSQL data models, and integration tests.",
                "applicationStatus": "To Apply",
                "dateFound": "2026-07-02",
                "analyzed": False,
                "matchScore": None,
                "analysis": None,
                "resumeId": None,
            },
            {
                "id": "app-orbit",
                "companyName": "Orbit Works",
                "role": "Platform Engineer",
                "jobUrl": "https://jobs.example.test/orbit/platform",
                "jobContent": "Own Python platform services, API reliability, CI workflows, observability, and cloud operations.",
                "applicationStatus": "To Apply",
                "dateFound": "2026-07-03",
                "analyzed": True,
                "matchScore": 88,
                "analysis": {
                    "summary": "The role aligns with backend systems, API design, and delivery automation.",
                    "skillSignals": ["Python", "REST APIs", "CI"],
                },
                "resumeId": None,
            },
        ],
        "resumes": {},
        "notes": {},
    }


class DemoWorkspace:
    def __init__(self, state_path: Path, export_path: Path):
        self._state_path = state_path
        self._lock = asyncio.Lock()
        self._state = self._load()

    def _load(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        state = initial_demo_state()
        self._save(state)
        return state

    def _save(self, state: dict | None = None) -> None:
        if state is not None:
            self._state = state
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._state, indent=2) + "\n")

    async def reset(self) -> dict:
        async with self._lock:
            self._save(initial_demo_state())
        return {"ok": True, "result": "reset", "validationFailures": [], "errors": []}

    @staticmethod
    def _page(
        items: list[dict], limit: int, cursor: str | None, context: str
    ) -> tuple[list[dict], dict]:
        fingerprint = hashlib.sha256(
            "\n".join(item["id"] for item in items).encode()
        ).hexdigest()[:16]
        offset = decode_cursor(cursor, context, fingerprint)
        if offset > len(items):
            raise InvalidCursor("Cursor is invalid or expired.")
        selected = items[offset : offset + limit]
        next_offset = offset + len(selected)
        has_more = next_offset < len(items)
        return selected, {
            "limit": limit,
            "nextCursor": encode_cursor(next_offset, context, fingerprint)
            if has_more
            else None,
            "hasMore": has_more,
        }

    async def validate_capture_workspace(self) -> WorkspaceReadiness:
        return WorkspaceReadiness()

    async def find_application_by_job_url(
        self, job_url: str
    ) -> ApplicationRecord | None:
        matches = [
            item for item in self._state["applications"] if item["jobUrl"] == job_url
        ]
        if len(matches) > 1:
            raise WorkspaceDataConflict(
                "Multiple Applications use the same canonical Job URL."
            )
        return self._application_record(matches[0]) if matches else None

    async def create_application(
        self,
        draft: ConfirmedApplicationDraft,
        *,
        captured_at: datetime,
        captured_url: str | None = None,
        parsing_notes: tuple[str, ...] = (),
    ) -> ApplicationRecord:
        async with self._lock:
            application = {
                "id": f"app-{uuid4().hex[:10]}",
                "companyName": draft.company_name.strip(),
                "role": draft.role.strip(),
                "jobUrl": draft.job_url,
                "capturedUrl": captured_url,
                "parsingNotes": list(parsing_notes),
                "location": draft.location,
                "jobContent": draft.job_content.strip(),
                "applicationStatus": "To Apply",
                "dateFound": captured_at.date().isoformat(),
                "analyzed": False,
                "matchScore": None,
                "analysis": None,
                "resumeId": None,
            }
            self._state["applications"].append(application)
            self._save()
        return self._application_record(application)

    @staticmethod
    def _application_record(application: dict) -> ApplicationRecord:
        analysis = application.get("analysis")
        analysis_document = None
        if analysis:
            analysis_document = ApplicationAnalysisDocument(
                summary=str(analysis.get("summary") or ""),
                match_score=analysis.get("matchScore", application.get("matchScore")),
                skill_signals=tuple(analysis.get("skillSignals") or ()),
                heading=analysis.get("heading", "Application Analysis"),
            )
        return ApplicationRecord(
            id=application["id"],
            url=f'https://www.notion.so/demo/{application["id"]}',
            company_name=application["companyName"],
            role=application["role"],
            job_url=application["jobUrl"],
            captured_url=application.get("capturedUrl"),
            location=application.get("location") or None,
            date_found=date.fromisoformat(application["dateFound"]),
            application_status=application["applicationStatus"],
            analyzed=bool(application["analyzed"]),
            match_score=application.get("matchScore"),
            resume_ids=(application["resumeId"],) if application.get("resumeId") else (),
            job_content=application.get("jobContent"),
            analysis=analysis_document,
        )

    async def validate_analysis_workspace(self) -> WorkspaceReadiness:
        return WorkspaceReadiness()

    async def list_analysis_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage[ApplicationRecord]:
        candidates = self._analysis_candidates()
        page, pagination = self._page(candidates, limit, cursor, "application_analysis")
        return QueuePage(
            items=tuple(self._application_record(item) for item in page),
            total=len(candidates),
            limit=limit,
            next_cursor=pagination["nextCursor"],
            has_more=pagination["hasMore"],
        )

    async def load_analysis_input(self, application_id: str) -> ApplicationRecord:
        application = next(
            (item for item in self._state["applications"] if item["id"] == application_id),
            None,
        )
        if application is None:
            raise WorkspaceDataError("Application was not found.")
        return self._application_record(application)

    async def append_application_analysis(
        self, application_id: str, document: ApplicationAnalysisDocument
    ) -> None:
        application = await self._mutable_application(application_id)
        application["analysis"] = {
            "summary": document.summary,
            "matchScore": document.match_score,
            "skillSignals": list(document.skill_signals),
        }
        self._save()

    async def finalize_application_analysis(
        self, application_id: str, *, match_score: int | None
    ) -> None:
        application = await self._mutable_application(application_id)
        application["matchScore"] = match_score
        application["analyzed"] = True
        self._save()

    async def _mutable_application(self, application_id: str) -> dict:
        application = next(
            (item for item in self._state["applications"] if item["id"] == application_id),
            None,
        )
        if application is None:
            raise WorkspaceDataError("Application was not found.")
        return application

    def _analysis_candidates(self) -> list[dict]:
        return sorted(
            [
                item
                for item in self._state["applications"]
                if item["applicationStatus"] == "To Apply"
                and not item["analyzed"]
                and len(item["jobContent"].strip()) >= 20
            ],
            key=lambda item: (item["dateFound"], item["id"]),
        )

    async def validate_resume_workspace(self) -> WorkspaceReadiness:
        return WorkspaceReadiness()

    async def list_resume_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage[ApplicationRecord]:
        candidates = []
        for item in self._state["applications"]:
            if (
                item["applicationStatus"] != "To Apply"
                or not item["analyzed"]
                or not item["analysis"]
                or item.get("matchScore") is None
                or len(item["jobContent"].strip()) < 20
            ):
                continue
            application = self._application_record(item)
            if await self.find_completed_resume(application) is None:
                candidates.append(item)
        candidates.sort(
            key=lambda item: (
                -(item["matchScore"] or 0),
                item["dateFound"],
                item["id"],
            )
        )
        page, pagination = self._page(candidates, limit, cursor, "resume_creation")
        return QueuePage(
            items=tuple(self._application_record(item) for item in page),
            total=len(candidates),
            limit=limit,
            next_cursor=pagination["nextCursor"],
            has_more=pagination["hasMore"],
        )

    async def load_resume_input(self, application_id: str) -> ApplicationRecord:
        application = await self.load_analysis_input(application_id)
        if (
            application.application_status != "To Apply"
            or not application.analyzed
            or application.match_score is None
            or len(application.job_content or "") < 20
            or application.analysis is None
        ):
            raise WorkspaceDataError(
                "Application is not eligible for Resume Creation."
            )
        return application

    async def find_completed_resume(
        self, application: ApplicationRecord
    ) -> ResumeRecord | None:
        active = [
            self._resume_record(resume)
            for resume_id in application.resume_ids
            if (resume := self._state["resumes"].get(resume_id))
            and not resume.get("archived")
        ]
        if len(active) > 1:
            raise WorkspaceDataConflict(
                "Application has multiple related Job-Specific Resumes."
            )
        return active[0] if active else None

    async def find_resume_fit_note(
        self, application_id: str, resume_id: str
    ) -> NoteRecord | None:
        active = [
            self._note_record(note)
            for note in self._state["notes"].values()
            if note.get("applicationId") == application_id
            and note.get("resumeId") == resume_id
            and not note.get("archived")
        ]
        if len(active) > 1:
            raise WorkspaceDataConflict(
                "Resume has multiple active Resume Fit Analysis Notes."
            )
        return active[0] if active else None

    async def load_master_resume(self) -> ResumeDocument:
        record = ResumeRecord(
            id="demo-master-resume",
            url="https://www.notion.so/demo/master-resume",
            name="Master Resume",
        )
        return ResumeDocument(
            record=record,
            blocks=(
                DocumentBlock(kind="heading_2", text="Software Engineer"),
                DocumentBlock(
                    kind="bulleted_list_item",
                    text="Built reliable APIs and accessible product interfaces.",
                ),
            ),
        )

    async def create_resume_draft(
        self, name: str, document: tuple[DocumentBlock, ...]
    ) -> ResumeRecord:
        resume_id = f"resume-{uuid4().hex[:10]}"
        resume = {
            "id": resume_id,
            "title": name,
            "url": f"https://www.notion.so/demo/{resume_id}",
            "applicationId": None,
            "document": [block.__dict__ for block in document],
            "archived": False,
        }
        self._state["resumes"][resume_id] = resume
        self._save()
        return self._resume_record(resume)

    async def create_resume_fit_note(
        self,
        name: str,
        *,
        application_id: str,
        resume_id: str,
        document: tuple[DocumentBlock, ...],
    ) -> NoteRecord:
        note_id = f"note-{uuid4().hex[:10]}"
        note = {
            "id": note_id,
            "title": name,
            "url": f"https://www.notion.so/demo/{note_id}",
            "applicationId": application_id,
            "resumeId": resume_id,
            "document": [block.__dict__ for block in document],
            "archived": False,
        }
        self._state["notes"][note_id] = note
        self._save()
        return self._note_record(note)

    async def attach_resume_to_application(
        self, resume_id: str, application_id: str
    ) -> ResumeRecord:
        resume = self._state["resumes"].get(resume_id)
        if resume is None:
            raise WorkspaceDataError("Resume was not found.")
        application = await self._mutable_application(application_id)
        resume["applicationId"] = application_id
        application["resumeId"] = resume_id
        self._save()
        return self._resume_record(resume)

    async def clear_resume_application(self, resume_id: str) -> None:
        resume = self._state["resumes"].get(resume_id)
        if resume is None:
            return
        application_id = resume.get("applicationId")
        resume["applicationId"] = None
        if application_id:
            application = next(
                (
                    item
                    for item in self._state["applications"]
                    if item["id"] == application_id
                ),
                None,
            )
            if application and application.get("resumeId") == resume_id:
                application["resumeId"] = None
        self._save()

    async def archive_note(self, note_id: str) -> None:
        note = self._state["notes"].get(note_id)
        if note is not None:
            note["archived"] = True
            self._save()

    async def archive_resume(self, resume_id: str) -> None:
        resume = self._state["resumes"].get(resume_id)
        if resume is not None:
            resume["archived"] = True
            self._save()

    @staticmethod
    def _resume_record(resume: dict) -> ResumeRecord:
        application_id = resume.get("applicationId")
        return ResumeRecord(
            id=resume["id"],
            url=resume["url"],
            name=resume.get("name") or resume.get("title") or "",
            application_ids=(application_id,) if application_id else (),
            archived=bool(resume.get("archived")),
        )

    @staticmethod
    def _note_record(note: dict) -> NoteRecord:
        return NoteRecord(
            id=note["id"],
            url=note["url"],
            name=note.get("name") or note.get("title") or "",
            application_ids=(note["applicationId"],)
            if note.get("applicationId")
            else (),
            resume_ids=(note["resumeId"],) if note.get("resumeId") else (),
            archived=bool(note.get("archived")),
        )

    def snapshot(self) -> dict:
        return deepcopy(self._state)
