import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from merida_api.features.applications.workspace import ApplicationRecord
from merida_api.core.settings import Settings
from merida_api.features.applications.analysis_model import DeepSeekApplicationAnalysisModel
from merida_api.integrations.deepseek import DeepSeekJsonClient
from merida_api.integrations.deepseek import DeepSeekProviderError
from merida_api.matching import SCORING_POLICY_VERSION
from merida_api.matching import EvidenceItem, EvidenceMatchingEngine
from merida_api.features.applications.workspace import SkillSignal
from fakes.app import create_test_app
from fakes.workspace import FakeWorkspace


class RecordedChatModel:
    def __init__(self, responses: list[str | Exception]):
        self.responses = list(responses)
        self.messages: list[list[tuple[str, str]]] = []

    async def ainvoke(self, messages: list[tuple[str, str]]):
        self.messages.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return type("Message", (), {"content": response})()


class ProviderFailure(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"private provider error {status_code}")
        self.status_code = status_code


def application(job_content: str) -> ApplicationRecord:
    from datetime import date

    return ApplicationRecord(
        id="application-1",
        url="https://notion.test/application-1",
        company_name="Example",
        role="Platform Engineer",
        job_url="https://example.test/jobs/1",
        captured_url=None,
        location=None,
        date_found=date(2026, 7, 11),
        application_status="To Apply",
        analyzed=False,
        match_score=None,
        job_content=job_content,
    )


def test_deepseek_analysis_returns_validated_evidence_without_model_score():
    chat = RecordedChatModel(
        [
            json.dumps(
                {
                    "summary": [
                        "The role builds reliable platform services.",
                        "Python and PostgreSQL are explicit requirements.",
                        "Automated testing supports safe delivery.",
                    ],
                    "skillSignals": [
                        {
                            "name": "Python",
                            "category": "programming_language",
                            "importance": "required",
                            "evidence": "Python",
                        },
                        {
                            "name": "PostgreSQL",
                            "category": "database",
                            "importance": "preferred",
                            "evidence": "PostgreSQL",
                        },
                    ],
                }
            )
        ]
    )
    model = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat))

    result = asyncio.run(
        model.analyze(
            application(
                "Build reliable Python platform services with PostgreSQL and automated testing."
            )
        )
    )

    assert result.summary == (
        "The role builds reliable platform services.",
        "Python and PostgreSQL are explicit requirements.",
        "Automated testing supports safe delivery.",
    )
    assert [(signal.name, signal.evidence) for signal in result.skill_signals] == [
        ("Python", "Python"),
        ("PostgreSQL", "PostgreSQL"),
    ]
    assert all("matchScore" not in message for _, message in chat.messages[0])
    assert "return json" in chat.messages[0][1][1].lower()
    assert "BEGIN_MERIDA_JOB_CONTENT_" in chat.messages[0][1][1]


def test_matching_calculates_score_from_master_resume_evidence():
    matcher = EvidenceMatchingEngine()
    signals = (
        SkillSignal(
            name="Python",
            category="programming_language",
            importance="required",
            evidence="Python",
        ),
        SkillSignal(
            name="PostgreSQL",
            category="database",
            importance="preferred",
            evidence="PostgreSQL",
        ),
    )
    evidence = (
        EvidenceItem(
            id="role-1-bullet-1",
            text="Built Python APIs for production services.",
            source_section="Software Engineer",
        ),
    )

    result = matcher.score(signals, evidence)

    assert result.score == 65
    assert result.scoring_policy == SCORING_POLICY_VERSION
    assert [match.strength for match in result.matches] == [
        "direct evidence",
        "no evidence",
    ]


def test_deepseek_analysis_repairs_invalid_structured_output_once():
    chat = RecordedChatModel(
        [
            "not-json",
            json.dumps(
                {
                    "summary": ["One.", "Two.", "Three."],
                    "skillSignals": [
                        {
                            "name": "Python",
                            "category": "programming_language",
                            "importance": "required",
                            "evidence": "Python",
                        }
                    ],
                }
            ),
        ]
    )

    result = asyncio.run(
        DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat)).analyze(
            application("Build production services with Python.")
        )
    )

    assert result.skill_signals[0].name == "Python"
    assert len(chat.messages) == 2
    assert "invalid_json" in chat.messages[1][-1][1]


def test_deepseek_analysis_rejects_a_model_owned_match_score_then_repairs():
    invalid = {
        "summary": ["One.", "Two.", "Three."],
        "skillSignals": [
            {
                "name": "Python",
                "category": "programming_language",
                "importance": "required",
                "evidence": "Python",
            }
        ],
        "matchScore": 100,
    }
    valid = {key: value for key, value in invalid.items() if key != "matchScore"}
    chat = RecordedChatModel([json.dumps(invalid), json.dumps(valid)])

    result = asyncio.run(
        DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat)).analyze(
            application("Build production services with Python.")
        )
    )

    assert result.skill_signals[0].name == "Python"
    assert "invalid_schema" in chat.messages[1][-1][1]


def test_deepseek_transport_retries_only_retryable_provider_failures():
    sleeps = []

    async def record_sleep(delay: float):
        sleeps.append(delay)

    valid = json.dumps(
        {
            "summary": ["One.", "Two.", "Three."],
            "skillSignals": [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "importance": "required",
                    "evidence": "Python",
                }
            ],
        }
    )
    retrying_chat = RecordedChatModel([ProviderFailure(429), valid])
    model = DeepSeekApplicationAnalysisModel(
        DeepSeekJsonClient(retrying_chat, sleep=record_sleep, jitter=lambda: 0)
    )

    asyncio.run(model.analyze(application("Build Python services.")))

    assert sleeps == [0.25]
    assert len(retrying_chat.messages) == 2

    rejected_chat = RecordedChatModel([ProviderFailure(401)])
    rejected = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(rejected_chat))
    with pytest.raises(DeepSeekProviderError) as error:
        asyncio.run(rejected.analyze(application("Build Python services.")))
    assert error.value.code == "authentication_failed"
    assert "private provider error" not in str(error.value)
    assert len(rejected_chat.messages) == 1


def test_asgi_analysis_uses_validated_deepseek_output_and_local_matching(tmp_path):
    class AnalysisWorkspace(FakeWorkspace):
        async def load_analysis_evidence(self):
            return (
                EvidenceItem(
                    id="master-role-1",
                    text="Built accessible React product interfaces.",
                    source_section="Software Engineer",
                ),
            )

    chat = RecordedChatModel(
        [
            json.dumps(
                {
                    "summary": [
                        "The role builds accessible interfaces.",
                        "React is an explicit requirement.",
                        "Automated testing supports delivery.",
                    ],
                    "skillSignals": [
                        {
                            "name": "React",
                            "category": "framework_library",
                            "importance": "required",
                            "evidence": "React",
                        }
                    ],
                }
            )
        ]
    )
    settings = Settings(
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = AnalysisWorkspace(tmp_path / "state.json")
    analysis_model = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat))

    with TestClient(
        create_test_app(
            settings,
            workspace=workspace,
            analysis_model=analysis_model,
        )
    ) as client:
        response = client.post(
            "/api/v1/applications/analysis/run", json={"limit": 1}
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["result"] == "analyzed"
    assert response.json()["items"][0]["matchScore"] == 100


@pytest.mark.parametrize(
    ("invalid_payload", "repair_code"),
    [
        (
            {
                "summary": ["One sentence. Another sentence.", "Two.", "Three."],
                "skillSignals": [
                    {
                        "name": "Python",
                        "category": "programming_language",
                        "importance": "required",
                        "evidence": "Python",
                    }
                ],
            },
            "invalid_summary",
        ),
        (
            {
                "summary": ["One.", "Two.", "Three."],
                "skillSignals": [
                    {
                        "name": "Strong communication skills",
                        "category": "other",
                        "importance": "signal",
                        "evidence": "strong communication skills",
                    }
                ],
            },
            "no_concrete_signals",
        ),
    ],
)
def test_analysis_repairs_invalid_summary_and_generic_trait_variants(
    invalid_payload, repair_code
):
    valid = {
        "summary": ["One.", "Two.", "Three."],
        "skillSignals": [
            {
                "name": "Python",
                "category": "programming_language",
                "importance": "required",
                "evidence": "Python",
            }
        ],
    }
    chat = RecordedChatModel([json.dumps(invalid_payload), json.dumps(valid)])
    content = "Build Python services with strong communication skills."

    result = asyncio.run(
        DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat)).analyze(
            application(content)
        )
    )

    assert result.skill_signals[0].name == "Python"
    assert repair_code in chat.messages[1][-1][1]
