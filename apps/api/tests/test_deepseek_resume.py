import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from merida_api.app import create_app
from merida_api.core.settings import Settings
from merida_api.features.applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
    PersistedSkillSignal,
)
from merida_api.features.resumes.resume_builder import (
    DeepSeekResumeDocumentBuilder,
    ResumeEvidenceError,
    _claim_supported,
    validate_master_resume_readiness,
    validate_master_resume_structure,
)
from merida_api.matching import MATCHING_V1, EvidenceItem, EvidenceMatchingEngine
from merida_api.features.resumes.workspace import (
    DocumentBlock,
    ResumeDocument,
    ResumeRecord,
)
from merida_api.integrations.deepseek import DeepSeekJsonClient
from merida_api.integrations.deepseek_resume import (
    DeepSeekFitRequirementModel,
    DeepSeekResumeDraftModel,
    create_deepseek_resume_builder,
)
from merida_api.shared.prompt_payload import JsonPromptPayloadEncoder
from fakes.workspace import FakeWorkspace


class RecordedChatModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    async def ainvoke(self, messages):
        self.messages.append(messages)
        return type("Message", (), {"content": self.responses.pop(0)})()


def recorded_resume_builder(chat: RecordedChatModel):
    client = DeepSeekJsonClient(chat)
    encoder = JsonPromptPayloadEncoder()
    return DeepSeekResumeDocumentBuilder(
        DeepSeekFitRequirementModel(client, encoder),
        DeepSeekResumeDraftModel(client, encoder),
    )


def test_resume_builder_uses_analysis_model_for_fit_requirements_and_resume_model_for_draft(
    monkeypatch,
):
    clients = []

    def create_client(**kwargs):
        client = object()
        clients.append((kwargs, client))
        return client

    monkeypatch.setattr(
        "merida_api.integrations.deepseek_resume.create_deepseek_json_client",
        create_client,
    )

    builder = create_deepseek_resume_builder(
        api_key="test-key",
        requirement_model="deepseek-v4-flash",
        resume_model="deepseek-v4-pro",
    )

    assert [kwargs for kwargs, _client in clients] == [
        {
            "api_key": "test-key",
            "model": "deepseek-v4-flash",
            "max_tokens": 8000,
            "timeout": 120,
        },
        {
            "api_key": "test-key",
            "model": "deepseek-v4-flash",
            "max_tokens": 16000,
            "timeout": 180,
        },
        {
            "api_key": "test-key",
            "model": "deepseek-v4-pro",
            "max_tokens": 8000,
        },
    ]
    assert builder._graph._requirement_model._client is clients[0][1]
    assert builder._graph._draft_model._primary._client is clients[1][1]
    assert builder._graph._draft_model._fallback._client is clients[2][1]


def analyzed_application(job_content: str) -> ApplicationRecord:
    return ApplicationRecord(
        id="application-1",
        url="https://notion.test/application-1",
        company_name="Example",
        role="Platform Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location="Remote",
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=True,
        match_score=88,
        job_content=job_content,
        analysis=ApplicationAnalysisDocument(
            summary="The role emphasizes reliable Python services.",
            match_score=88,
            skill_signals=(PersistedSkillSignal(text="Python", name="Python"),),
            heading="Application Analysis",
        ),
    )


def master_resume() -> ResumeDocument:
    return ResumeDocument(
        record=ResumeRecord(
            id="master-resume",
            url="https://notion.test/master-resume",
            name="Master Resume",
        ),
        blocks=(
            DocumentBlock(kind="heading_1", text="Candidate Name"),
            DocumentBlock(kind="paragraph", text="Boston | candidate@example.test"),
            DocumentBlock(kind="heading_2", text="Summary"),
            DocumentBlock(kind="paragraph", text="Original professional summary."),
            DocumentBlock(kind="heading_2", text="Software Engineer, Example Co"),
            DocumentBlock(kind="paragraph", text="2022 - Present"),
            DocumentBlock(kind="bulleted_list_item", text="Built reliable Python APIs."),
            DocumentBlock(kind="bulleted_list_item", text="Designed observable services."),
            DocumentBlock(kind="bulleted_list_item", text="Automated integration tests."),
            DocumentBlock(kind="bulleted_list_item", text="Improved deployment safety."),
            DocumentBlock(kind="bulleted_list_item", text="Partnered on accessible workflows."),
            DocumentBlock(kind="heading_2", text="Education"),
            DocumentBlock(kind="paragraph", text="Example University"),
            DocumentBlock(kind="bulleted_list_item", text="B.S. Computer Science"),
        ),
    )


def master_resume_with_duplicate_role_headings() -> ResumeDocument:
    return ResumeDocument(
        record=ResumeRecord(
            id="master-resume",
            url="https://notion.test/master-resume",
            name="Master Resume",
        ),
        blocks=(
            DocumentBlock(kind="heading_1", text="Candidate Name"),
            DocumentBlock(kind="paragraph", text="Boston | candidate@example.test"),
            DocumentBlock(kind="heading_2", text="Summary"),
            DocumentBlock(kind="paragraph", text="Original professional summary."),
            DocumentBlock(kind="heading_2", text="Software Engineer, Example Co"),
            DocumentBlock(kind="paragraph", text="2022 - Present"),
            DocumentBlock(kind="bulleted_list_item", text="Built reliable Python APIs."),
            DocumentBlock(kind="bulleted_list_item", text="Designed observable services."),
            DocumentBlock(kind="bulleted_list_item", text="Automated integration tests."),
            DocumentBlock(kind="bulleted_list_item", text="Improved deployment safety."),
            DocumentBlock(kind="bulleted_list_item", text="Partnered on accessible workflows."),
            DocumentBlock(kind="heading_2", text="Software Engineer, Example Co"),
            DocumentBlock(kind="paragraph", text="2019 - 2022"),
            DocumentBlock(kind="bulleted_list_item", text="Migrated legacy Python services."),
            DocumentBlock(kind="bulleted_list_item", text="Documented service ownership."),
            DocumentBlock(kind="bulleted_list_item", text="Reviewed API changes."),
            DocumentBlock(kind="bulleted_list_item", text="Maintained release tooling."),
            DocumentBlock(kind="bulleted_list_item", text="Supported incident response."),
        ),
    )


def test_resume_builder_creates_one_evidence_grounded_document_for_notion_and_pdf():
    requirements = {
        "requirements": [
            {
                "id": "req-1",
                "text": "Build reliable Python services",
                "type": "responsibility",
                "category": "Backend",
                "importance": "required",
                "evidence": "reliable Python services",
            }
        ]
    }
    generated = {
        "resume": {
            "summary": "Platform engineer who builds reliable Python services.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        },
                        {
                            "text": "Designed observable services.",
                            "evidenceIds": ["master-resume:block-8"],
                            "requirementIds": [],
                        },
                        {
                            "text": "Automated integration tests.",
                            "evidenceIds": ["master-resume:block-9"],
                            "requirementIds": [],
                        },
                        {
                            "text": "Improved deployment safety.",
                            "evidenceIds": ["master-resume:block-10"],
                            "requirementIds": [],
                        },
                        {
                            "text": "Partnered on accessible workflows.",
                            "evidenceIds": ["master-resume:block-11"],
                            "requirementIds": [],
                        },
                    ],
                }
            ],
        }
    }
    chat = RecordedChatModel([json.dumps(requirements), json.dumps(generated)])
    builder = recorded_resume_builder(chat)

    bundle = asyncio.run(
        builder.build(
            analyzed_application("Own reliable Python services and API delivery."),
            master_resume(),
        )
    )

    assert DocumentBlock(kind="paragraph", text="Example University") in bundle.resume
    assert DocumentBlock(kind="bulleted_list_item", text="B.S. Computer Science") in bundle.resume
    assert bundle.resume_document == bundle.resume
    assert bundle.note[0].text == "Resume Fit Analysis"
    assert [block.text for block in bundle.note[:5]] == [
        "Resume Fit Analysis",
        "Summary",
        "Evidence-grounded comparison for Platform Engineer at Example.",
        "Fit Score",
        "100% using matching-v1.",
    ]
    assert any("req-1" in block.text for block in bundle.note)
    assert any(block.text == "Category Coverage" for block in bundle.note)
    assert any(block.text == "Final Claim Traces" for block in bundle.note)
    assert len(chat.messages) == 2
    assert "BEGIN_MERIDA_JOB_CONTENT_" in chat.messages[0][1][1]
    assert "```json" in chat.messages[1][1][1]
    assert "'sourceSection'" not in chat.messages[1][1][1]


def test_resume_graph_repairs_once_then_completes_roles_from_same_role_evidence():
    requirements = {
        "requirements": [
            {
                "id": "req-1",
                "text": "Build reliable Python services",
                "type": "responsibility",
                "category": "Backend",
                "importance": "required",
                "evidence": "reliable Python services",
            }
        ]
    }
    incomplete = {
        "resume": {
            "summary": "Platform engineer who builds reliable Python services.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }
                    ],
                }
            ],
        }
    }
    chat = RecordedChatModel(
        [json.dumps(requirements), json.dumps(incomplete), json.dumps(incomplete)]
    )
    builder = recorded_resume_builder(chat)

    bundle = asyncio.run(
        builder.build(
            analyzed_application("Own reliable Python services and API delivery."),
            master_resume(),
        )
    )

    role_heading_index = next(
        index
        for index, block in enumerate(bundle.resume)
        if block.text == "Software Engineer, Example Co"
    )
    role_bullets = []
    for block in bundle.resume[role_heading_index + 1 :]:
        if block.kind.startswith("heading_"):
            break
        if block.kind == "bulleted_list_item":
            role_bullets.append(block.text)
    assert len(role_bullets) == 5
    assert len(chat.messages) == 3
    assert "role_bullet_count" in chat.messages[2][-1][1]


def test_resume_graph_deduplicates_roles_before_deterministic_completion():
    requirements = {
        "requirements": [
            {
                "id": "req-1",
                "text": "Build reliable Python services",
                "type": "responsibility",
                "category": "Backend",
                "importance": "required",
                "evidence": "reliable Python services",
            }
        ]
    }
    duplicate_roles = {
        "resume": {
            "summary": "Platform engineer who builds reliable Python services.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }
                    ],
                },
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Designed observable services.",
                            "evidenceIds": ["master-resume:block-8"],
                            "requirementIds": [],
                        }
                    ],
                },
            ],
        }
    }
    chat = RecordedChatModel(
        [json.dumps(requirements), json.dumps(duplicate_roles), json.dumps(duplicate_roles)]
    )

    bundle = asyncio.run(
        recorded_resume_builder(chat).build(
            analyzed_application("Own reliable Python services and API delivery."),
            master_resume(),
        )
    )

    role_bullets = [
        block.text
        for block in bundle.resume
        if block.kind == "bulleted_list_item"
    ]
    assert len(role_bullets) >= 5
    assert "Built reliable Python APIs." in role_bullets


def test_resume_graph_preserves_distinct_roles_with_the_same_heading():
    requirements = {
        "requirements": [
            {
                "id": "req-1",
                "text": "Build reliable Python services",
                "type": "responsibility",
                "category": "Backend",
                "importance": "required",
                "evidence": "reliable Python services",
            }
        ]
    }
    incomplete = {
        "resume": {
            "summary": "Platform engineer who builds reliable Python services.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }
                    ],
                }
            ],
        }
    }
    chat = RecordedChatModel(
        [json.dumps(requirements), json.dumps(incomplete), json.dumps(incomplete)]
    )

    bundle = asyncio.run(
        recorded_resume_builder(chat).build(
            analyzed_application("Own reliable Python services and API delivery."),
            master_resume_with_duplicate_role_headings(),
        )
    )

    role_heading_indexes = [
        index
        for index, block in enumerate(bundle.resume)
        if block.text == "Software Engineer, Example Co"
    ]
    assert len(role_heading_indexes) == 2
    assert any(block.text == "Migrated legacy Python services." for block in bundle.resume)


def test_resume_graph_removes_invented_metrics_and_ownership_after_one_repair():
    requirements = {
        "requirements": [
            {
                "id": "req-1",
                "text": "Build reliable Python services",
                "type": "responsibility",
                "category": "Backend",
                "importance": "required",
                "evidence": "reliable Python services",
            }
        ]
    }
    invented = {
        "resume": {
            "summary": "Platform engineer who builds reliable Python services.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [
                        {
                            "text": "Led 50 engineers building reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }
                    ],
                }
            ],
        }
    }
    chat = RecordedChatModel(
        [json.dumps(requirements), json.dumps(invented), json.dumps(invented)]
    )
    builder = recorded_resume_builder(chat)

    bundle = asyncio.run(
        builder.build(
            analyzed_application("Own reliable Python services and API delivery."),
            master_resume(),
        )
    )

    rendered = " ".join(block.text for block in bundle.resume)
    assert "50 engineers" not in rendered
    assert "Led 50" not in rendered
    assert "Built reliable Python APIs." in rendered


def test_resume_graph_removes_cross_role_claims_and_preserves_every_role():
    source = master_resume()
    two_role_master = ResumeDocument(
        record=source.record,
        blocks=(
            *source.blocks,
            DocumentBlock(kind="heading_2", text="Engineering Manager, Other Co"),
            DocumentBlock(kind="paragraph", text="2020 - 2022"),
            DocumentBlock(kind="bulleted_list_item", text="Mentored engineers."),
            DocumentBlock(kind="bulleted_list_item", text="Planned team delivery."),
            DocumentBlock(kind="bulleted_list_item", text="Improved hiring systems."),
            DocumentBlock(kind="bulleted_list_item", text="Coordinated releases."),
            DocumentBlock(kind="bulleted_list_item", text="Supported team growth."),
        ),
    )
    requirements = {
        "requirements": [{
            "id": "req-1", "text": "Build reliable Python services",
            "type": "responsibility", "category": "Backend",
            "importance": "required", "evidence": "reliable Python services",
        }]
    }
    cross_role = {
        "resume": {
            "summary": "Original professional summary.",
            "roles": [
                {
                    "sourceSection": "Software Engineer, Example Co",
                    "bullets": [{
                        "text": "Invented a cross-role management claim.",
                        "evidenceIds": ["master-resume:block-17"],
                        "requirementIds": [],
                    }],
                },
                {
                    "sourceSection": "Engineering Manager, Other Co",
                    "bullets": [{
                        "text": "Mentored engineers.",
                        "evidenceIds": ["master-resume:block-17"],
                        "requirementIds": [],
                    }],
                },
            ],
        }
    }
    chat = RecordedChatModel(
        [json.dumps(requirements), json.dumps(cross_role), json.dumps(cross_role)]
    )

    bundle = asyncio.run(
        recorded_resume_builder(chat).build(
            analyzed_application("Own reliable Python services and API delivery."),
            two_role_master,
        )
    )

    rendered = " ".join(block.text for block in bundle.resume)
    assert "Invented a cross-role management claim." not in rendered
    for heading in (
        "Software Engineer, Example Co",
        "Engineering Manager, Other Co",
    ):
        start = next(i for i, block in enumerate(bundle.resume) if block.text == heading)
        bullets = []
        for block in bundle.resume[start + 1 :]:
            if block.kind.startswith("heading_"):
                break
            if block.kind == "bulleted_list_item":
                bullets.append(block.text)
        assert len(bullets) >= 5


@pytest.mark.parametrize(
    "claim",
    [
        "Mentored a team that built reliable Python APIs and designed observable services for customers.",
        "Spearheaded a team that built reliable Python APIs and designed observable services for customers.",
        "Built reliable Python APIs and designed observable services as engineering manager.",
        "Built reliable Python APIs and designed observable services using kubernetes.",
        "Built reliable Python APIs and designed observable services at google.",
    ],
)
def test_claim_validation_rejects_novel_actions_titles_tools_and_employers(claim):
    evidence = (
        EvidenceItem(
            id="evidence-1",
            text="Built reliable Python APIs and designed observable services for customers.",
            source_section="Engineer, Example",
        ),
    )

    assert _claim_supported(claim, evidence, EvidenceMatchingEngine()) is False


def test_fit_scoring_uses_required_importance_before_requirement_type():
    assert MATCHING_V1.weight_for(
        SimpleNamespace(importance="required", type="responsibility")
    ) == 1.5
    assert MATCHING_V1.weight_for(
        SimpleNamespace(importance="required", type="preferred skill")
    ) == 1.5


def test_resume_builder_blocks_when_required_job_evidence_has_no_resume_support():
    chat = RecordedChatModel(
        [
            json.dumps(
                {
                    "requirements": [
                        {
                            "id": "req-1",
                            "text": "Administer Kubernetes clusters",
                            "type": "required skill",
                            "category": "Cloud",
                            "importance": "required",
                            "evidence": "Kubernetes clusters",
                        }
                    ]
                }
            )
        ]
    )
    builder = recorded_resume_builder(chat)

    with pytest.raises(ResumeEvidenceError, match="Insufficient Master Resume evidence"):
        asyncio.run(
            builder.build(
                analyzed_application("You must administer Kubernetes clusters."),
                master_resume(),
            )
        )

    assert len(chat.messages) == 1


def test_product_composition_enables_real_resume_creation_when_configured(tmp_path):
    settings = Settings(
        capture_token="test-capture-token",
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )

    with TestClient(
        create_app(settings, workspace=FakeWorkspace(tmp_path / "state.json"))
    ) as client:
        health = client.get("/api/v1/health/resumes").json()

    assert health["status"] == "ready"


def test_resume_health_checks_general_master_readiness_not_application_sufficiency():
    document = ResumeDocument(
        record=master_resume().record,
        blocks=(
            DocumentBlock(kind="heading_2", text="Engineer, Example"),
            DocumentBlock(kind="paragraph", text="2024 - Present"),
            DocumentBlock(kind="bulleted_list_item", text="Built APIs."),
        ),
    )

    validate_master_resume_readiness(document)
    with pytest.raises(ResumeEvidenceError, match="at least five"):
        validate_master_resume_structure(document)
