import asyncio
import json

from merida_api.features.applications.workspace import ApplicationRecord
from merida_api.integrations.deepseek_analysis import DeepSeekApplicationAnalysisModel
from merida_api.matching import EvidenceItem, EvidenceMatchingEngine
from merida_api.features.applications.workspace import SkillSignal


class RecordedChatModel:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.messages: list[list[tuple[str, str]]] = []

    async def ainvoke(self, messages: list[tuple[str, str]]):
        self.messages.append(messages)
        return type("Message", (), {"content": self.responses.pop(0)})()


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
                    "matchScore": 100,
                }
            )
        ]
    )
    model = DeepSeekApplicationAnalysisModel(chat)

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
        DeepSeekApplicationAnalysisModel(chat).analyze(
            application("Build production services with Python.")
        )
    )

    assert result.skill_signals[0].name == "Python"
    assert len(chat.messages) == 2
    assert "invalid_json" in chat.messages[1][-1][1]
