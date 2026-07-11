import asyncio
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from ..features.applications.schemas import ConfirmedApplicationDraft
from ..shared.pagination import InvalidCursor, decode_cursor, encode_cursor
from .pdf_export import write_simple_pdf


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
        self._export_path = export_path
        self._lock = asyncio.Lock()
        self._resume_locks: dict[str, asyncio.Lock] = {}
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
    def _application_ref(application: dict) -> dict:
        return {
            "id": application["id"],
            "title": f'{application["role"]} at {application["companyName"]}',
            "companyName": application["companyName"],
            "role": application["role"],
            "location": application.get("location") or None,
            "jobUrl": application["jobUrl"],
            "applicationStatus": application["applicationStatus"],
            "url": f'https://www.notion.so/demo/{application["id"]}',
        }

    @staticmethod
    def _queue_ref(application: dict) -> dict:
        return {
            "applicationId": application["id"],
            "title": f'{application["role"]} at {application["companyName"]}',
            "companyName": application["companyName"],
            "role": application["role"],
            "applicationStatus": application["applicationStatus"],
            "jobUrl": application["jobUrl"],
        }

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

    async def confirm_capture(self, draft: ConfirmedApplicationDraft) -> dict:
        async with self._lock:
            for application in self._state["applications"]:
                if application["jobUrl"] == draft.job_url:
                    return {
                        "ok": True,
                        "result": "already_captured",
                        "application": self._application_ref(application),
                        "validationFailures": [],
                        "errors": [],
                    }
            application = {
                "id": f"app-{uuid4().hex[:10]}",
                "companyName": draft.company_name.strip(),
                "role": draft.role.strip(),
                "jobUrl": draft.job_url,
                "location": draft.location,
                "jobContent": draft.job_content.strip(),
                "applicationStatus": "To Apply",
                "dateFound": date.today().isoformat(),
                "analyzed": False,
                "matchScore": None,
                "analysis": None,
                "resumeId": None,
            }
            self._state["applications"].append(application)
            self._save()
        return {
            "ok": True,
            "result": "created",
            "application": self._application_ref(application),
            "validationFailures": [],
            "errors": [],
        }

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

    async def analysis_queue(self, limit: int, cursor: str | None) -> dict:
        candidates = self._analysis_candidates()
        page, pagination = self._page(candidates, limit, cursor, "application_analysis")
        return {
            "ok": True,
            "queueCount": len(candidates),
            "items": [self._queue_ref(item) for item in page],
            "pagination": pagination,
            "validationFailures": [],
            "errors": [],
        }

    @staticmethod
    def _analyze(application: dict) -> tuple[list[str], int]:
        vocabulary = {
            "React": "react",
            "Python": "python",
            "REST APIs": "rest api",
            "PostgreSQL": "postgres",
            "Testing": "test",
            "CI": "ci",
            "Accessibility": "accessib",
            "Observability": "observab",
        }
        content = application["jobContent"].lower()
        signals = [name for name, token in vocabulary.items() if token in content]
        score = min(96, 58 + len(signals) * 6)
        return signals, score

    async def run_analysis(self, limit: int) -> dict:
        async with self._lock:
            candidates = self._analysis_candidates()[:limit]
            results = []
            failed = 0
            repaired = 0
            for application in candidates:
                try:
                    if application["analysis"]:
                        application["analyzed"] = True
                        repaired += 1
                        results.append({**self._queue_ref(application), "result": "repaired", "matchScore": application["matchScore"], "errors": []})
                        continue
                    signals, score = self._analyze(application)
                    application["analysis"] = {
                        "summary": (
                            f'{application["role"]} at {application["companyName"]} emphasizes '
                            f'{", ".join(signals) if signals else "transferable engineering experience"}. '
                            "The analysis uses only readable Job Content and deterministic demo evidence. "
                            "Review the durable record in Notion before applying."
                        ),
                        "skillSignals": signals,
                    }
                    application["matchScore"] = score
                    application["analyzed"] = True
                    results.append({**self._queue_ref(application), "result": "analyzed", "matchScore": score, "errors": []})
                except Exception:
                    failed += 1
                    results.append({**self._queue_ref(application), "result": "failed", "matchScore": None, "errors": ["Application Analysis failed for this item."]})
            self._save()
        return {
            "ok": True,
            "result": "completed",
            "processed": len(results),
            "succeeded": len(results) - failed,
            "failed": failed,
            "repaired": repaired,
            "items": results,
            "validationFailures": [],
            "errors": [],
        }

    def _resume_candidates(self) -> list[dict]:
        return sorted(
            [
                item
                for item in self._state["applications"]
                if item["applicationStatus"] == "To Apply"
                and item["analyzed"]
                and item["resumeId"] is None
                and item["analysis"]
                and len(item["jobContent"].strip()) >= 20
            ],
            key=lambda item: (-(item["matchScore"] or 0), item["dateFound"], item["id"]),
        )

    async def resume_queue(self, limit: int, cursor: str | None) -> dict:
        candidates = self._resume_candidates()
        page, pagination = self._page(candidates, limit, cursor, "resume_creation")
        items = []
        for application in page:
            items.append(
                {
                    **self._queue_ref(application),
                    "matchScore": application["matchScore"],
                    "analyzed": True,
                    "hasResume": False,
                }
            )
        return {
            "ok": True,
            "queueCount": len(candidates),
            "items": items,
            "pagination": pagination,
            "validationFailures": [],
            "errors": [],
        }

    def _existing_resume_result(self, application: dict) -> dict:
        resume = self._state["resumes"][application["resumeId"]]
        note = self._state["notes"].get(resume["noteId"])
        result = self._resume_result("already_created", application, resume, note)
        if self.pdf_path(resume["id"]) is None:
            result["pdf"] = None
        return result

    @staticmethod
    def _resume_result(result: str, application: dict, resume: dict, note: dict | None) -> dict:
        payload = {
            "ok": True,
            "result": result,
            "application": {
                "id": application["id"],
                "title": f'{application["role"]} at {application["companyName"]}',
                "companyName": application["companyName"],
                "role": application["role"],
            },
            "resume": {
                "id": resume["id"],
                "title": resume["title"],
                "companyName": application["companyName"],
                "role": application["role"],
                "url": resume["url"],
            },
            "pdf": {
                "filename": resume["filename"],
                "downloadUrl": f'/api/v1/resumes/{resume["id"]}/pdf',
            },
            "validationFailures": [],
            "errors": [],
        }
        if note:
            payload["note"] = {
                "id": note["id"],
                "title": note["title"],
                "companyName": application["companyName"],
                "role": application["role"],
                "url": note["url"],
            }
        else:
            payload["note"] = None
        return payload

    async def create_resume(self, application_id: str) -> dict:
        lock = self._resume_locks.setdefault(application_id, asyncio.Lock())
        async with lock:
            application = next(
                (item for item in self._state["applications"] if item["id"] == application_id),
                None,
            )
            if not application:
                return {"ok": False, "status": "blocked", "result": "blocked", "cleanup": {"status": "not_required", "errors": []}, "validationFailures": [], "errors": ["Application was not found."]}
            if application["resumeId"]:
                return self._existing_resume_result(application)
            if application not in self._resume_candidates():
                return {"ok": False, "status": "blocked", "result": "blocked", "cleanup": {"status": "not_required", "errors": []}, "validationFailures": [], "errors": ["Application is not eligible for Resume Creation."]}

            resume_id = f"resume-{uuid4().hex[:10]}"
            note_id = f"note-{uuid4().hex[:10]}"
            slug = re.sub(r"[^a-z0-9]+", "-", f'{application["companyName"]}-{application["role"]}'.lower()).strip("-")
            filename = f"{slug}.pdf"
            title = f'{application["role"]} at {application["companyName"]}'
            resume = {
                "id": resume_id,
                "title": title,
                "url": f"https://www.notion.so/demo/{resume_id}",
                "filename": filename,
                "noteId": note_id,
            }
            note = {
                "id": note_id,
                "title": f"Resume Fit Analysis - {title}",
                "url": f"https://www.notion.so/demo/{note_id}",
            }
            pdf_path = self._export_path / filename
            try:
                write_simple_pdf(
                    pdf_path,
                    [
                        "Elizabeth Parnell",
                        title,
                        "Evidence-backed application-ready demo resume",
                        f'Match Score: {application["matchScore"]}',
                        "Skills: " + ", ".join(application["analysis"]["skillSignals"]),
                    ],
                )
                async with self._lock:
                    self._state["resumes"][resume_id] = resume
                    self._state["notes"][note_id] = note
                    application["resumeId"] = resume_id
                    self._save()
            except Exception:
                if pdf_path.exists():
                    pdf_path.unlink()
                return {
                    "ok": False,
                    "status": "failed",
                    "result": "failed",
                    "cleanup": {
                        "status": "completed" if not pdf_path.exists() else "incomplete",
                        "errors": [] if not pdf_path.exists() else ["Generated PDF could not be removed."],
                    },
                    "validationFailures": [],
                    "errors": ["Resume artifacts could not be committed."],
                }
            return self._resume_result("created", application, resume, note)

    def pdf_path(self, resume_id: str) -> Path | None:
        resume = self._state["resumes"].get(resume_id)
        if not resume:
            return None
        path = self._export_path / resume["filename"]
        return path if path.exists() else None

    def snapshot(self) -> dict:
        return deepcopy(self._state)
