import asyncio
import json
import pytest
import httpx
import sys
import time
import types
from pathlib import Path
from fastapi.testclient import TestClient

from dataclasses import replace

from merida_api.features.applications.workspace import (
    AnalysisCallEvidence,
    ApplicationAnalysisDocument,
    ApplicationRecord,
)
from merida_api.core.settings import Settings
from merida_api.app import create_app
from merida_api.features.applications.analysis_graph import ApplicationAnalysisGraph
from merida_api.features.applications.analysis_model import (
    AnalysisModelOutputError,
    DeepSeekApplicationAnalysisModel,
    create_deepseek_analysis_model,
    validate_analysis_payload,
)
from merida_api.integrations.deepseek import DeepSeekJsonClient
from merida_api.integrations.deepseek import DeepSeekProviderError
from merida_api.integrations.deepseek import create_deepseek_json_client
from merida_api.matching import MATCHING_V1, SCORING_POLICY_VERSION
from merida_api.matching import EvidenceItem, EvidenceMatchingEngine
from merida_api.features.applications.workspace import SkillSignal
from fakes.app import create_test_app
from fakes.models import FakeResumeDocumentBuilder
from fakes.models import FakeApplicationAnalysisModel
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

    def render_request(self, messages: list[tuple[str, str]]) -> bytes:
        return json.dumps(
            {
                "model": "deepseek-v4-flash",
                "messages": [
                    {
                        "role": "system" if role == "system" else "user",
                        "content": content,
                    }
                    for role, content in messages
                ],
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
                "stream": False,
                "reasoning_effort": "high",
                "thinking": {"type": "enabled"},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()

    async def ainvoke_prepared(self, rendered_request: bytes):
        document = json.loads(rendered_request)
        messages = [
            (
                "system" if message["role"] == "system" else "human",
                message["content"],
            )
            for message in document["messages"]
        ]
        response = await self.ainvoke(messages)
        response.response_metadata = {
            "finish_reason": "stop",
            "model_name": "deepseek-v4-flash",
            "request_id": f"recorded-{len(self.messages)}",
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
                "prompt_cache_hit_tokens": 0,
            },
        }
        response.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
        }
        return response


class ProviderFailure(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"private provider error {status_code}")
        self.status_code = status_code


def test_deepseek_chat_adapter_uses_only_supported_json_mode(monkeypatch):
    captured = {}

    class FakeChatDeepSeek:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def bind(self, **kwargs):
            captured["bind"] = kwargs
            return self

        async def ainvoke(self, _messages):
            return type("Message", (), {"content": '{"ok": true}'})()

    module = types.ModuleType("langchain_deepseek")
    module.ChatDeepSeek = FakeChatDeepSeek
    monkeypatch.setitem(sys.modules, "langchain_deepseek", module)

    response = asyncio.run(
        create_deepseek_json_client(
            api_key="test-key", model="deepseek-v4-flash", max_tokens=32
        ).request_json([("human", "Return JSON.")])
    )

    assert response == {"ok": True}
    assert captured["init"]["max_retries"] == 0
    assert captured["bind"] == {"response_format": {"type": "json_object"}}


def test_application_analysis_explicitly_uses_bounded_high_effort_thinking(
    monkeypatch,
):
    captured = {}

    class FakeChatDeepSeek:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def bind(self, **kwargs):
            captured["bind"] = kwargs
            return self

        async def ainvoke(self, messages):
            captured["messages"] = messages
            return type(
                "Message",
                (),
                {
                    "content": json.dumps(
                        {
                            "summary": ["One.", "Two.", "Three."],
                            "skillSignals": [],
                        }
                    )
                },
            )()

    module = types.ModuleType("langchain_deepseek")
    module.ChatDeepSeek = FakeChatDeepSeek
    monkeypatch.setitem(sys.modules, "langchain_deepseek", module)

    model = create_deepseek_analysis_model(
        api_key="test-key", model="deepseek-v4-flash"
    )
    asyncio.run(model.generate(application("Build Python services.")))

    assert captured["init"] == {
        "api_key": "test-key",
        "model": "deepseek-v4-flash",
        "max_tokens": 8000,
        "timeout": httpx.Timeout(
            connect=10,
            read=120,
            write=120,
            pool=10,
        ),
        "max_retries": 0,
        "reasoning_effort": "high",
        "streaming": False,
        "extra_body": {"thinking": {"type": "enabled"}},
    }
    assert captured["bind"] == {"response_format": {"type": "json_object"}}
    prompt = captured["messages"][1][1]
    assert "exactly three summary sentences" in prompt
    assert "between three and ten candidate Skill Signals" in prompt


def test_prepared_analysis_sends_the_exact_authorized_bytes(monkeypatch):
    sent = {}

    class Response:
        headers = {"x-request-id": "request-1"}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "request-1",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": ["One.", "Two.", "Three."],
                                    "skillSignals": [],
                                }
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                },
            }

    class Client:
        def __init__(self, *, timeout):
            sent["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, endpoint, *, content, headers):
            sent.update(endpoint=endpoint, content=content, headers=headers)
            return Response()

    monkeypatch.setattr(
        "merida_api.integrations.deepseek.httpx.AsyncClient", Client
    )
    model = create_deepseek_analysis_model(
        api_key="test-key", model="deepseek-v4-flash"
    )
    prepared = model.prepare(application("Build Python services."))
    response = asyncio.run(model.transmit(prepared))

    envelope = json.loads(prepared.rendered_request)
    assert sent["content"] is prepared.rendered_request
    assert sent["endpoint"] == prepared.endpoint
    assert envelope["model"] == prepared.model
    assert envelope["max_tokens"] == 8000
    assert envelope["stream"] is False
    assert envelope["reasoning_effort"] == "high"
    assert envelope["thinking"] == {"type": "enabled"}
    assert "temperature" not in envelope
    assert response.call_evidence is not None
    assert response.call_evidence.request_id == "request-1"
    assert response.call_evidence.model_id is None


def test_recorded_analysis_call_captures_only_safe_settlement_evidence():
    private_reasoning = "PRIVATE_REASONING_MUST_NOT_BE_RECORDED"

    class EvidenceChat:
        async def ainvoke(self, _messages):
            return type(
                "Message",
                (),
                {
                    "id": "request-123",
                    "content": json.dumps(
                        {
                            "summary": ["One.", "Two.", "Three."],
                            "skillSignals": [],
                        }
                    ),
                    "response_metadata": {
                        "finish_reason": "stop",
                        "model_name": "deepseek-v4-flash-20260801",
                        "token_usage": {
                            "prompt_tokens": 321,
                            "completion_tokens": 654,
                            "total_tokens": 975,
                            "prompt_cache_hit_tokens": 20,
                            "prompt_cache_miss_tokens": 301,
                            "completion_tokens_details": {
                                "reasoning_tokens": 600
                            },
                        },
                    },
                    "additional_kwargs": {
                        "reasoning_content": private_reasoning,
                    },
                    "reasoning_content": private_reasoning,
                },
            )()

    model = DeepSeekApplicationAnalysisModel(
        DeepSeekJsonClient(
            EvidenceChat(),
            requested_model_id="deepseek-v4-flash",
        )
    )

    response = asyncio.run(model.generate(application("Build Python services.")))

    assert response.call_evidence == AnalysisCallEvidence(
        transmission_state="sent",
        finish_reason="stop",
        model_id="deepseek-v4-flash-20260801",
        request_id="request-123",
        input_tokens=321,
        output_tokens=654,
        total_tokens=975,
        cache_hit_input_tokens=20,
        cache_miss_input_tokens=301,
        reasoning_output_tokens=600,
    )
    assert private_reasoning not in repr(response)


def test_response_model_identity_is_never_synthesized_from_the_requested_model():
    class MissingModelChat:
        async def ainvoke(self, _messages):
            return type(
                "Message",
                (),
                {
                    "id": "request-without-model",
                    "content": '{"summary":["One.","Two.","Three."],"skillSignals":[]}',
                    "response_metadata": {
                        "finish_reason": "stop",
                        "token_usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 20,
                            "total_tokens": 30,
                        },
                    },
                    "usage_metadata": {},
                },
            )()

    response = asyncio.run(
        DeepSeekJsonClient(
            MissingModelChat(),
            requested_model_id="deepseek-v4-flash",
        ).request_json_once([("human", "Return JSON.")])
    )

    assert response.evidence.model_id is None


def test_zero_optional_usage_counts_remain_available_for_consistency_checks():
    class ZeroDetailsChat:
        async def ainvoke(self, _messages):
            return type(
                "Message",
                (),
                {
                    "id": "request-with-zero-details",
                    "content": "{}",
                    "response_metadata": {
                        "model_name": "deepseek-v4-flash",
                        "token_usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 20,
                            "total_tokens": 30,
                            "prompt_cache_hit_tokens": 0,
                            "prompt_cache_miss_tokens": 0,
                            "completion_tokens_details": {
                                "reasoning_tokens": 0,
                            },
                        },
                    },
                    "usage_metadata": {},
                },
            )()

    response = asyncio.run(
        DeepSeekJsonClient(
            ZeroDetailsChat(),
            requested_model_id="deepseek-v4-flash",
        ).request_json_once([("human", "Return JSON.")])
    )

    assert response.evidence.cache_hit_input_tokens == 0
    assert response.evidence.cache_miss_input_tokens == 0
    assert response.evidence.reasoning_output_tokens == 0


class AnalysisStore:
    def __init__(self, record: ApplicationRecord):
        self.record = record
        self.document = None
        self.final_score = None

    async def load_analysis_input(self, application_id: str):
        assert application_id == self.record.id
        return self.record

    async def load_analysis_evidence(self):
        return (
            EvidenceItem(
                id="master-evidence-1",
                text="Built Python and React product systems.",
                source_section="Software Engineer",
            ),
        )

    async def append_application_analysis(self, application_id, document):
        assert application_id == self.record.id
        self.document = document

    async def finalize_application_analysis(self, application_id, *, match_score):
        assert application_id == self.record.id
        self.final_score = match_score


def run_graph(chat: RecordedChatModel, record: ApplicationRecord):
    store = AnalysisStore(record)
    graph = ApplicationAnalysisGraph(
        store,
        DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat)),
        EvidenceMatchingEngine(),
    )
    outcome = asyncio.run(graph.run(record, batch_run_id="batch-1"))
    return outcome, store


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
                        {
                            "name": "Automated testing",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated testing",
                        },
                    ],
                }
            )
        ]
    )
    model = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat))

    record = application(
        "Build reliable Python platform services with PostgreSQL and automated testing."
    )
    response = asyncio.run(model.generate(record))
    result = validate_analysis_payload(response.payload or {}, record.job_content or "")

    assert result.summary == (
        "The role builds reliable platform services.",
        "Python and PostgreSQL are explicit requirements.",
        "Automated testing supports safe delivery.",
    )
    assert [(signal.name, signal.evidence) for signal in result.skill_signals] == [
        ("Python", "Python"),
        ("PostgreSQL", "PostgreSQL"),
        ("Automated testing", "automated testing"),
    ]
    assert all("matchScore" not in message for _, message in chat.messages[0])
    assert "return json" in chat.messages[0][1][1].lower()
    assert "BEGIN_MERIDA_JOB_CONTENT_" in chat.messages[0][1][1]


def test_matching_calculates_score_from_master_resume_evidence():
    matcher = EvidenceMatchingEngine()
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/matching.v1.json").read_text()
    )
    case = fixture["cases"][0]
    signals = tuple(SkillSignal(**signal) for signal in case["signals"])
    evidence = tuple(
        EvidenceItem(
            id=item["id"],
            text=item["text"],
            source_section=item["sourceSection"],
        )
        for item in case["evidenceItems"]
    )

    result = matcher.match(signals, evidence, MATCHING_V1)

    assert fixture["scoringPolicy"] == SCORING_POLICY_VERSION
    assert result.score == case["expected"]["score"]
    assert result.scoring_policy == SCORING_POLICY_VERSION
    assert [match.strength for match in result.matches] == case["expected"][
        "strengths"
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
                        },
                        {
                            "name": "PostgreSQL",
                            "category": "database",
                            "importance": "preferred",
                            "evidence": "PostgreSQL",
                        },
                        {
                            "name": "Automated testing",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated tests",
                        },
                    ],
                }
            ),
        ]
    )

    result, _store = run_graph(
        chat,
        application(
            "Build production services with Python, PostgreSQL, and automated tests."
        ),
    )

    assert result.result == "analyzed"
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
            },
            {
                "name": "PostgreSQL",
                "category": "database",
                "importance": "preferred",
                "evidence": "PostgreSQL",
            },
            {
                "name": "Automated testing",
                "category": "testing_quality",
                "importance": "signal",
                "evidence": "automated tests",
            },
        ],
        "matchScore": 100,
    }
    valid = {key: value for key, value in invalid.items() if key != "matchScore"}
    chat = RecordedChatModel([json.dumps(invalid), json.dumps(valid)])

    result, _store = run_graph(
        chat,
        application(
            "Build production services with Python, PostgreSQL, and automated tests."
        ),
    )

    assert result.result == "analyzed"
    assert "invalid_schema" in chat.messages[1][-1][1]


def test_analysis_transport_exposes_retryability_without_retrying_itself():
    sleeps = []

    async def record_sleep(delay: float):
        sleeps.append(delay)

    retrying_chat = RecordedChatModel([ProviderFailure(429)])
    model = DeepSeekApplicationAnalysisModel(
        DeepSeekJsonClient(retrying_chat, sleep=record_sleep, jitter=lambda: 0)
    )

    with pytest.raises(DeepSeekProviderError) as retryable:
        asyncio.run(model.generate(application("Build Python services.")))

    assert retryable.value.code == "rate_limited"
    assert retryable.value.retryable is True
    assert sleeps == []
    assert len(retrying_chat.messages) == 1

    rejected_chat = RecordedChatModel([ProviderFailure(401)])
    rejected = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(rejected_chat))
    with pytest.raises(DeepSeekProviderError) as error:
        asyncio.run(rejected.generate(application("Build Python services.")))
    assert error.value.code == "authentication_failed"
    assert "private provider error" not in str(error.value)
    assert len(rejected_chat.messages) == 1

    balance_chat = RecordedChatModel([ProviderFailure(402)])
    balance = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(balance_chat))
    with pytest.raises(DeepSeekProviderError) as balance_error:
        asyncio.run(balance.generate(application("Build Python services.")))
    assert balance_error.value.code == "balance_insufficient"
    assert balance_error.value.retryable is False
    assert balance_error.value.evidence.transmission_state == "sent"
    assert len(balance_chat.messages) == 1


def test_analysis_transport_normalizes_timeout_for_the_owner_recovery_loop():
    sleeps = []

    async def record_sleep(delay: float):
        sleeps.append(delay)

    timeout = lambda: httpx.ReadTimeout(
        "private timeout", request=httpx.Request("POST", "https://example.test")
    )
    chat = RecordedChatModel([timeout(), timeout(), timeout()])
    model = DeepSeekApplicationAnalysisModel(
        DeepSeekJsonClient(chat, sleep=record_sleep, jitter=lambda: 0)
    )

    with pytest.raises(DeepSeekProviderError) as error:
        asyncio.run(model.generate(application("Build Python services.")))

    assert error.value.code == "transport_unavailable"
    assert error.value.retryable is True
    assert sleeps == []
    assert len(chat.messages) == 1


def test_analysis_shares_three_transmissions_across_transport_and_json_repair():
    valid = json.dumps(
        {
            "summary": ["One.", "Two.", "Three."],
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
                {
                    "name": "Automated testing",
                    "category": "testing_quality",
                    "importance": "signal",
                    "evidence": "automated tests",
                },
            ],
        }
    )
    chat = RecordedChatModel([ProviderFailure(429), "not-json", valid])

    outcome, store = run_graph(
        chat,
        application(
            "Build Python services with PostgreSQL and automated tests."
        ),
    )

    assert outcome.result == "analyzed"
    assert len(chat.messages) == 3
    assert len(outcome.call_evidence) == 3
    assert store.document is not None


def test_analysis_never_makes_a_fourth_transmission_after_mixed_recovery():
    fourth_call_would_complete = json.dumps(
        {
            "summary": ["One.", "Two.", "Three."],
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
                {
                    "name": "Automated testing",
                    "category": "testing_quality",
                    "importance": "signal",
                    "evidence": "automated tests",
                },
            ],
        }
    )
    chat = RecordedChatModel(
        [ProviderFailure(500), ProviderFailure(429), "not-json", fourth_call_would_complete]
    )

    outcome, store = run_graph(
        chat,
        application(
            "Build Python services with PostgreSQL and automated tests."
        ),
    )

    assert outcome.result == "failed"
    assert len(chat.messages) == 3
    assert len(chat.responses) == 1
    assert len(outcome.call_evidence) == 3
    assert store.document is None


def test_proven_pretransmission_failure_does_not_consume_a_call_budget_slot():
    valid = json.dumps(
        {
            "summary": ["One.", "Two.", "Three."],
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
                {
                    "name": "Automated testing",
                    "category": "testing_quality",
                    "importance": "signal",
                    "evidence": "automated tests",
                },
            ],
        }
    )
    connect_timeout = httpx.ConnectTimeout(
        "private connect timeout",
        request=httpx.Request("POST", "https://example.test"),
    )
    chat = RecordedChatModel(
        [connect_timeout, ProviderFailure(500), "not-json", valid]
    )

    outcome, _store = run_graph(
        chat,
        application(
            "Build Python services with PostgreSQL and automated tests."
        ),
    )

    assert outcome.result == "analyzed"
    assert len(chat.messages) == 4
    assert [call.transmission_state for call in outcome.call_evidence] == [
        "not_transmitted",
        "sent",
        "sent",
        "sent",
    ]
    assert sum(call.consumed_transmission for call in outcome.call_evidence) == 3


@pytest.mark.parametrize(
    ("error_factory", "expected_state"),
    [
        (
            lambda: httpx.ConnectTimeout(
                "private connect timeout",
                request=httpx.Request("POST", "https://example.test"),
            ),
            "not_transmitted",
        ),
        (
            lambda: httpx.ReadTimeout(
                "private read timeout",
                request=httpx.Request("POST", "https://example.test"),
            ),
            "indeterminate",
        ),
    ],
)
def test_single_transmission_classifies_timeout_evidence(
    error_factory, expected_state
):
    chat = RecordedChatModel([error_factory()])
    client = DeepSeekJsonClient(
        chat,
        requested_model_id="deepseek-v4-flash",
    )

    with pytest.raises(DeepSeekProviderError) as caught:
        asyncio.run(client.request_json_once([("human", "Return JSON.")]))

    assert caught.value.evidence.transmission_state == expected_state
    assert caught.value.evidence.model_id is None
    assert "private" not in repr(caught.value.evidence)
    assert len(chat.messages) == 1


def test_single_transmission_absolute_deadline_is_indeterminate():
    class StalledChat:
        calls = 0

        async def ainvoke(self, _messages):
            self.calls += 1
            await asyncio.sleep(60)

    chat = StalledChat()
    client = DeepSeekJsonClient(
        chat,
        requested_model_id="deepseek-v4-flash",
        absolute_timeout=0.001,
    )

    with pytest.raises(DeepSeekProviderError) as caught:
        asyncio.run(client.request_json_once([("human", "Return JSON.")]))

    assert caught.value.code == "absolute_deadline_exceeded"
    assert caught.value.evidence.transmission_state == "indeterminate"
    assert chat.calls == 1


def test_length_finish_consumes_a_call_and_never_persists_partial_output():
    class LengthChat(RecordedChatModel):
        async def ainvoke(self, messages):
            self.messages.append(messages)
            self.responses.pop(0)
            return type(
                "Message",
                (),
                {
                    "id": f"request-{len(self.messages)}",
                    "content": '{"summary":["partial',
                    "response_metadata": {
                        "finish_reason": "length",
                        "model_name": "deepseek-v4-flash-20260801",
                    },
                },
            )()

    chat = LengthChat([None, None, None, None])
    outcome, store = run_graph(chat, application("Build Python services."))

    assert outcome.result == "failed"
    assert len(chat.messages) == 3
    assert [call.finish_reason for call in outcome.call_evidence] == [
        "length",
        "length",
        "length",
    ]
    assert store.document is None


def test_asgi_analysis_uses_validated_deepseek_output_and_local_matching(tmp_path):
    class AnalysisWorkspace(FakeWorkspace):
        async def load_analysis_evidence(self):
            return (
                EvidenceItem(
                    id="master-role-1",
                    text=(
                        "Built accessible React product interfaces, REST APIs, "
                        "and automated tests."
                    ),
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
                        },
                        {
                            "name": "REST APIs",
                            "category": "api_integration",
                            "importance": "preferred",
                            "evidence": "REST APIs",
                        },
                        {
                            "name": "Automated testing",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated tests",
                        },
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
    analysis_model = DeepSeekApplicationAnalysisModel(
        DeepSeekJsonClient(chat, requested_model_id="deepseek-v4-flash")
    )

    with TestClient(
        create_test_app(
            settings,
            workspace=workspace,
            analysis_model=analysis_model,
        )
    ) as client:
        response = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "validated-output"},
            json={"target": 1},
        )
        run_id = response.json()["run"]["runId"]
        for _ in range(200):
            run = client.get(
                f"/api/v1/applications/analysis/runs/{run_id}"
            ).json()["run"]
            if run["lifecycle"] == "finished":
                break
            time.sleep(0.005)

    assert response.status_code == 202
    assert run["outcome"] == "target_met"
    stored = asyncio.run(workspace.load_analysis_input("app-northstar"))
    assert stored.analyzed is True
    assert stored.match_score == 94


def test_public_analysis_discards_bad_signals_and_persists_a_prioritized_completion(
    tmp_path, caplog
):
    private_reasoning = "PRIVATE_PROVIDER_REASONING_MUST_NOT_ESCAPE"

    class AnalysisWorkspace(FakeWorkspace):
        async def load_analysis_input(self, application_id):
            record = await super().load_analysis_input(application_id)
            return replace(
                record,
                job_content=(
                    f"{record.job_content} "
                    "The posting also mentions problem solving and leadership."
                ),
            )

        async def load_analysis_evidence(self):
            return (
                EvidenceItem(
                    id="master-react",
                    text="Built accessible React interfaces.",
                    source_section="Software Engineer",
                ),
                EvidenceItem(
                    id="master-api",
                    text="Built REST APIs.",
                    source_section="Software Engineer",
                ),
                EvidenceItem(
                    id="master-tests",
                    text="Created reliable automated tests.",
                    source_section="Software Engineer",
                ),
            )

    class ReasoningChatModel(RecordedChatModel):
        async def ainvoke(self, messages):
            self.messages.append(messages)
            response = self.responses.pop(0)
            return type(
                "Message",
                (),
                {
                    "content": response,
                    "additional_kwargs": {"reasoning_content": private_reasoning},
                    "reasoning_content": private_reasoning,
                },
            )()

    chat = ReasoningChatModel(
        [
            json.dumps(
                {
                    "summary": [
                        "The role builds accessible product interfaces.",
                        "React and REST APIs are explicit requirements.",
                        "Reliable automated tests support delivery.",
                    ],
                    "skillSignals": [
                        {
                            "name": "Automated testing",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated tests",
                        },
                        {
                            "name": "Accessibility",
                            "category": "domain_knowledge",
                            "importance": "preferred",
                            "evidence": "accessible",
                        },
                        {
                            "name": "Strong communication skills",
                            "category": "other",
                            "importance": "signal",
                            "evidence": "interfaces",
                        },
                        {
                            "name": "REST APIs",
                            "category": "api_integration",
                            "importance": "required",
                            "evidence": "REST APIs",
                        },
                        {
                            "name": "React framework",
                            "category": "framework_library",
                            "importance": "preferred",
                            "evidence": "React",
                        },
                        {
                            "name": "React",
                            "category": "framework_library",
                            "importance": "required",
                            "evidence": "React",
                        },
                        {
                            "name": "Kubernetes",
                            "category": "cloud_platform",
                            "importance": "signal",
                            "evidence": "React",
                        },
                        {
                            "name": "Problem solving skills",
                            "category": "other",
                            "importance": "signal",
                            "evidence": "problem solving",
                        },
                        {
                            "name": "Leadership skills",
                            "category": "other",
                            "importance": "signal",
                            "evidence": "leadership",
                        },
                        {
                            "name": "Design systems",
                            "category": "not-a-category",
                            "importance": "signal",
                            "evidence": "design systems",
                        },
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

    with TestClient(
        create_test_app(
            settings,
            workspace=workspace,
            analysis_model=DeepSeekApplicationAnalysisModel(
                DeepSeekJsonClient(
                    chat, requested_model_id="deepseek-v4-flash"
                )
            ),
        )
    ) as client:
        response = client.post(
            "/api/v1/applications/analysis/run",
            headers={"Idempotency-Key": "prioritized-output"},
            json={"target": 1},
        )
        run_id = response.json()["run"]["runId"]
        for _ in range(200):
            run_response = client.get(
                f"/api/v1/applications/analysis/runs/{run_id}"
            )
            run = run_response.json()["run"]
            if run["lifecycle"] == "finished":
                break
            time.sleep(0.005)

    assert response.status_code == 202
    assert run["outcome"] == "target_met"
    assert run["candidates"][0]["state"] == "analyzed"
    assert len(chat.messages) == 1
    stored = asyncio.run(workspace.load_analysis_input("app-northstar"))
    assert stored.analyzed is True
    assert stored.analysis is not None
    assert stored.match_score == 57
    assert stored.analysis.summary == (
        "The role builds accessible product interfaces. "
        "React and REST APIs are explicit requirements. "
        "Reliable automated tests support delivery."
    )
    assert [signal.name for signal in stored.analysis.skill_signals] == [
        "REST APIs",
        "React",
        "Accessibility",
        "Automated testing",
    ]
    assert private_reasoning not in response.text
    assert private_reasoning not in run_response.text
    assert private_reasoning not in repr(stored)
    assert private_reasoning not in caplog.text


def test_signal_evidence_supports_sensible_aliases_while_soft_traits_are_discarded():
    result = validate_analysis_payload(
        {
            "summary": ["One.", "Two.", "Three."],
            "skillSignals": [
                {
                    "name": "REST APIs",
                    "category": "api_integration",
                    "importance": "required",
                    "evidence": "RESTful API development",
                },
                {
                    "name": "PostgreSQL",
                    "category": "database",
                    "importance": "preferred",
                    "evidence": "Postgres",
                },
                {
                    "name": "Automated testing",
                    "category": "testing_quality",
                    "importance": "signal",
                    "evidence": "automated tests",
                },
                {
                    "name": "Problem solving skills",
                    "category": "other",
                    "importance": "signal",
                    "evidence": "problem solving skills",
                },
                {
                    "name": "Leadership skills",
                    "category": "other",
                    "importance": "signal",
                    "evidence": "leadership skills",
                },
                {
                    "name": "Adaptability",
                    "category": "other",
                    "importance": "signal",
                    "evidence": "adaptability",
                },
            ],
        },
        (
            "Own RESTful API development using Postgres and automated tests. "
            "Bring problem solving skills, leadership skills, and adaptability."
        ),
    )

    assert [signal.name for signal in result.skill_signals] == [
        "REST APIs",
        "PostgreSQL",
        "Automated testing",
    ]


def test_signal_evidence_requires_token_boundaries_not_embedded_substrings():
    with pytest.raises(
        AnalysisModelOutputError, match="at least three concrete Skill Signals"
    ):
        validate_analysis_payload(
            {
                "summary": ["One.", "Two.", "Three."],
                "skillSignals": [
                    {
                        "name": "React",
                        "category": "framework_library",
                        "importance": "required",
                        "evidence": "React",
                    },
                    {
                        "name": "Go",
                        "category": "programming_language",
                        "importance": "preferred",
                        "evidence": "Go",
                    },
                    {
                        "name": "Rust",
                        "category": "programming_language",
                        "importance": "signal",
                        "evidence": "Rust",
                    },
                ],
            },
            "Coordinate preaction planning, ongoing delivery, and customer trust.",
        )


def test_signal_evidence_rejects_partially_supported_composite_names():
    with pytest.raises(
        AnalysisModelOutputError, match="at least three concrete Skill Signals"
    ):
        validate_analysis_payload(
            {
                "summary": ["One.", "Two.", "Three."],
                "skillSignals": [
                    {
                        "name": "Python and Kubernetes",
                        "category": "programming_language",
                        "importance": "required",
                        "evidence": "Python",
                    },
                    {
                        "name": "PostgreSQL and Terraform",
                        "category": "database",
                        "importance": "preferred",
                        "evidence": "PostgreSQL",
                    },
                    {
                        "name": "React development",
                        "category": "framework_library",
                        "importance": "signal",
                        "evidence": "software development",
                    },
                ],
            },
            "Python, PostgreSQL, and software development are required.",
        )


def test_base_signal_and_development_descriptor_merge_deterministically():
    result = validate_analysis_payload(
        {
            "summary": ["One.", "Two.", "Three."],
            "skillSignals": [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "importance": "required",
                    "evidence": "Python",
                },
                {
                    "name": "Python development",
                    "category": "programming_language",
                    "importance": "preferred",
                    "evidence": "Python development",
                },
                {
                    "name": "REST APIs",
                    "category": "api_integration",
                    "importance": "required",
                    "evidence": "REST APIs",
                },
                {
                    "name": "REST API development",
                    "category": "api_integration",
                    "importance": "signal",
                    "evidence": "REST API development",
                },
                {
                    "name": "PostgreSQL",
                    "category": "database",
                    "importance": "preferred",
                    "evidence": "PostgreSQL",
                },
                {
                    "name": "Kubernetes",
                    "category": "cloud_platform",
                    "importance": "preferred",
                    "evidence": "Kubernetes",
                },
                {
                    "name": "Kubernetes orchestration",
                    "category": "cloud_platform",
                    "importance": "signal",
                    "evidence": "Kubernetes orchestration",
                },
            ],
        },
        "Use Python, PostgreSQL, and Kubernetes for Python development, REST API development, and Kubernetes orchestration. REST APIs are required.",
    )

    assert [signal.name for signal in result.skill_signals] == [
        "Python",
        "REST APIs",
        "PostgreSQL",
        "Kubernetes",
    ]


def test_analysis_with_fewer_than_three_valid_signals_does_not_complete():
    insufficient = json.dumps(
        {
            "summary": ["One.", "Two.", "Three."],
            "skillSignals": [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "importance": "required",
                    "evidence": "Python",
                },
                {
                    "name": "React",
                    "category": "framework_library",
                    "importance": "preferred",
                    "evidence": "React",
                },
            ],
        }
    )
    chat = RecordedChatModel([insufficient, insufficient])

    outcome, store = run_graph(
        chat, application("Build production services with Python and React.")
    )

    assert outcome.result == "failed"
    assert "insufficient_concrete_signals" in chat.messages[1][-1][1]
    assert store.document is None
    assert store.final_score is None


def test_analysis_persists_only_the_ten_highest_priority_valid_signals():
    candidates = [
        ("Observability", "signal", "Observability"),
        ("Terraform", "preferred", "Terraform"),
        ("React", "required", "React"),
        ("Automated testing", "signal", "Automated testing"),
        ("Python", "required", "Python"),
        ("AWS", "preferred", "AWS"),
        ("Accessibility", "signal", "Accessibility"),
        ("REST APIs", "required", "REST APIs"),
        ("Docker", "preferred", "Docker"),
        ("Continuous integration", "signal", "Continuous integration"),
        ("PostgreSQL", "required", "PostgreSQL"),
        ("Kubernetes", "preferred", "Kubernetes"),
    ]
    chat = RecordedChatModel(
        [
            json.dumps(
                {
                    "summary": ["One.", "Two.", "Three."],
                    "skillSignals": [
                        {
                            "name": name,
                            "category": "other",
                            "importance": importance,
                            "evidence": evidence,
                        }
                        for name, importance, evidence in candidates
                    ],
                }
            )
        ]
    )
    content = "Use " + ", ".join(evidence for _, _, evidence in candidates) + "."

    outcome, store = run_graph(chat, application(content))

    assert outcome.result == "analyzed"
    assert len(chat.messages) == 1
    assert store.document is not None
    assert [signal.name for signal in store.document.skill_signals] == [
        "React",
        "Python",
        "REST APIs",
        "PostgreSQL",
        "Terraform",
        "AWS",
        "Docker",
        "Kubernetes",
        "Observability",
        "Automated testing",
    ]


def test_configured_product_composition_reports_real_analysis_ready(tmp_path):
    settings = Settings(
        notion_token="test-notion-token",
        notion_database_id="applications-database",
        notion_resume_database_id="resumes-database",
        notion_notes_database_id="notes-database",
        deepseek_api_key="test-deepseek-key",
        export_path=tmp_path / "export",
        recovery_journal_path=tmp_path / "recovery.json",
    )
    workspace = FakeWorkspace(tmp_path / "state.json")

    with TestClient(
        create_app(
            settings,
            workspace=workspace,
            resume_builder=FakeResumeDocumentBuilder(),
        )
    ) as client:
        health = client.get("/api/v1/health").json()

    assert health["checks"]["analysis"] == "ready"


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
            "insufficient_concrete_signals",
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
            },
            {
                "name": "React",
                "category": "framework_library",
                "importance": "preferred",
                "evidence": "React",
            },
            {
                "name": "Automated testing",
                "category": "testing_quality",
                "importance": "signal",
                "evidence": "automated tests",
            },
        ],
    }
    chat = RecordedChatModel([json.dumps(invalid_payload), json.dumps(valid)])
    content = (
        "Build Python and React services with automated tests and "
        "strong communication skills."
    )

    result, _store = run_graph(chat, application(content))

    assert result.result == "analyzed"
    assert repair_code in chat.messages[1][-1][1]


def test_graph_repairs_persisted_analysis_without_calling_deepseek():
    record = replace(
        application("Build Python services."),
        analysis=ApplicationAnalysisDocument(
            summary="One. Two. Three.",
            match_score=84,
            skill_signals=("Programming Languages: Python",),
            heading="Application Analysis",
        ),
    )
    chat = RecordedChatModel([])

    outcome, store = run_graph(chat, record)

    assert outcome.result == "repaired"
    assert outcome.match_score == 84
    assert store.final_score == 84
    assert chat.messages == []


def test_graph_returns_typed_failure_after_exhausting_structured_repairs():
    chat = RecordedChatModel(["not-json", "still-not-json", "also-not-json"])

    outcome, store = run_graph(chat, application("Build Python services."))

    assert outcome.result == "failed"
    assert outcome.errors == ("Application Analysis output failed validation.",)
    assert store.document is None
    assert store.final_score is None
    assert len(chat.messages) == 3


def test_graph_preserves_body_first_partial_state_when_property_commit_fails():
    class FailingFinalizeStore(AnalysisStore):
        async def finalize_application_analysis(self, application_id, *, match_score):
            raise RuntimeError("private Notion failure")

    record = application("Build Python and React services with automated tests.")
    store = FailingFinalizeStore(record)
    chat = RecordedChatModel(
        [
            json.dumps(
                {
                    "summary": ["One.", "Two.", "Three."],
                    "skillSignals": [
                        {
                            "name": "Python",
                            "category": "programming_language",
                            "importance": "required",
                            "evidence": "Python",
                        },
                        {
                            "name": "React",
                            "category": "framework_library",
                            "importance": "preferred",
                            "evidence": "React",
                        },
                        {
                            "name": "Automated testing",
                            "category": "testing_quality",
                            "importance": "signal",
                            "evidence": "automated tests",
                        },
                    ],
                }
            )
        ]
    )
    graph = ApplicationAnalysisGraph(
        store,
        DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat)),
        EvidenceMatchingEngine(),
    )

    outcome = asyncio.run(graph.run(record, batch_run_id="batch-1"))

    assert outcome.result == "failed"
    assert store.document is not None
    assert store.final_score is None


@pytest.mark.parametrize("model_kind", ["recorded_deepseek", "deterministic_fake"])
def test_analysis_models_share_the_graph_output_contract(model_kind):
    record = application("Build accessible React interfaces with automated tests.")
    store = AnalysisStore(record)
    if model_kind == "recorded_deepseek":
        chat = RecordedChatModel(
            [
                json.dumps(
                    {
                        "summary": ["One.", "Two.", "Three."],
                        "skillSignals": [
                            {
                                "name": "React",
                                "category": "framework_library",
                                "importance": "required",
                                "evidence": "React",
                            },
                            {
                                "name": "Accessibility",
                                "category": "domain_knowledge",
                                "importance": "preferred",
                                "evidence": "accessible",
                            },
                            {
                                "name": "Automated testing",
                                "category": "testing_quality",
                                "importance": "signal",
                                "evidence": "automated tests",
                            },
                        ],
                    }
                )
            ]
        )
        model = DeepSeekApplicationAnalysisModel(DeepSeekJsonClient(chat))
    else:
        model = FakeApplicationAnalysisModel()
    graph = ApplicationAnalysisGraph(store, model, EvidenceMatchingEngine())

    outcome = asyncio.run(graph.run(record, batch_run_id="batch-contract"))

    assert outcome.result == "analyzed"
    assert outcome.match_score is not None
    assert store.document is not None
    assert store.final_score == outcome.match_score
