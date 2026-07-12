from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime
import hashlib
import re
from typing import Protocol
from urllib.parse import urlencode, urlsplit

import httpx

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
from ..shared.pagination import decode_cursor, encode_cursor
from ..matching import EvidenceItem, evidence_items_from_blocks
from ..shared.workspace import (
    QueuePage,
    WorkspaceDataConflict,
    WorkspaceDataError,
    WorkspaceIssue,
    WorkspaceProviderError,
    WorkspaceReadiness,
)


NOTION_VERSION = "2022-06-28"
APPLICATION_STATUSES = {
    "To Apply",
    "Applied",
    "Rejected",
    "Not Interested",
    "Archived",
}
READABLE_BLOCK_TYPES = {
    "heading_1",
    "heading_2",
    "heading_3",
    "paragraph",
    "quote",
    "callout",
    "bulleted_list_item",
    "numbered_list_item",
    "toggle",
}
MAX_READABLE_BLOCKS = 5000
APPLICATION_PROPERTIES = {
    "title": "Job Posting",
    "company_name": "Company Name",
    "role": "Job Title",
    "job_url": "Job URL",
    "captured_url": "Captured URL",
    "location": "Location",
    "date_found": "Application Date",
    "status": "Application Status",
    "analyzed": "Analyzed",
    "match_score": "Match Score",
    "resumes": "Resumes",
    "notes": "Notes",
}
class NotionTransport(Protocol):
    async def request(
        self, method: str, path: str, body: dict | None = None
    ) -> dict: ...


class HttpxNotionTransport:
    def __init__(
        self,
        token: str,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ):
        self._token = token
        self._client_factory = client_factory or (
            lambda: httpx.AsyncClient(base_url="https://api.notion.com/v1", timeout=30)
        )

    async def request(self, method: str, path: str, body: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        try:
            async with self._client_factory() as client:
                response = await client.request(method, path, headers=headers, json=body)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise WorkspaceProviderError(
                "Notion could not be reached.", retryable=True
            ) from exc
        except Exception as exc:
            raise WorkspaceProviderError(
                "Notion request failed unexpectedly."
            ) from exc
        payload = _json_object(response)
        if response.is_error:
            code = str((payload or {}).get("code") or "") or None
            retryable = response.status_code == 429 or response.status_code >= 500
            raise WorkspaceProviderError(
                _safe_provider_message(response.status_code),
                status=response.status_code,
                code=code,
                retryable=retryable,
            )
        if payload is None:
            raise WorkspaceProviderError(
                "Notion returned an invalid response.",
                status=response.status_code,
            )
        return payload


class NotionWorkspace:
    def __init__(
        self,
        *,
        application_database_id: str,
        resume_database_id: str,
        notes_database_id: str,
        transport: NotionTransport | None = None,
        token: str = "",
    ):
        self._transport = transport or HttpxNotionTransport(token)
        self._application_database_id = application_database_id
        self._resume_database_id = resume_database_id
        self._notes_database_id = notes_database_id

    async def validate_capture_workspace(self) -> WorkspaceReadiness:
        database = await self._transport.request(
            "GET", f"/databases/{self._application_database_id}"
        )
        return _validate_capture_database(database)

    async def find_application_by_job_url(
        self, job_url: str
    ) -> ApplicationRecord | None:
        response = await self._transport.request(
            "POST",
            f"/databases/{self._application_database_id}/query",
            {
                "filter": {
                    "property": APPLICATION_PROPERTIES["job_url"],
                    "url": {"equals": job_url},
                },
                "page_size": 2,
            },
        )
        results = tuple(response.get("results") or ())
        if len(results) > 1:
            raise WorkspaceDataConflict(
                "Multiple Applications use the same canonical Job URL."
            )
        return _application_record(results[0]) if results else None

    async def create_application(
        self,
        draft: ConfirmedApplicationDraft,
        *,
        captured_at: datetime,
        captured_url: str | None = None,
        parsing_notes: tuple[str, ...] = (),
        on_created: Callable[[ApplicationRecord], None] | None = None,
    ) -> ApplicationRecord:
        database = await self._transport.request(
            "GET", f"/databases/{self._application_database_id}"
        )
        readiness = _validate_capture_database(database)
        if not readiness.ready:
            raise WorkspaceDataError(readiness.errors[0].message)

        properties = _capture_properties(
            draft,
            captured_at=captured_at,
            captured_url=captured_url,
            has_captured_url="Captured URL" in (database.get("properties") or {}),
        )
        blocks = _capture_blocks(
            draft,
            captured_at=captured_at,
            captured_url=captured_url,
            parsing_notes=parsing_notes,
        )
        page = await self._transport.request(
            "POST",
            "/pages",
            {
                "parent": {"database_id": self._application_database_id},
                "properties": properties,
                "children": blocks[:80],
            },
        )
        record = _application_record(page)
        if on_created:
            on_created(record)
        for batch in _chunks(blocks[80:], 90):
            await self._transport.request(
                "PATCH", f"/blocks/{page['id']}/children", {"children": batch}
            )
        return record

    async def capture_is_complete(self, application_id: str) -> bool:
        blocks = await self._get_page_children(application_id)
        return bool(
            _read_top_level_section(blocks, "Capture Summary")
            and len(_read_top_level_section(blocks, "Job Content").strip()) >= 20
        )

    async def archive_application(self, application_id: str) -> None:
        await self._transport.request(
            "PATCH", f"/pages/{application_id}", {"archived": True}
        )

    async def validate_analysis_workspace(self) -> WorkspaceReadiness:
        database = await self._transport.request(
            "GET", f"/databases/{self._application_database_id}"
        )
        return _validate_properties(
            "applications",
            database,
            {
                "Job Posting": "title",
                "Company Name": "rich_text",
                "Job Title": "rich_text",
                "Job URL": "url",
                "Application Date": "date",
                "Application Status": "select",
                "Analyzed": "checkbox",
                "Match Score": "number",
            },
            required_select_options={"Application Status": {"To Apply"}},
            known_select_options={"Application Status": APPLICATION_STATUSES},
        )

    async def list_analysis_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage:
        pages = await self._query_all(
            self._application_database_id,
            {
                "filter": {
                    "and": [
                        {
                            "property": "Application Status",
                            "select": {"equals": "To Apply"},
                        },
                        {"property": "Analyzed", "checkbox": {"equals": False}},
                    ]
                },
                "sorts": [
                    {"property": "Application Date", "direction": "ascending"}
                ],
            },
        )
        eligible: list[ApplicationRecord] = []
        for page in pages:
            try:
                application = _application_record(page)
                blocks = await self._get_page_children(application.id)
                job_content = _read_top_level_section(blocks, "Job Content")
                if len(job_content) < 20:
                    continue
                analysis = _select_analysis(blocks)
                eligible.append(
                    replace(
                        application,
                        job_content=job_content,
                        analysis=analysis,
                    )
                )
            except WorkspaceDataError:
                continue
        eligible.sort(key=lambda item: (item.date_found, item.id))
        return _queue_page(eligible, limit, cursor, "application_analysis")

    async def load_analysis_input(self, application_id: str) -> ApplicationRecord:
        page = await self._transport.request("GET", f"/pages/{application_id}")
        application = _application_record(page)
        blocks = await self._get_page_children(application_id)
        return replace(
            application,
            job_content=_read_top_level_section(blocks, "Job Content") or None,
            analysis=_select_analysis(blocks),
        )

    async def load_analysis_evidence(self) -> tuple[EvidenceItem, ...]:
        master_resume = await self.load_master_resume()
        return evidence_items_from_blocks(
            master_resume.record.id, master_resume.blocks
        )

    async def append_application_analysis(
        self, application_id: str, document: ApplicationAnalysisDocument
    ) -> None:
        blocks = _analysis_blocks(document)
        for batch in _chunks(blocks, 90):
            await self._transport.request(
                "PATCH",
                f"/blocks/{application_id}/children",
                {"children": batch},
            )

    async def finalize_application_analysis(
        self, application_id: str, *, match_score: int | None
    ) -> None:
        await self._transport.request(
            "PATCH",
            f"/pages/{application_id}",
            {
                "properties": {
                    "Match Score": {"number": match_score},
                    "Analyzed": {"checkbox": True},
                }
            },
        )

    async def validate_resume_workspace(self) -> WorkspaceReadiness:
        applications = await self._transport.request(
            "GET", f"/databases/{self._application_database_id}"
        )
        resumes = await self._transport.request(
            "GET", f"/databases/{self._resume_database_id}"
        )
        notes = await self._transport.request(
            "GET", f"/databases/{self._notes_database_id}"
        )
        results = [
            _validate_properties(
                "applications",
                applications,
                {
                    "Job Posting": "title",
                    "Company Name": "rich_text",
                    "Job Title": "rich_text",
                    "Job URL": "url",
                    "Application Date": "date",
                    "Application Status": "select",
                    "Analyzed": "checkbox",
                    "Match Score": "number",
                    "Resumes": "relation",
                    "Notes": "relation",
                },
                required_select_options={"Application Status": {"To Apply"}},
                known_select_options={"Application Status": APPLICATION_STATUSES},
            ),
            _validate_properties(
                "resumes",
                resumes,
                {"Name": "title", "Job Posting": "relation", "Notes": "relation"},
            ),
            _validate_properties(
                "notes",
                notes,
                {"Name": "title", "Job Posting": "relation", "Resume": "relation"},
            ),
        ]
        relation_results = [
            _validate_relation(
                "applications",
                applications,
                "Resumes",
                resumes,
                self._resume_database_id,
                "Job Posting",
            ),
            _validate_relation(
                "resumes",
                resumes,
                "Job Posting",
                applications,
                self._application_database_id,
                "Resumes",
            ),
            _validate_relation(
                "applications",
                applications,
                "Notes",
                notes,
                self._notes_database_id,
                "Job Posting",
            ),
            _validate_relation(
                "notes",
                notes,
                "Job Posting",
                applications,
                self._application_database_id,
                "Notes",
            ),
            _validate_relation(
                "resumes",
                resumes,
                "Notes",
                notes,
                self._notes_database_id,
                "Resume",
            ),
            _validate_relation(
                "notes",
                notes,
                "Resume",
                resumes,
                self._resume_database_id,
                "Notes",
            ),
        ]
        return _merge_readiness(*results, *relation_results)

    async def list_resume_queue(
        self, *, limit: int, cursor: str | None
    ) -> QueuePage:
        pages = await self._query_all(
            self._application_database_id,
            {
                "filter": {
                    "and": [
                        {
                            "property": "Application Status",
                            "select": {"equals": "To Apply"},
                        },
                        {"property": "Analyzed", "checkbox": {"equals": True}},
                    ]
                },
                "sorts": [
                    {"property": "Match Score", "direction": "descending"},
                    {"property": "Application Date", "direction": "ascending"},
                ],
            },
        )
        eligible: list[ApplicationRecord] = []
        for page in pages:
            try:
                application = _application_record(page)
                if application.match_score is None:
                    continue
                if await self.find_completed_resume(application) is not None:
                    continue
                blocks = await self._get_page_children(application.id)
                job_content = _read_top_level_section(blocks, "Job Content")
                analysis = _select_analysis(blocks)
                if len(job_content) < 20 or analysis is None:
                    continue
                eligible.append(
                    replace(
                        application,
                        job_content=job_content,
                        analysis=analysis,
                    )
                )
            except WorkspaceDataError:
                continue
        eligible.sort(
            key=lambda item: (-(item.match_score or 0), item.date_found, item.id)
        )
        return _queue_page(eligible, limit, cursor, "resume_creation")

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
        active: list[ResumeRecord] = []
        for resume_id in application.resume_ids:
            page = await self._transport.request("GET", f"/pages/{resume_id}")
            record = _resume_record(page)
            if not record.archived and record.name != "Master Resume":
                active.append(record)
        if len(active) > 1:
            raise WorkspaceDataConflict(
                "Application has multiple related Job-Specific Resumes."
            )
        return active[0] if active else None

    async def find_resume_fit_note(
        self, application_id: str, resume_id: str
    ) -> NoteRecord | None:
        response = await self._transport.request(
            "POST",
            f"/databases/{self._notes_database_id}/query",
            {
                "filter": {
                    "and": [
                        {
                            "property": "Job Posting",
                            "relation": {"contains": application_id},
                        },
                        {
                            "property": "Resume",
                            "relation": {"contains": resume_id},
                        },
                    ]
                },
                "page_size": 2,
            },
        )
        notes = [
            _note_record(page)
            for page in (response.get("results") or ())
            if not page.get("archived")
        ]
        if len(notes) > 1:
            raise WorkspaceDataConflict(
                "Resume has multiple active Resume Fit Analysis Notes."
            )
        return notes[0] if notes else None

    async def load_master_resume(self) -> ResumeDocument:
        response = await self._transport.request(
            "POST",
            f"/databases/{self._resume_database_id}/query",
            {
                "filter": {"property": "Name", "title": {"equals": "Master Resume"}},
                "page_size": 2,
            },
        )
        pages = [page for page in (response.get("results") or ()) if not page.get("archived")]
        if len(pages) != 1:
            raise WorkspaceDataError(
                "Resume Creation requires exactly one active Master Resume."
            )
        record = _resume_record(pages[0])
        if record.application_ids:
            raise WorkspaceDataError("Master Resume must not be related to an Application.")
        raw_blocks = await self._get_page_children(record.id, recursive=True)
        blocks = tuple(
            DocumentBlock(
                kind=str(block.get("type") or "unknown"),
                text=text,
                depth=int(block.get("merida_depth") or 0),
            )
            for block in raw_blocks
            if (text := _block_text(block))
        )
        if not blocks:
            raise WorkspaceDataError("Master Resume body is not readable.")
        return ResumeDocument(record=record, blocks=blocks)

    async def create_resume_draft(
        self, name: str, document: tuple[DocumentBlock, ...]
    ) -> ResumeRecord:
        page = await self._create_page_with_document(
            self._resume_database_id,
            {"Name": {"title": _rich_text(name)}},
            document,
        )
        return _resume_record(page)

    async def create_resume_fit_note(
        self,
        name: str,
        *,
        application_id: str,
        resume_id: str,
        document: tuple[DocumentBlock, ...],
    ) -> NoteRecord:
        page = await self._create_page_with_document(
            self._notes_database_id,
            {
                "Name": {"title": _rich_text(name)},
                "Job Posting": {"relation": [{"id": application_id}]},
                "Resume": {"relation": [{"id": resume_id}]},
            },
            document,
        )
        return _note_record(page)

    async def attach_resume_to_application(
        self, resume_id: str, application_id: str
    ) -> ResumeRecord:
        page = await self._transport.request(
            "PATCH",
            f"/pages/{resume_id}",
            {
                "properties": {
                    "Job Posting": {"relation": [{"id": application_id}]}
                }
            },
        )
        return _resume_record(page)

    async def clear_resume_application(self, resume_id: str) -> None:
        await self._transport.request(
            "PATCH",
            f"/pages/{resume_id}",
            {"properties": {"Job Posting": {"relation": []}}},
        )

    async def archive_note(self, note_id: str) -> None:
        await self._transport.request(
            "PATCH", f"/pages/{note_id}", {"archived": True}
        )

    async def archive_resume(self, resume_id: str) -> None:
        await self._transport.request(
            "PATCH", f"/pages/{resume_id}", {"archived": True}
        )

    async def verify_recovery_artifacts(
        self,
        *,
        application_id: str,
        resume_id: str | None,
        note_id: str | None,
    ) -> bool:
        if resume_id:
            resume_page = await self._transport.request("GET", f"/pages/{resume_id}")
            resume = _resume_record(resume_page)
            if resume.name == "Master Resume" or any(
                related_id != application_id for related_id in resume.application_ids
            ):
                return False
        if note_id:
            note_page = await self._transport.request("GET", f"/pages/{note_id}")
            note = _note_record(note_page)
            if note.application_ids != (application_id,) or (
                resume_id is not None and note.resume_ids != (resume_id,)
            ):
                return False
        return True

    async def _create_page_with_document(
        self,
        database_id: str,
        properties: dict,
        document: tuple[DocumentBlock, ...],
    ) -> dict:
        blocks = [_document_block(item) for item in document]
        page = await self._transport.request(
            "POST",
            "/pages",
            {
                "parent": {"database_id": database_id},
                "properties": properties,
                "children": blocks[:80],
            },
        )
        for batch in _chunks(blocks[80:], 90):
            await self._transport.request(
                "PATCH", f"/blocks/{page['id']}/children", {"children": batch}
            )
        return page

    async def _query_all(self, database_id: str, query: dict) -> list[dict]:
        results: list[dict] = []
        cursor: str | None = None
        while True:
            body = {**query, "page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            response = await self._transport.request(
                "POST", f"/databases/{database_id}/query", body
            )
            results.extend(response.get("results") or ())
            cursor = response.get("next_cursor") if response.get("has_more") else None
            if not cursor:
                return results

    async def _get_page_children(
        self, page_id: str, *, recursive: bool = False, max_depth: int = 8
    ) -> list[dict]:
        blocks = await self._get_block_children(
            page_id, recursive=recursive, depth=0, max_depth=max_depth
        )
        if len(blocks) > MAX_READABLE_BLOCKS:
            raise WorkspaceDataError(
                "Notion page content exceeds the supported block limit."
            )
        return blocks

    async def _get_block_children(
        self, block_id: str, *, recursive: bool, depth: int, max_depth: int
    ) -> list[dict]:
        results: list[dict] = []
        cursor: str | None = None
        while True:
            query = {"page_size": "100"}
            if cursor:
                query["start_cursor"] = cursor
            response = await self._transport.request(
                "GET", f"/blocks/{block_id}/children?{urlencode(query)}"
            )
            page = response.get("results") or ()
            for child in page:
                results.append(child if depth == 0 else {**child, "merida_depth": depth})
                if recursive and child.get("has_children"):
                    if depth >= max_depth:
                        raise WorkspaceDataError(
                            "Notion page content exceeds the supported nesting depth."
                        )
                    child_id = child.get("id")
                    if child_id:
                        results.extend(
                            await self._get_block_children(
                                str(child_id),
                                recursive=True,
                                depth=depth + 1,
                                max_depth=max_depth,
                            )
                        )
            cursor = response.get("next_cursor") if response.get("has_more") else None
            if not cursor:
                return results


def _json_object(response: httpx.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_provider_message(status: int) -> str:
    if status in {401, 403}:
        return "Notion authentication or workspace access is invalid."
    if status == 404:
        return "A configured Notion resource was not found."
    if status == 429:
        return "Notion rate-limited the request."
    if status >= 500:
        return "Notion is temporarily unavailable."
    return "Notion rejected the workspace operation."


def _validate_properties(
    database_name: str,
    database: dict,
    required: dict[str, str],
    *,
    optional: dict[str, str] | None = None,
    required_select_options: dict[str, set[str]] | None = None,
    known_select_options: dict[str, set[str]] | None = None,
) -> WorkspaceReadiness:
    properties = database.get("properties") or {}
    errors: list[WorkspaceIssue] = []
    warnings: list[WorkspaceIssue] = []
    for name, expected_type in required.items():
        actual = properties.get(name)
        if not actual:
            errors.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Missing Notion property "{name}".',
                )
            )
        elif actual.get("type") != expected_type:
            errors.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Notion property "{name}" must be {expected_type}, found {actual.get("type")}.',
                )
            )
    for name, expected_type in (optional or {}).items():
        actual = properties.get(name)
        if not actual:
            warnings.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Optional Notion property "{name}" is not present.',
                )
            )
        elif actual.get("type") != expected_type:
            errors.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Optional Notion property "{name}" must be {expected_type} when present.',
                )
            )
    for name, expected_options in (required_select_options or {}).items():
        actual = properties.get(name) or {}
        if actual.get("type") != "select":
            continue
        options = {
            str(option.get("name"))
            for option in (actual.get("select") or {}).get("options") or ()
        }
        for missing in sorted(expected_options - options):
            errors.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Notion property "{name}" must include a "{missing}" option.',
                )
            )
    for name, known_options in (known_select_options or {}).items():
        actual = properties.get(name) or {}
        if actual.get("type") != "select":
            continue
        options = {
            str(option.get("name"))
            for option in (actual.get("select") or {}).get("options") or ()
        }
        extras = sorted(options - known_options)
        if extras:
            warnings.append(
                WorkspaceIssue(
                    database_name,
                    name,
                    f'Notion property "{name}" has unrecognized options that remain ineligible: {", ".join(extras)}.',
                )
            )
    return WorkspaceReadiness(tuple(errors), tuple(warnings))


def _validate_capture_database(database: dict) -> WorkspaceReadiness:
    return _validate_properties(
        "applications",
        database,
        {
            "Job Posting": "title",
            "Company Name": "rich_text",
            "Job Title": "rich_text",
            "Job URL": "url",
            "Location": "rich_text",
            "Application Date": "date",
            "Application Status": "select",
            "Analyzed": "checkbox",
        },
        optional={"Captured URL": "url"},
        required_select_options={"Application Status": {"To Apply"}},
        known_select_options={"Application Status": APPLICATION_STATUSES},
    )


def _validate_relation(
    database_name: str,
    database: dict,
    property_name: str,
    target_database: dict,
    configured_target_id: str,
    expected_inverse: str,
) -> WorkspaceReadiness:
    property_value = (database.get("properties") or {}).get(property_name) or {}
    if property_value.get("type") != "relation":
        return WorkspaceReadiness()
    relation = property_value.get("relation") or {}
    target_id = relation.get("database_id") or relation.get("data_source_id")
    target_data_sources = {
        str(item.get("id"))
        for item in (target_database.get("data_sources") or ())
        if item.get("id")
    }
    allowed = {
        configured_target_id,
        str(target_database.get("id") or ""),
        *target_data_sources,
    }
    errors: list[WorkspaceIssue] = []
    warnings: list[WorkspaceIssue] = []
    if target_id and target_id not in allowed:
        if relation.get("data_source_id") and not target_data_sources:
            warnings.append(
                WorkspaceIssue(
                    database_name,
                    property_name,
                    "Notion returned a data-source relation target that could not be compared strictly.",
                )
            )
        else:
            errors.append(
                WorkspaceIssue(
                    database_name,
                    property_name,
                    f'Notion relation "{property_name}" targets a different database.',
                )
            )
    inverse = (relation.get("dual_property") or {}).get("synced_property_name")
    if inverse and inverse != expected_inverse:
        errors.append(
            WorkspaceIssue(
                database_name,
                property_name,
                f'Notion relation "{property_name}" inverse must be "{expected_inverse}", found "{inverse}".',
            )
        )
    elif not inverse:
        warnings.append(
            WorkspaceIssue(
                database_name,
                property_name,
                f'Notion did not return inverse metadata for relation "{property_name}".',
            )
        )
    return WorkspaceReadiness(tuple(errors), tuple(warnings))


def _merge_readiness(*results: WorkspaceReadiness) -> WorkspaceReadiness:
    return WorkspaceReadiness(
        errors=tuple(issue for result in results for issue in result.errors),
        warnings=tuple(issue for result in results for issue in result.warnings),
    )


def _application_record(page: dict) -> ApplicationRecord:
    record_id, record_url = _record_identity(page, "Application")
    properties = page.get("properties") or {}
    physical_title = _plain_property(properties, "Job Posting", "title")
    company_name = _plain_property(properties, "Company Name", "rich_text")
    role = _plain_property(properties, "Job Title", "rich_text")
    job_url = str((properties.get("Job URL") or {}).get("url") or "").strip()
    if not physical_title or not company_name or not role or not job_url:
        raise WorkspaceDataError(
            "Application is missing Job Posting, Company Name, Job Title, or Job URL."
        )
    date_value = ((properties.get("Application Date") or {}).get("date") or {}).get(
        "start"
    )
    try:
        date_found = date.fromisoformat(str(date_value)[:10])
    except ValueError as exc:
        raise WorkspaceDataError("Application Date is missing or invalid.") from exc
    status = ((properties.get("Application Status") or {}).get("select") or {}).get(
        "name"
    )
    if not status:
        raise WorkspaceDataError("Application Status is missing.")
    if status not in APPLICATION_STATUSES:
        raise WorkspaceDataError("Application Status is not recognized by Merida.")
    score = (properties.get("Match Score") or {}).get("number")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise WorkspaceDataError(
                "Match Score must be an integer from 0 through 100."
            )
    return ApplicationRecord(
        id=record_id,
        url=record_url,
        company_name=company_name,
        role=role,
        job_url=job_url,
        captured_url=(
            str((properties.get("Captured URL") or {}).get("url") or "").strip()
            or None
        ),
        location=_plain_property(properties, "Location", "rich_text") or None,
        date_found=date_found,
        application_status=str(status),
        analyzed=bool((properties.get("Analyzed") or {}).get("checkbox")),
        match_score=score,
        resume_ids=_relation_ids(properties.get("Resumes")),
        note_ids=_relation_ids(properties.get("Notes")),
    )


def _resume_record(page: dict) -> ResumeRecord:
    record_id, record_url = _record_identity(page, "Resume")
    properties = page.get("properties") or {}
    name = _plain_property(properties, "Name", "title")
    if not name:
        raise WorkspaceDataError("Resume Name is missing.")
    return ResumeRecord(
        id=record_id,
        url=record_url,
        name=name,
        application_ids=_relation_ids(properties.get("Job Posting")),
        archived=bool(page.get("archived")),
    )


def _note_record(page: dict) -> NoteRecord:
    record_id, record_url = _record_identity(page, "Note")
    properties = page.get("properties") or {}
    name = _plain_property(properties, "Name", "title")
    if not name:
        raise WorkspaceDataError("Note Name is missing.")
    return NoteRecord(
        id=record_id,
        url=record_url,
        name=name,
        application_ids=_relation_ids(properties.get("Job Posting")),
        resume_ids=_relation_ids(properties.get("Resume")),
        archived=bool(page.get("archived")),
    )


def _plain_property(properties: dict, name: str, value_key: str) -> str:
    parts = (properties.get(name) or {}).get(value_key) or ()
    return "".join(
        str(part.get("plain_text") or (part.get("text") or {}).get("content") or "")
        for part in parts
    ).strip()


def _record_identity(page: dict, noun: str) -> tuple[str, str]:
    record_id = str(page.get("id") or "").strip()
    record_url = str(page.get("url") or "").strip()
    parts = urlsplit(record_url)
    host = (parts.hostname or "").lower()
    if not record_id:
        raise WorkspaceDataError(f"{noun} ID is missing.")
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or (host != "notion.so" and not host.endswith(".notion.so"))
    ):
        raise WorkspaceDataError(f"{noun} Notion URL is missing or invalid.")
    return record_id, record_url


def _relation_ids(property_value: dict | None) -> tuple[str, ...]:
    return tuple(
        str(item.get("id"))
        for item in ((property_value or {}).get("relation") or ())
        if item.get("id")
    )


def _capture_properties(
    draft: ConfirmedApplicationDraft,
    *,
    captured_at: datetime,
    captured_url: str | None,
    has_captured_url: bool,
) -> dict:
    title = f"{draft.role} at {draft.company_name}"
    properties = {
        "Job Posting": {"title": _rich_text(title)},
        "Company Name": {"rich_text": _rich_text(draft.company_name)},
        "Job Title": {"rich_text": _rich_text(draft.role)},
        "Job URL": {"url": draft.job_url},
        "Location": {"rich_text": _rich_text(draft.location or "")},
        "Application Date": {"date": {"start": captured_at.date().isoformat()}},
        "Application Status": {"select": {"name": "To Apply"}},
        "Analyzed": {"checkbox": False},
    }
    if has_captured_url and captured_url:
        properties["Captured URL"] = {"url": captured_url}
    return properties


def _capture_blocks(
    draft: ConfirmedApplicationDraft,
    *,
    captured_at: datetime,
    captured_url: str | None,
    parsing_notes: tuple[str, ...],
) -> list[dict]:
    blocks = [
        _block("heading_2", "Capture Summary"),
        _block("bulleted_list_item", f"Source: {draft.job_url}"),
        _block("bulleted_list_item", f"Captured: {captured_at.isoformat()}"),
    ]
    if captured_url:
        blocks.append(_block("bulleted_list_item", f"Captured URL: {captured_url}"))
    blocks.extend(
        _block("bulleted_list_item", f"Note: {note}")
        for note in parsing_notes
        if note.strip()
    )
    blocks.append(_block("heading_2", "Job Content"))
    blocks.extend(_content_blocks(draft.job_content))
    return blocks


def _content_blocks(content: str) -> list[dict]:
    output: list[dict] = []
    for paragraph in re.split(r"\n\s*\n", content.strip()):
        text = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        for start in range(0, len(text), 1900):
            value = text[start : start + 1900].strip()
            if value:
                output.append(_block("paragraph", value))
    return output or [_block("paragraph", "No job content was captured.")]


def _block(block_type: str, content: str) -> dict:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": _rich_text(content)},
    }


def _document_block(value: DocumentBlock) -> dict:
    supported = {
        "heading_1",
        "heading_2",
        "heading_3",
        "paragraph",
        "quote",
        "callout",
        "bulleted_list_item",
        "numbered_list_item",
    }
    kind = value.kind if value.kind in supported else "paragraph"
    return _block(kind, value.text)


def _rich_text(content: str) -> list[dict]:
    return [
        {"type": "text", "text": {"content": content[index : index + 2000]}}
        for index in range(0, len(content), 2000)
    ]


def _chunks(items: list[dict], size: int) -> Iterable[list[dict]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _queue_page(
    applications: list[ApplicationRecord],
    limit: int,
    cursor: str | None,
    context: str,
) -> QueuePage:
    fingerprint = hashlib.sha256(
        "\n".join(item.id for item in applications).encode()
    ).hexdigest()[:16]
    offset = decode_cursor(cursor, context, fingerprint)
    if offset > len(applications):
        from ..shared.pagination import InvalidCursor

        raise InvalidCursor("Cursor is invalid or expired.")
    selected = tuple(applications[offset : offset + limit])
    next_offset = offset + len(selected)
    has_more = next_offset < len(applications)
    return QueuePage(
        items=selected,
        total=len(applications),
        limit=limit,
        next_cursor=(
            encode_cursor(next_offset, context, fingerprint) if has_more else None
        ),
        has_more=has_more,
    )


def _read_top_level_section(blocks: list[dict], heading: str) -> str:
    sections = _top_level_sections(blocks, {heading})
    if not sections:
        return ""
    _, content = sections[-1]
    return "\n".join(
        value for block in content if (value := _block_text(block))
    ).strip()


def _select_analysis(blocks: list[dict]) -> ApplicationAnalysisDocument | None:
    sections = _top_level_sections(
        blocks, {"Application Analysis", "Job Posting Analysis"}
    )
    parsed: list[ApplicationAnalysisDocument] = []
    for heading, content in sections:
        document = _parse_analysis_section(heading, content)
        if document is not None:
            parsed.append(document)
    canonical = [item for item in parsed if item.heading == "Application Analysis"]
    if canonical:
        return canonical[-1]
    legacy = [item for item in parsed if item.heading == "Job Posting Analysis"]
    return legacy[-1] if legacy else None


def _top_level_sections(
    blocks: list[dict], recognized: set[str]
) -> list[tuple[str, list[dict]]]:
    sections: list[tuple[str, list[dict]]] = []
    active_heading: str | None = None
    active_blocks: list[dict] = []
    for block in blocks:
        if block.get("type") == "heading_2":
            if active_heading is not None:
                sections.append((active_heading, active_blocks))
            value = _block_text(block)
            active_heading = value if value in recognized else None
            active_blocks = []
            continue
        if active_heading is not None:
            active_blocks.append(block)
    if active_heading is not None:
        sections.append((active_heading, active_blocks))
    return sections


def _parse_analysis_section(
    heading: str, blocks: list[dict]
) -> ApplicationAnalysisDocument | None:
    subsections: dict[str, list[str]] = {}
    active: str | None = None
    for block in blocks:
        if block.get("type") == "heading_3":
            active = _block_text(block)
            subsections.setdefault(active, [])
            continue
        if active:
            value = _block_text(block)
            if value:
                subsections[active].append(value)
    summary = " ".join(subsections.get("Summary") or ()).strip()
    signals = tuple(subsections.get("Skill Signals") or ())
    if not summary or not signals:
        return None
    score: int | None = None
    match_score_text = " ".join(subsections.get("Match Score") or ())
    match = re.search(r"(?:Match Score:\s*)?(\d{1,3})", match_score_text)
    if match:
        candidate = int(match.group(1))
        if 0 <= candidate <= 100:
            score = candidate
    if heading == "Application Analysis" and score is None:
        return None
    return ApplicationAnalysisDocument(
        summary=summary,
        match_score=score,
        skill_signals=signals,
        heading=heading,
    )


def _analysis_blocks(document: ApplicationAnalysisDocument) -> list[dict]:
    blocks = [
        _block("heading_2", "Application Analysis"),
        _block("heading_3", "Summary"),
        _block("paragraph", document.summary),
        _block("heading_3", "Match Score"),
        _block("bulleted_list_item", f"Match Score: {document.match_score}"),
        _block("heading_3", "Skill Signals"),
    ]
    blocks.extend(
        _block("bulleted_list_item", signal.text)
        for signal in document.skill_signals
    )
    return blocks


def _block_text(block: dict) -> str:
    if block.get("type") not in READABLE_BLOCK_TYPES:
        return ""
    typed = block.get(str(block.get("type"))) or {}
    return "".join(
        str(part.get("plain_text") or (part.get("text") or {}).get("content") or "")
        for part in typed.get("rich_text") or ()
    ).strip()
