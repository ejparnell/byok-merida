import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
import json

import httpx
import pytest

from merida_api.features.applications.capture import ApplicationCapture
from merida_api.features.applications.schemas import CaptureEvidence, ConfirmedApplicationDraft
from merida_api.features.applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
)
from merida_api.features.resumes.commit import ResumeArtifactCommitter
from merida_api.features.resumes.workspace import DocumentBlock, ResumeArtifactBundle
from merida_api.integrations.demo_workspace import DemoWorkspace, initial_demo_state
from merida_api.integrations.notion_workspace import (
    HttpxNotionTransport,
    NotionWorkspace,
)
from merida_api.shared.workspace import WorkspaceDataConflict, WorkspaceProviderError
from merida_api.integrations.pdf_export import LocalPdfArtifacts
from merida_api.shared.pagination import InvalidCursor
from merida_api.shared.workspace import WorkspaceDataError


def rich_text(value: str) -> list[dict]:
    return [{"plain_text": value, "text": {"content": value}}] if value else []


def application_schema(*, captured_url: bool = True) -> dict:
    properties = {
        "Job Posting": {"type": "title", "title": {}},
        "Company Name": {"type": "rich_text", "rich_text": {}},
        "Job Title": {"type": "rich_text", "rich_text": {}},
        "Job URL": {"type": "url", "url": {}},
        "Location": {"type": "rich_text", "rich_text": {}},
        "Application Date": {"type": "date", "date": {}},
        "Application Status": {
            "type": "select",
            "select": {
                "options": [
                    {"name": "To Apply"},
                    {"name": "Applied"},
                    {"name": "Rejected"},
                    {"name": "Not Interested"},
                    {"name": "Archived"},
                ]
            },
        },
        "Analyzed": {"type": "checkbox", "checkbox": {}},
        "Match Score": {"type": "number", "number": {}},
        "Resumes": {"type": "relation", "relation": {}},
        "Notes": {"type": "relation", "relation": {}},
    }
    if captured_url:
        properties["Captured URL"] = {"type": "url", "url": {}}
    return {"id": "applications-db", "properties": properties}


def relational_schemas() -> tuple[dict, dict, dict]:
    applications = application_schema()
    applications["data_sources"] = [{"id": "applications-source"}]
    applications["properties"]["Resumes"] = {
        "type": "relation",
        "relation": {
            "data_source_id": "resumes-source",
            "dual_property": {"synced_property_name": "Job Posting"},
        },
    }
    applications["properties"]["Notes"] = {
        "type": "relation",
        "relation": {
            "database_id": "notes-db",
            "dual_property": {"synced_property_name": "Job Posting"},
        },
    }
    resumes = {
        "id": "resumes-db",
        "data_sources": [{"id": "resumes-source"}],
        "properties": {
            "Name": {"type": "title", "title": {}},
            "Job Posting": {
                "type": "relation",
                "relation": {
                    "data_source_id": "applications-source",
                    "dual_property": {"synced_property_name": "Resumes"},
                },
            },
            "Notes": {
                "type": "relation",
                "relation": {
                    "database_id": "notes-db",
                    "dual_property": {"synced_property_name": "Resume"},
                },
            },
        },
    }
    notes = {
        "id": "notes-db",
        "properties": {
            "Name": {"type": "title", "title": {}},
            "Job Posting": {
                "type": "relation",
                "relation": {
                    "database_id": "applications-db",
                    "dual_property": {"synced_property_name": "Notes"},
                },
            },
            "Resume": {
                "type": "relation",
                "relation": {
                    "data_source_id": "resumes-source",
                    "dual_property": {"synced_property_name": "Notes"},
                },
            },
        },
    }
    return applications, resumes, notes


def application_page(**overrides) -> dict:
    values = {
        "id": "application-1",
        "url": "https://www.notion.so/application-1",
        "properties": {
            "Job Posting": {"type": "title", "title": rich_text("Engineer at Example")},
            "Company Name": {"type": "rich_text", "rich_text": rich_text("Example")},
            "Job Title": {"type": "rich_text", "rich_text": rich_text("Engineer")},
            "Job URL": {"type": "url", "url": "https://example.test/jobs/1"},
            "Captured URL": {"type": "url", "url": "https://example.test/jobs/1?utm_source=x"},
            "Location": {"type": "rich_text", "rich_text": []},
            "Application Date": {"type": "date", "date": {"start": "2026-07-11"}},
            "Application Status": {"type": "select", "select": {"name": "To Apply"}},
            "Analyzed": {"type": "checkbox", "checkbox": False},
            "Match Score": {"type": "number", "number": None},
            "Resumes": {"type": "relation", "relation": []},
            "Notes": {"type": "relation", "relation": []},
        },
    }
    values.update(overrides)
    return values


def block(block_type: str, value: str) -> dict:
    return {
        "id": f"block-{block_type}-{value}",
        "type": block_type,
        block_type: {"rich_text": rich_text(value)},
        "has_children": False,
    }


def captured_body(
    *,
    analysis_heading: str | None = None,
    score: int | None = None,
    summary: str = "The role needs reliable product engineering.",
) -> list[dict]:
    blocks = [
        block("heading_2", "Capture Summary"),
        block("bulleted_list_item", "Source: https://example.test/jobs/1"),
        block("heading_2", "Job Content"),
        block("paragraph", "Build reliable Python services and accessible React interfaces."),
    ]
    if analysis_heading:
        blocks.extend(
            [
                block("heading_2", analysis_heading),
                block("heading_3", "Summary"),
                block("paragraph", summary),
            ]
        )
        if score is not None:
            blocks.extend(
                [
                    block("heading_3", "Match Score"),
                    block("bulleted_list_item", f"Match Score: {score}"),
                ]
            )
        blocks.extend(
            [
                block("heading_3", "Skill Signals"),
                block("bulleted_list_item", "Programming Languages: Python"),
            ]
        )
    return blocks


class RecordingTransport:
    def __init__(self, responses: list[dict | Exception]):
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict | None]] = []

    async def request(self, method: str, path: str, body: dict | None = None) -> dict:
        self.requests.append((method, path, body))
        if not self.responses:
            raise AssertionError(f"Unexpected Notion request: {method} {path}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def workspace(transport: RecordingTransport) -> NotionWorkspace:
    return NotionWorkspace(
        transport=transport,
        application_database_id="applications-db",
        resume_database_id="resumes-db",
        notes_database_id="notes-db",
    )


def test_capture_readiness_uses_legacy_physical_properties_and_warns_for_optional_captured_url():
    transport = RecordingTransport([application_schema(captured_url=False)])

    readiness = asyncio.run(workspace(transport).validate_capture_workspace())

    assert readiness.ready is True
    assert readiness.errors == ()
    assert [(warning.database, warning.property) for warning in readiness.warnings] == [
        ("applications", "Captured URL")
    ]
    assert transport.requests == [("GET", "/databases/applications-db", None)]


def test_capture_readiness_warns_without_blocking_for_unknown_status_options():
    schema = application_schema()
    schema["properties"]["Application Status"]["select"]["options"].append(
        {"name": "Maybe Later"}
    )
    transport = RecordingTransport([schema])

    readiness = asyncio.run(workspace(transport).validate_capture_workspace())

    assert readiness.ready is True
    assert any("Maybe Later" in warning.message for warning in readiness.warnings)


def test_capture_store_projects_a_legacy_job_posting_page_into_canonical_application_values():
    transport = RecordingTransport(
        [{"results": [application_page()], "has_more": False, "next_cursor": None}]
    )

    result = asyncio.run(
        workspace(transport).find_application_by_job_url(
            "https://example.test/jobs/1"
        )
    )

    assert result is not None
    assert result.id == "application-1"
    assert result.title == "Engineer at Example"
    assert result.company_name == "Example"
    assert result.role == "Engineer"
    assert result.location is None
    assert result.date_found == date(2026, 7, 11)
    assert result.job_url == "https://example.test/jobs/1"
    assert result.captured_url == "https://example.test/jobs/1?utm_source=x"
    assert result.application_status == "To Apply"
    assert result.analyzed is False
    assert result.match_score is None
    assert transport.requests[0] == (
        "POST",
        "/databases/applications-db/query",
        {
            "filter": {
                "property": "Job URL",
                "url": {"equals": "https://example.test/jobs/1"},
            },
            "page_size": 2,
        },
    )


def test_application_projection_rejects_fractional_scores_and_empty_identity():
    fractional = application_page(
        properties={
            **application_page()["properties"],
            "Match Score": {"type": "number", "number": 87.6},
        }
    )
    missing_identity = application_page(id="", url="")

    for page, message in (
        (fractional, "integer"),
        (missing_identity, "ID is missing"),
    ):
        transport = RecordingTransport(
            [{"results": [page], "has_more": False, "next_cursor": None}]
        )
        try:
            asyncio.run(
                workspace(transport).find_application_by_job_url(
                    "https://example.test/jobs/1"
                )
            )
        except WorkspaceDataError as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected malformed Notion identity data to fail.")


def test_capture_store_writes_canonical_draft_through_legacy_properties_and_stable_body_sections():
    created = application_page()
    transport = RecordingTransport([application_schema(), created])
    draft = ConfirmedApplicationDraft(
        jobUrl="https://example.test/jobs/1",
        companyName="Example",
        role="Engineer",
        location=None,
        jobContent="Build reliable Python services and accessible React interfaces.",
    )

    result = asyncio.run(
        workspace(transport).create_application(
            draft,
            captured_at=datetime(2026, 7, 11, 15, 30, tzinfo=timezone.utc),
            captured_url="https://example.test/jobs/1?utm_source=x",
            parsing_notes=("Selected text used.",),
        )
    )

    assert result.id == "application-1"
    _, path, body = transport.requests[1]
    assert path == "/pages"
    assert body is not None
    properties = body["properties"]
    assert set(properties) == {
        "Job Posting",
        "Company Name",
        "Job Title",
        "Job URL",
        "Captured URL",
        "Location",
        "Application Date",
        "Application Status",
        "Analyzed",
    }
    assert properties["Job Posting"]["title"][0]["text"]["content"] == "Engineer at Example"
    assert properties["Job Title"]["rich_text"][0]["text"]["content"] == "Engineer"
    assert properties["Application Date"] == {"date": {"start": "2026-07-11"}}
    assert properties["Application Status"] == {"select": {"name": "To Apply"}}
    assert properties["Analyzed"] == {"checkbox": False}
    assert "Match Score" not in properties
    headings = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in body["children"]
        if block["type"].startswith("heading_")
    ]
    assert headings == ["Capture Summary", "Job Content"]


def test_analysis_queue_filters_unreadable_bodies_and_returns_merida_owned_cursor():
    first = application_page()
    second = application_page(
        id="application-2",
        url="https://www.notion.so/application-2",
        properties={
            **application_page()["properties"],
            "Job Posting": {"type": "title", "title": rich_text("Developer at Example")},
            "Job Title": {"type": "rich_text", "rich_text": rich_text("Developer")},
            "Job URL": {"type": "url", "url": "https://example.test/jobs/2"},
            "Application Date": {"type": "date", "date": {"start": "2026-07-12"}},
        },
    )
    unreadable = application_page(
        id="application-3",
        url="https://www.notion.so/application-3",
        properties={
            **application_page()["properties"],
            "Job Posting": {"type": "title", "title": rich_text("Architect at Example")},
            "Job Title": {"type": "rich_text", "rich_text": rich_text("Architect")},
            "Job URL": {"type": "url", "url": "https://example.test/jobs/3"},
            "Application Date": {"type": "date", "date": {"start": "2026-07-13"}},
        },
    )
    transport = RecordingTransport(
        [
            {"results": [first, second, unreadable], "has_more": False, "next_cursor": "notion-next"},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {"results": [block("paragraph", "User notes only")], "has_more": False, "next_cursor": None},
        ]
    )

    page = asyncio.run(workspace(transport).list_analysis_queue(limit=1, cursor=None))

    assert page.total == 2
    assert [item.id for item in page.items] == ["application-1"]
    assert page.has_more is True
    assert page.next_cursor
    assert page.next_cursor != "notion-next"
    method, path, body = transport.requests[0]
    assert (method, path) == ("POST", "/databases/applications-db/query")
    assert body["filter"] == {
        "and": [
            {"property": "Application Status", "select": {"equals": "To Apply"}},
            {"property": "Analyzed", "checkbox": {"equals": False}},
        ]
    }
    assert body["sorts"] == [
        {"property": "Application Date", "direction": "ascending"}
    ]


def test_analysis_store_reads_legacy_analysis_without_merging_raw_blocks():
    transport = RecordingTransport(
        [
            application_page(),
            {
                "results": captured_body(analysis_heading="Job Posting Analysis"),
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )

    result = asyncio.run(workspace(transport).load_analysis_input("application-1"))

    assert result.job_content == "Build reliable Python services and accessible React interfaces."
    assert result.analysis == ApplicationAnalysisDocument(
        summary="The role needs reliable product engineering.",
        match_score=None,
        skill_signals=("Programming Languages: Python",),
        heading="Job Posting Analysis",
    )


def test_analysis_store_appends_canonical_body_before_final_properties():
    transport = RecordingTransport([{}, {}])
    document = ApplicationAnalysisDocument(
        summary="Sentence one. Sentence two. Sentence three.",
        match_score=84,
        skill_signals=("Programming Languages: Python", "Frameworks & Libraries: React"),
        heading="Application Analysis",
    )
    store = workspace(transport)

    asyncio.run(store.append_application_analysis("application-1", document))
    asyncio.run(store.finalize_application_analysis("application-1", match_score=84))

    append_request, finalize_request = transport.requests
    assert append_request[0:2] == ("PATCH", "/blocks/application-1/children")
    headings = [
        item[item["type"]]["rich_text"][0]["text"]["content"]
        for item in append_request[2]["children"]
        if item["type"].startswith("heading_")
    ]
    assert headings == ["Application Analysis", "Summary", "Match Score", "Skill Signals"]
    assert finalize_request == (
        "PATCH",
        "/pages/application-1",
        {
            "properties": {
                "Match Score": {"number": 84},
                "Analyzed": {"checkbox": True},
            }
        },
    )


def test_notion_body_writer_splits_long_rich_text_without_truncating_content():
    transport = RecordingTransport([{}])
    summary = "evidence " * 700
    document = ApplicationAnalysisDocument(
        summary=summary,
        match_score=84,
        skill_signals=("Programming Languages: Python",),
        heading="Application Analysis",
    )

    asyncio.run(
        workspace(transport).append_application_analysis("application-1", document)
    )

    summary_block = transport.requests[0][2]["children"][2]
    parts = summary_block["paragraph"]["rich_text"]
    assert len(parts) > 1
    assert "".join(part["text"]["content"] for part in parts) == summary


def test_resume_readiness_accepts_database_and_data_source_relation_targets():
    transport = RecordingTransport(list(relational_schemas()))

    readiness = asyncio.run(workspace(transport).validate_resume_workspace())

    assert readiness.ready is True
    assert readiness.errors == ()
    assert readiness.warnings == ()


def test_resume_queue_requires_readable_canonical_or_legacy_analysis():
    eligible = application_page(
        properties={
            **application_page()["properties"],
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 88},
        }
    )
    unreadable = application_page(
        id="application-2",
        properties={
            **application_page()["properties"],
            "Job URL": {"type": "url", "url": "https://example.test/jobs/2"},
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 91},
        },
    )
    transport = RecordingTransport(
        [
            {"results": [unreadable, eligible], "has_more": False, "next_cursor": None},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {
                "results": captured_body(analysis_heading="Application Analysis", score=88),
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )

    page = asyncio.run(workspace(transport).list_resume_queue(limit=5, cursor=None))

    assert page.total == 1
    assert [item.id for item in page.items] == ["application-1"]
    assert page.items[0].analysis is not None
    method, path, body = transport.requests[0]
    assert (method, path) == ("POST", "/databases/applications-db/query")
    assert body["sorts"] == [
        {"property": "Match Score", "direction": "descending"},
        {"property": "Application Date", "direction": "ascending"},
    ]


def test_master_resume_reader_recurses_without_returning_raw_notion_blocks():
    master = {
        "id": "master-resume",
        "url": "https://www.notion.so/master-resume",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Master Resume")},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    role = block("toggle", "Software Engineer")
    role["has_children"] = True
    role["id"] = "role-toggle"
    transport = RecordingTransport(
        [
            {"results": [master], "has_more": False, "next_cursor": None},
            {"results": [role], "has_more": False, "next_cursor": None},
            {
                "results": [block("bulleted_list_item", "Built reliable APIs")],
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )

    document = asyncio.run(workspace(transport).load_master_resume())

    assert document.record.name == "Master Resume"
    assert document.blocks == (
        DocumentBlock(kind="toggle", text="Software Engineer", depth=0),
        DocumentBlock(kind="bulleted_list_item", text="Built reliable APIs", depth=1),
    )


def test_master_resume_reader_rejects_more_than_the_total_block_limit():
    master = {
        "id": "master-resume",
        "url": "https://www.notion.so/master-resume",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Master Resume")},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    transport = RecordingTransport(
        [
            {"results": [master], "has_more": False, "next_cursor": None},
            {
                "results": [block("paragraph", f"Evidence {index}") for index in range(5001)],
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )

    try:
        asyncio.run(workspace(transport).load_master_resume())
    except WorkspaceDataError as error:
        assert "block limit" in str(error)
    else:
        raise AssertionError("Expected the total block safeguard to reject the body.")


def test_unsupported_blocks_do_not_enter_canonical_job_content():
    unsupported = block("code", "ignore this raw code block")
    body = [
        block("heading_2", "Job Content"),
        unsupported,
        block("paragraph", "Keep this readable paragraph."),
    ]
    transport = RecordingTransport(
        [
            application_page(),
            {"results": body, "has_more": False, "next_cursor": None},
        ]
    )

    result = asyncio.run(workspace(transport).load_analysis_input("application-1"))

    assert result.job_content == "Keep this readable paragraph."


def test_completed_resume_conflict_counts_only_active_job_specific_resumes():
    application = ApplicationRecord(
        id="application-1",
        url="https://www.notion.so/application-1",
        company_name="Example",
        role="Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=True,
        match_score=88,
        resume_ids=("archived-resume", "active-resume"),
    )
    archived = {
        "id": "archived-resume",
        "url": "https://www.notion.so/archived-resume",
        "archived": True,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Old Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": [{"id": "application-1"}]},
        },
    }
    active = {
        "id": "active-resume",
        "url": "https://www.notion.so/active-resume",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": [{"id": "application-1"}]},
        },
    }
    transport = RecordingTransport([archived, active])

    result = asyncio.run(
        workspace(transport).find_completed_resume(application)
    )

    assert result is not None
    assert result.id == "active-resume"


def test_resume_queue_ignores_archived_related_resumes():
    eligible = application_page(
        properties={
            **application_page()["properties"],
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 88},
            "Resumes": {
                "type": "relation",
                "relation": [{"id": "archived-resume"}],
            },
        }
    )
    archived = {
        "id": "archived-resume",
        "url": "https://www.notion.so/archived-resume",
        "archived": True,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Old Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": [{"id": "application-1"}]},
        },
    }
    transport = RecordingTransport(
        [
            {"results": [eligible], "has_more": False, "next_cursor": None},
            archived,
            {
                "results": captured_body(analysis_heading="Application Analysis", score=88),
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )

    page = asyncio.run(workspace(transport).list_resume_queue(limit=5, cursor=None))

    assert [item.id for item in page.items] == ["application-1"]


def test_resume_artifact_writes_keep_resume_unlinked_until_final_attachment_and_archive_cleanup():
    resume_page = {
        "id": "resume-1",
        "url": "https://www.notion.so/resume-1",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    note_page = {
        "id": "note-1",
        "url": "https://www.notion.so/note-1",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Resume Fit Analysis - Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": [{"id": "application-1"}]},
            "Resume": {"type": "relation", "relation": [{"id": "resume-1"}]},
        },
    }
    transport = RecordingTransport([resume_page, note_page, resume_page, {}, {}])
    store = workspace(transport)

    resume = asyncio.run(
        store.create_resume_draft(
            "Engineer at Example",
            (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),),
        )
    )
    note = asyncio.run(
        store.create_resume_fit_note(
            "Resume Fit Analysis - Engineer at Example",
            application_id="application-1",
            resume_id=resume.id,
            document=(DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),),
        )
    )
    asyncio.run(store.attach_resume_to_application(resume.id, "application-1"))
    asyncio.run(store.archive_note(note.id))
    asyncio.run(store.archive_resume(resume.id))

    create_resume, create_note, attach, archive_note, archive_resume = transport.requests
    assert create_resume[2]["properties"] == {
        "Name": {"title": [{"type": "text", "text": {"content": "Engineer at Example"}}]}
    }
    assert "Job Posting" not in create_resume[2]["properties"]
    assert create_note[2]["properties"]["Job Posting"] == {
        "relation": [{"id": "application-1"}]
    }
    assert create_note[2]["properties"]["Resume"] == {
        "relation": [{"id": "resume-1"}]
    }
    assert attach == (
        "PATCH",
        "/pages/resume-1",
        {"properties": {"Job Posting": {"relation": [{"id": "application-1"}]}}},
    )
    assert archive_note == ("PATCH", "/pages/note-1", {"archived": True})
    assert archive_resume == ("PATCH", "/pages/resume-1", {"archived": True})


def test_demo_analysis_store_preserves_body_first_property_second_commit_contract(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    document = ApplicationAnalysisDocument(
        summary="Sentence one. Sentence two. Sentence three.",
        match_score=84,
        skill_signals=("Programming Languages: Python",),
        heading="Application Analysis",
    )

    asyncio.run(store.append_application_analysis("app-northstar", document))
    after_body = asyncio.run(store.load_analysis_input("app-northstar"))

    assert after_body.analysis == document
    assert after_body.match_score is None
    assert after_body.analyzed is False

    asyncio.run(
        store.finalize_application_analysis("app-northstar", match_score=84)
    )
    completed = asyncio.run(store.load_analysis_input("app-northstar"))
    assert completed.match_score == 84
    assert completed.analyzed is True


def test_capture_workflow_carries_exact_source_url_from_prepare_into_confirm(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    capture = ApplicationCapture(store)
    evidence = CaptureEvidence(
        url="https://example.test/jobs/42?utm_source=newsletter",
        title="Engineer at Example",
        selectedText="Example is hiring an Engineer to build reliable Python services.",
    )

    prepared = asyncio.run(capture.prepare(evidence))
    asyncio.run(
        capture.confirm(
            ConfirmedApplicationDraft(
                jobUrl=prepared.draft.job_url,
                companyName=prepared.draft.company_name,
                role=prepared.draft.role,
                location=None,
                jobContent=evidence.selected_text,
            )
        )
    )

    created = next(
        item
        for item in store.snapshot()["applications"]
        if item["jobUrl"] == "https://example.test/jobs/42"
    )
    assert created["capturedUrl"] == evidence.url


def test_demo_resume_store_uses_relation_last_as_the_completion_marker(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    document = (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),)

    draft = asyncio.run(store.create_resume_draft("Engineer at Example", document))
    assert draft.application_ids == ()
    application_before = asyncio.run(store.load_resume_input("app-orbit"))
    assert asyncio.run(store.find_completed_resume(application_before)) is None

    attached = asyncio.run(
        store.attach_resume_to_application(draft.id, application_before.id)
    )
    application_after = asyncio.run(store.load_resume_input("app-orbit"))

    assert attached.application_ids == ("app-orbit",)
    assert asyncio.run(store.find_completed_resume(application_after)) == attached


def test_artifact_committer_clears_a_relation_when_final_attach_response_fails(tmp_path):
    class AppliedThenFailedWorkspace(DemoWorkspace):
        async def attach_resume_to_application(self, resume_id, application_id):
            await super().attach_resume_to_application(resume_id, application_id)
            raise RuntimeError("simulated response loss after relation write")

    store = AppliedThenFailedWorkspace(
        tmp_path / "state.json", tmp_path / "export"
    )
    application = asyncio.run(store.load_resume_input("app-orbit"))
    pdfs = LocalPdfArtifacts(tmp_path / "export")
    result = asyncio.run(
        assert_artifact_compensation_contract(store, application, pdfs)
    )

    state = store.snapshot()
    current = next(item for item in state["applications"] if item["id"] == "app-orbit")
    assert result.cleanup_status == "completed"
    assert current["resumeId"] is None
    assert all(resume["archived"] for resume in state["resumes"].values())
    assert all(note["archived"] for note in state["notes"].values())
    assert not list((tmp_path / "export").glob("*.pdf"))


async def assert_artifact_compensation_contract(store, application, pdfs):
    bundle = ResumeArtifactBundle(
        resume=(DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),),
        note=(DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),),
        pdf_lines=("Elizabeth Parnell", application.title),
    )
    result = await ResumeArtifactCommitter(store, pdfs).commit(application, bundle)

    assert result.committed is False
    assert result.cleanup_status == "completed"
    assert result.cleanup_errors == ()
    return result


def test_notion_artifact_compensation_conformance(tmp_path):
    application = ApplicationRecord(
        id="application-1",
        url="https://www.notion.so/application-1",
        company_name="Example",
        role="Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=True,
        match_score=88,
    )
    draft = {
        "id": "resume-1",
        "url": "https://www.notion.so/resume-1",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text(application.title)},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    note = {
        "id": "note-1",
        "url": "https://www.notion.so/note-1",
        "archived": False,
        "properties": {
            "Name": {
                "type": "title",
                "title": rich_text(f"Resume Fit Analysis - {application.title}"),
            },
            "Job Posting": {
                "type": "relation",
                "relation": [{"id": application.id}],
            },
            "Resume": {"type": "relation", "relation": [{"id": "resume-1"}]},
        },
    }
    transport = RecordingTransport(
        [
            draft,
            note,
            WorkspaceProviderError("Safe injected attach failure."),
            {},
            {},
            {},
        ]
    )
    pdfs = LocalPdfArtifacts(tmp_path / "export")

    asyncio.run(
        assert_artifact_compensation_contract(
            workspace(transport), application, pdfs
        )
    )

    assert not list((tmp_path / "export").glob("*.pdf"))


async def assert_capture_store_contract(store, existing_job_url: str):
    readiness = await store.validate_capture_workspace()
    existing = await store.find_application_by_job_url(existing_job_url)

    assert readiness.ready is True
    assert existing is not None
    assert existing.job_url == existing_job_url
    assert existing.title == f"{existing.role} at {existing.company_name}"
    assert existing.application_status == "To Apply"


def test_demo_capture_store_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(
        assert_capture_store_contract(
            store, "https://jobs.example.test/northstar/frontend"
        )
    )


def test_notion_capture_store_conformance():
    transport = RecordingTransport(
        [
            application_schema(),
            {"results": [application_page()], "has_more": False, "next_cursor": None},
        ]
    )
    asyncio.run(
        assert_capture_store_contract(
            workspace(transport), "https://example.test/jobs/1"
        )
    )


async def assert_capture_write_contract(store, job_url: str):
    assert await store.find_application_by_job_url(job_url) is None
    created = await store.create_application(
        ConfirmedApplicationDraft(
            jobUrl=job_url,
            companyName="Conformance Co",
            role="Platform Engineer",
            location=None,
            jobContent="Build reliable Python APIs and accessible React interfaces.",
        ),
        captured_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
        captured_url=f"{job_url}?utm_source=test",
        parsing_notes=("Conformance fixture",),
    )
    found = await store.find_application_by_job_url(job_url)

    assert found is not None
    assert found.id == created.id
    assert found.captured_url == f"{job_url}?utm_source=test"
    assert found.match_score is None
    assert found.analyzed is False


def test_demo_capture_write_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(
        assert_capture_write_contract(store, "https://jobs.example.test/new-role")
    )


def test_notion_capture_write_conformance():
    created = application_page(
        id="created-application",
        url="https://www.notion.so/created-application",
        properties={
            **application_page()["properties"],
            "Job Posting": {
                "type": "title",
                "title": rich_text("Platform Engineer at Conformance Co"),
            },
            "Company Name": {
                "type": "rich_text",
                "rich_text": rich_text("Conformance Co"),
            },
            "Job Title": {
                "type": "rich_text",
                "rich_text": rich_text("Platform Engineer"),
            },
            "Job URL": {
                "type": "url",
                "url": "https://example.test/jobs/conformance",
            },
            "Captured URL": {
                "type": "url",
                "url": "https://example.test/jobs/conformance?utm_source=test",
            },
        },
    )
    transport = RecordingTransport(
        [
            {"results": [], "has_more": False, "next_cursor": None},
            application_schema(),
            created,
            {"results": [created], "has_more": False, "next_cursor": None},
        ]
    )
    asyncio.run(
        assert_capture_write_contract(
            workspace(transport), "https://example.test/jobs/conformance"
        )
    )


async def assert_capture_duplicate_conflict_contract(store, job_url: str):
    try:
        await store.find_application_by_job_url(job_url)
    except WorkspaceDataConflict:
        pass
    else:
        raise AssertionError("Expected duplicate canonical Job URLs to conflict.")


def test_demo_capture_duplicate_conflict_conformance(tmp_path):
    state = initial_demo_state()
    state["applications"].append({**state["applications"][0], "id": "duplicate"})
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    store = DemoWorkspace(state_path, tmp_path / "export")
    asyncio.run(
        assert_capture_duplicate_conflict_contract(
            store, "https://jobs.example.test/northstar/frontend"
        )
    )


def test_notion_capture_duplicate_conflict_conformance():
    duplicate = application_page(
        id="application-2", url="https://www.notion.so/application-2"
    )
    transport = RecordingTransport(
        [
            {
                "results": [application_page(), duplicate],
                "has_more": False,
                "next_cursor": None,
            }
        ]
    )
    asyncio.run(
        assert_capture_duplicate_conflict_contract(
            workspace(transport), "https://example.test/jobs/1"
        )
    )


async def assert_capture_partial_failure_contract(store, job_url: str):
    draft = ConfirmedApplicationDraft(
        jobUrl=job_url,
        companyName="Failure Co",
        role="Engineer",
        location=None,
        jobContent="Build reliable Python services and React interfaces.",
    )
    try:
        await store.create_application(
            draft, captured_at=datetime(2026, 7, 11, tzinfo=timezone.utc)
        )
    except WorkspaceProviderError:
        pass
    else:
        raise AssertionError("Expected the injected capture write failure.")
    assert await store.find_application_by_job_url(job_url) is None


def test_demo_capture_partial_failure_conformance(tmp_path):
    class FailingCaptureStore(DemoWorkspace):
        async def create_application(self, *args, **kwargs):
            raise WorkspaceProviderError("Safe injected failure.")

    store = FailingCaptureStore(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(
        assert_capture_partial_failure_contract(
            store, "https://jobs.example.test/failing-role"
        )
    )


def test_notion_capture_partial_failure_conformance():
    transport = RecordingTransport(
        [
            application_schema(),
            WorkspaceProviderError("Safe injected failure."),
            {"results": [], "has_more": False, "next_cursor": None},
        ]
    )
    asyncio.run(
        assert_capture_partial_failure_contract(
            workspace(transport), "https://example.test/jobs/failing-role"
        )
    )


def test_notion_capture_reports_created_page_before_later_block_append_failure():
    created_page = application_page()
    transport = RecordingTransport(
        [
            application_schema(),
            created_page,
            WorkspaceProviderError("Safe injected append failure."),
        ]
    )
    recorded = []
    draft = ConfirmedApplicationDraft(
        jobUrl="https://example.test/jobs/append-failure",
        companyName="Failure Co",
        role="Engineer",
        location=None,
        jobContent="Build reliable Python services and React interfaces.",
    )

    async def create():
        await workspace(transport).create_application(
            draft,
            captured_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
            parsing_notes=tuple(f"Parsing note {index}" for index in range(90)),
            on_created=recorded.append,
        )

    with pytest.raises(WorkspaceProviderError):
        asyncio.run(create())

    assert [record.id for record in recorded] == ["application-1"]


async def assert_analysis_store_contract(store):
    readiness = await store.validate_analysis_workspace()
    queue = await store.list_analysis_queue(limit=1, cursor=None)

    assert readiness.ready is True
    assert queue.total >= 1
    assert len(queue.items) == 1
    assert queue.items[0].job_content
    assert queue.items[0].application_status == "To Apply"
    if queue.next_cursor:
        next_page = await store.list_analysis_queue(
            limit=1, cursor=queue.next_cursor
        )
        assert next_page.items[0].id != queue.items[0].id
        await store.finalize_application_analysis(
            queue.items[0].id, match_score=queue.items[0].match_score
        )
        try:
            await store.list_analysis_queue(limit=1, cursor=queue.next_cursor)
        except InvalidCursor:
            pass
        else:
            raise AssertionError("Expected a queue mutation to expire the cursor.")


def test_demo_analysis_store_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(assert_analysis_store_contract(store))


def test_notion_analysis_store_conformance():
    second = application_page(
        id="application-2",
        url="https://www.notion.so/application-2",
        properties={
            **application_page()["properties"],
            "Job Posting": {
                "type": "title",
                "title": rich_text("Developer at Example"),
            },
            "Job Title": {
                "type": "rich_text",
                "rich_text": rich_text("Developer"),
            },
            "Job URL": {"type": "url", "url": "https://example.test/jobs/2"},
            "Application Date": {
                "type": "date",
                "date": {"start": "2026-07-12"},
            },
        },
    )
    transport = RecordingTransport(
        [
            application_schema(),
            {
                "results": [application_page(), second],
                "has_more": False,
                "next_cursor": None,
            },
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {
                "results": [application_page(), second],
                "has_more": False,
                "next_cursor": None,
            },
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
            {},
            {"results": [second], "has_more": False, "next_cursor": None},
            {"results": captured_body(), "has_more": False, "next_cursor": None},
        ]
    )
    asyncio.run(assert_analysis_store_contract(workspace(transport)))


async def assert_analysis_write_contract(store, application_id: str):
    document = ApplicationAnalysisDocument(
        summary="Sentence one. Sentence two. Sentence three.",
        match_score=84,
        skill_signals=("Programming Languages: Python",),
        heading="Application Analysis",
    )
    await store.append_application_analysis(application_id, document)
    await store.finalize_application_analysis(application_id, match_score=84)
    completed = await store.load_analysis_input(application_id)

    assert completed.analysis == document
    assert completed.analyzed is True
    assert completed.match_score == 84


def test_demo_analysis_write_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(assert_analysis_write_contract(store, "app-northstar"))


def test_notion_analysis_write_conformance():
    completed = application_page(
        properties={
            **application_page()["properties"],
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 84},
        }
    )
    transport = RecordingTransport(
        [
            {},
            {},
            completed,
            {
                "results": captured_body(
                    analysis_heading="Application Analysis",
                    score=84,
                    summary="Sentence one. Sentence two. Sentence three.",
                ),
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )
    asyncio.run(
        assert_analysis_write_contract(workspace(transport), "application-1")
    )


async def assert_legacy_analysis_repair_contract(store, application_id: str):
    partial = await store.load_analysis_input(application_id)
    assert partial.analysis is not None
    assert partial.analysis.heading == "Job Posting Analysis"
    assert partial.analyzed is False

    repair_score = (
        partial.analysis.match_score
        if partial.analysis.match_score is not None
        else partial.match_score
    )
    await store.finalize_application_analysis(application_id, match_score=repair_score)
    repaired = await store.load_analysis_input(application_id)
    assert repaired.analyzed is True
    assert repaired.match_score == repair_score


def test_demo_legacy_analysis_repair_conformance(tmp_path):
    state = initial_demo_state()
    application = state["applications"][0]
    application["analysis"] = {
        "summary": "Existing legacy analysis.",
        "skillSignals": ["Programming Languages: Python"],
        "heading": "Job Posting Analysis",
    }
    application["matchScore"] = 77
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    asyncio.run(
        assert_legacy_analysis_repair_contract(
            DemoWorkspace(state_path, tmp_path / "export"), "app-northstar"
        )
    )


def test_notion_legacy_analysis_repair_conformance():
    partial = application_page(
        properties={
            **application_page()["properties"],
            "Match Score": {"type": "number", "number": 77},
        }
    )
    repaired = application_page(
        properties={
            **application_page()["properties"],
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 77},
        }
    )
    legacy_body = captured_body(analysis_heading="Job Posting Analysis")
    transport = RecordingTransport(
        [
            partial,
            {"results": legacy_body, "has_more": False, "next_cursor": None},
            {},
            repaired,
            {"results": legacy_body, "has_more": False, "next_cursor": None},
        ]
    )
    asyncio.run(
        assert_legacy_analysis_repair_contract(
            workspace(transport), "application-1"
        )
    )
    assert not any(
        method == "PATCH" and path.startswith("/blocks/")
        for method, path, _body in transport.requests
    )


async def assert_resume_store_contract(store):
    readiness = await store.validate_resume_workspace()
    queue = await store.list_resume_queue(limit=1, cursor=None)
    master = await store.load_master_resume()

    assert readiness.ready is True
    assert queue.total >= 1
    assert queue.items[0].analysis is not None
    assert queue.items[0].match_score is not None
    assert master.record.name == "Master Resume"
    assert master.blocks


def test_demo_resume_store_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    asyncio.run(assert_resume_store_contract(store))


def test_notion_resume_store_conformance():
    eligible = application_page(
        properties={
            **application_page()["properties"],
            "Analyzed": {"type": "checkbox", "checkbox": True},
            "Match Score": {"type": "number", "number": 88},
        }
    )
    master = {
        "id": "master-resume",
        "url": "https://www.notion.so/master-resume",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Master Resume")},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    transport = RecordingTransport(
        [
            *relational_schemas(),
            {"results": [eligible], "has_more": False, "next_cursor": None},
            {
                "results": captured_body(analysis_heading="Application Analysis", score=88),
                "has_more": False,
                "next_cursor": None,
            },
            {"results": [master], "has_more": False, "next_cursor": None},
            {
                "results": [block("bulleted_list_item", "Built reliable APIs")],
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )
    asyncio.run(assert_resume_store_contract(workspace(transport)))


async def assert_resume_artifact_store_contract(store, application):
    resume = await store.create_resume_draft(
        application.title,
        (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),),
    )
    assert resume.application_ids == ()
    note = await store.create_resume_fit_note(
        f"Resume Fit Analysis - {application.title}",
        application_id=application.id,
        resume_id=resume.id,
        document=(DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),),
    )
    attached = await store.attach_resume_to_application(resume.id, application.id)
    related_application = replace(application, resume_ids=(resume.id,))
    existing = await store.find_completed_resume(related_application)

    assert note.application_ids == (application.id,)
    assert note.resume_ids == (resume.id,)
    assert attached.application_ids == (application.id,)
    assert existing is not None
    assert existing.id == resume.id
    await store.clear_resume_application(resume.id)
    await store.archive_note(note.id)
    await store.archive_resume(resume.id)
    assert await store.find_completed_resume(related_application) is None


def test_demo_resume_artifact_store_conformance(tmp_path):
    store = DemoWorkspace(tmp_path / "state.json", tmp_path / "export")
    application = asyncio.run(store.load_resume_input("app-orbit"))
    asyncio.run(assert_resume_artifact_store_contract(store, application))


def test_notion_resume_artifact_store_conformance():
    application = ApplicationRecord(
        id="application-1",
        url="https://www.notion.so/application-1",
        company_name="Example",
        role="Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=True,
        match_score=88,
    )
    draft = {
        "id": "resume-1",
        "url": "https://www.notion.so/resume-1",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": rich_text("Engineer at Example")},
            "Job Posting": {"type": "relation", "relation": []},
        },
    }
    note = {
        "id": "note-1",
        "url": "https://www.notion.so/note-1",
        "archived": False,
        "properties": {
            "Name": {
                "type": "title",
                "title": rich_text("Resume Fit Analysis - Engineer at Example"),
            },
            "Job Posting": {
                "type": "relation",
                "relation": [{"id": "application-1"}],
            },
            "Resume": {"type": "relation", "relation": [{"id": "resume-1"}]},
        },
    }
    attached = {
        **draft,
        "properties": {
            **draft["properties"],
            "Job Posting": {
                "type": "relation",
                "relation": [{"id": "application-1"}],
            },
        },
    }
    archived = {**attached, "archived": True}
    transport = RecordingTransport(
        [draft, note, attached, attached, {}, {}, {}, archived]
    )
    asyncio.run(
        assert_resume_artifact_store_contract(workspace(transport), application)
    )


async def assert_multiple_resume_conflict_contract(store, application):
    try:
        await store.find_completed_resume(application)
    except WorkspaceDataConflict:
        pass
    else:
        raise AssertionError("Expected multiple active Resumes to conflict.")


def test_demo_multiple_resume_conflict_conformance(tmp_path):
    state = initial_demo_state()
    state["resumes"] = {
        "resume-1": {
            "id": "resume-1",
            "title": "Engineer at Example",
            "url": "https://www.notion.so/demo/resume-1",
            "applicationId": "app-orbit",
            "archived": False,
        },
        "resume-2": {
            "id": "resume-2",
            "title": "Engineer at Example",
            "url": "https://www.notion.so/demo/resume-2",
            "applicationId": "app-orbit",
            "archived": False,
        },
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    store = DemoWorkspace(state_path, tmp_path / "export")
    application = replace(
        asyncio.run(store.load_resume_input("app-orbit")),
        resume_ids=("resume-1", "resume-2"),
    )
    asyncio.run(assert_multiple_resume_conflict_contract(store, application))


def test_notion_multiple_resume_conflict_conformance():
    application = ApplicationRecord(
        id="application-1",
        url="https://www.notion.so/application-1",
        company_name="Example",
        role="Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=True,
        match_score=88,
        resume_ids=("resume-1", "resume-2"),
    )
    pages = [
        {
            "id": resume_id,
            "url": f"https://www.notion.so/{resume_id}",
            "archived": False,
            "properties": {
                "Name": {
                    "type": "title",
                    "title": rich_text("Engineer at Example"),
                },
                "Job Posting": {
                    "type": "relation",
                    "relation": [{"id": "application-1"}],
                },
            },
        }
        for resume_id in application.resume_ids
    ]
    asyncio.run(
        assert_multiple_resume_conflict_contract(
            workspace(RecordingTransport(pages)), application
        )
    )


def test_notion_transport_normalizes_provider_errors_without_leaking_payloads():
    def handler(_request):
        return httpx.Response(
            400,
            json={
                "code": "validation_error",
                "message": "private Job Content and secret-token-value",
            },
        )

    transport = HttpxNotionTransport(
        "secret-token-value",
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            transport=httpx.MockTransport(handler),
        ),
    )

    try:
        asyncio.run(transport.request("GET", "/databases/private"))
    except WorkspaceProviderError as error:
        assert error.status == 400
        assert error.code == "validation_error"
        assert str(error) == "Notion rejected the workspace operation."
        assert "private Job Content" not in str(error)
        assert "secret-token-value" not in str(error)
    else:
        raise AssertionError("Expected a normalized provider error.")


def test_notion_transport_normalizes_all_provider_status_classes():
    expected = {
        401: ("Notion authentication or workspace access is invalid.", False),
        403: ("Notion authentication or workspace access is invalid.", False),
        404: ("A configured Notion resource was not found.", False),
        409: ("Notion rejected the workspace operation.", False),
        429: ("Notion rate-limited the request.", True),
        500: ("Notion is temporarily unavailable.", True),
    }
    for status, (message, retryable) in expected.items():
        def handler(_request, status=status):
            return httpx.Response(
                status,
                json={
                    "code": f"provider_{status}",
                    "message": "private payload secret-token-value",
                },
            )

        transport = HttpxNotionTransport(
            "secret-token-value",
            client_factory=lambda handler=handler: httpx.AsyncClient(
                base_url="https://api.notion.com/v1",
                transport=httpx.MockTransport(handler),
            ),
        )
        try:
            asyncio.run(transport.request("GET", "/databases/private"))
        except WorkspaceProviderError as error:
            assert error.status == status
            assert error.code == f"provider_{status}"
            assert str(error) == message
            assert error.retryable is retryable
            assert "private payload" not in str(error)
            assert "secret-token-value" not in str(error)
        else:
            raise AssertionError(f"Expected status {status} to be normalized.")


def test_notion_transport_normalizes_timeouts_without_leaking_exception_text():
    def handler(request):
        raise httpx.ReadTimeout(
            "private Job Content secret-token-value", request=request
        )

    transport = HttpxNotionTransport(
        "secret-token-value",
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            transport=httpx.MockTransport(handler),
        ),
    )
    try:
        asyncio.run(transport.request("GET", "/databases/private"))
    except WorkspaceProviderError as error:
        assert str(error) == "Notion could not be reached."
        assert error.retryable is True
        assert "private Job Content" not in str(error)
        assert "secret-token-value" not in str(error)
    else:
        raise AssertionError("Expected timeout normalization.")


def test_notion_transport_normalizes_unexpected_transport_failures():
    def handler(_request):
        raise RuntimeError("private proxy failure secret-token-value")

    transport = HttpxNotionTransport(
        "secret-token-value",
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            transport=httpx.MockTransport(handler),
        ),
    )
    try:
        asyncio.run(transport.request("GET", "/databases/private"))
    except WorkspaceProviderError as error:
        assert str(error) == "Notion request failed unexpectedly."
        assert "private proxy failure" not in str(error)
        assert "secret-token-value" not in str(error)
    else:
        raise AssertionError("Expected unexpected transport normalization.")


def test_notion_transport_normalizes_malformed_success_payloads():
    transport = HttpxNotionTransport(
        "secret-token-value",
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, text="private malformed payload secret-token-value"
                )
            ),
        ),
    )

    try:
        asyncio.run(transport.request("GET", "/databases/private"))
    except WorkspaceProviderError as error:
        assert str(error) == "Notion returned an invalid response."
        assert error.status == 200
        assert "secret-token-value" not in str(error)
    else:
        raise AssertionError("Expected malformed success payload normalization.")
