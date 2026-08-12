from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from merida_api.features.applications.analysis_spend import (
    ANALYSIS_OUTPUT_TOKEN_BOUND,
    RATE_CARD_PATH,
    AnalysisAuthorizationBlocked,
    AnalysisContextLimitExceeded,
    AnalysisRateCard,
    AnalysisSpendPolicy,
    AnalysisUsageReceipt,
)


VERIFIED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
END_OF_WINDOW = datetime(2026, 9, 11, 23, 59, tzinfo=timezone.utc)
AFTER_WINDOW = datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc)
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"


def policy(*, now=VERIFIED_AT, token_count: int | None = None):
    tokenizer_factory = None
    if token_count is not None:
        tokenizer_factory = lambda _approval: lambda _text: token_count
    return AnalysisSpendPolicy(
        AnalysisRateCard.load(),
        clock=lambda: now,
        tokenizer_factory=tokenizer_factory,
    )


def rendered_request(
    content: str,
    *,
    model: str = MODEL,
    max_tokens: int = ANALYSIS_OUTPUT_TOKEN_BOUND,
) -> bytes:
    return json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "Be exact."},
                {"role": "user", "content": content},
            ],
            "max_tokens": max_tokens,
            "stream": False,
            "reasoning_effort": "high",
            "thinking": {"type": "enabled"},
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def test_reviewed_tokenizer_and_protocol_evidence_bound_the_exact_request():
    request = rendered_request("Analyze Python and café operations.")

    estimate = policy().estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=request,
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )

    # Token count comes from the immutable DeepSeek-V4-Flash tokenizer revision
    # named in the reviewed rate card; protocol overhead comes from that
    # revision's published chat encoder for Analysis' largest three-message call.
    assert estimate.tokenizer_tokens == 74
    assert estimate.utf8_bytes == 277
    assert estimate.protocol_overhead_tokens == 27
    assert estimate.input_cost_bound_tokens == 304
    assert estimate.worst_case_micros == 2_283
    assert estimate.request_fingerprint == hashlib.sha256(request).hexdigest()


def test_cost_authorization_uses_whichever_conservative_input_branch_is_greater():
    request = rendered_request("Analyze Python and café operations.")

    byte_bound = policy(token_count=1).estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=request,
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )
    tokenizer_bound = policy(token_count=400).estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=request,
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )

    assert byte_bound.input_cost_bound_tokens == 304
    assert tokenizer_bound.input_cost_bound_tokens == 427
    assert byte_bound.worst_case_micros == 2_283
    assert tokenizer_bound.worst_case_micros == 2_300


def test_context_boundary_is_checked_without_changing_the_rendered_request():
    request = rendered_request("Do not truncate this Job Content.")
    original = bytes(request)

    exact_boundary = policy(token_count=991_973).estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=request,
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )
    with pytest.raises(AnalysisContextLimitExceeded) as raised:
        policy(token_count=991_974).estimate(
            endpoint=ENDPOINT,
            model=MODEL,
            rendered_request=request,
            max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
        )

    assert exact_boundary.input_cost_bound_tokens == 992_000
    assert raised.value.code == "source_context_exceeded"
    assert request == original


def test_rate_card_requires_the_exact_model_and_is_valid_only_through_day_30():
    request = rendered_request("Analyze Python.")

    estimate = policy(now=END_OF_WINDOW).estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=request,
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )

    assert estimate.model == MODEL
    for now, endpoint, model, code in (
        (VERIFIED_AT, ENDPOINT, "unknown-model", "model_not_approved"),
        (VERIFIED_AT, "https://gateway.example/chat", MODEL, "model_not_approved"),
        (AFTER_WINDOW, ENDPOINT, MODEL, "pricing_approval_expired"),
    ):
        with pytest.raises(AnalysisAuthorizationBlocked) as raised:
            policy(now=now).estimate(
                endpoint=endpoint,
                model=model,
                rendered_request=request,
                max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
            )
        assert raised.value.code == code


def test_authorization_rejects_a_request_whose_wire_model_or_output_bound_differs():
    for request, code in (
        (rendered_request("Analyze Python.", model="other-model"), "request_model_mismatch"),
        (rendered_request("Analyze Python.", max_tokens=7_999), "request_output_bound_mismatch"),
    ):
        with pytest.raises(AnalysisAuthorizationBlocked) as raised:
            policy().estimate(
                endpoint=ENDPOINT,
                model=MODEL,
                rendered_request=request,
                max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
            )
        assert raised.value.code == code


def test_authorization_rejects_an_envelope_outside_reviewed_protocol_evidence():
    document = json.loads(rendered_request("Analyze Python."))
    document["messages"].append({"role": "user", "content": "repair one"})
    document["messages"].append({"role": "user", "content": "repair two"})
    unreviewed_request = json.dumps(document, separators=(",", ":")).encode()

    with pytest.raises(AnalysisAuthorizationBlocked) as raised:
        policy().estimate(
            endpoint=ENDPOINT,
            model=MODEL,
            rendered_request=unreviewed_request,
            max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
        )

    assert raised.value.code == "request_protocol_mismatch"


def test_missing_or_tampered_reviewed_tokenizer_artifact_fails_closed(tmp_path: Path):
    document = json.loads(RATE_CARD_PATH.read_text())
    tokenizer = document["entries"][0]["tokenizer"]
    source_artifact = RATE_CARD_PATH.parent / tokenizer["artifact"]
    copied_artifact = tmp_path / source_artifact.name
    shutil.copyfile(source_artifact, copied_artifact)
    tokenizer["artifactSha256"] = "0" * 64
    copied_card = tmp_path / RATE_CARD_PATH.name
    copied_card.write_text(json.dumps(document))

    with pytest.raises(AnalysisAuthorizationBlocked) as raised:
        AnalysisRateCard.load(copied_card)

    assert raised.value.code == "rate_card_unavailable"


def test_malformed_reviewed_configuration_fails_closed(tmp_path: Path):
    malformed_card = tmp_path / "analysis-rate-card.json"
    malformed_card.write_text("[]")

    with pytest.raises(AnalysisAuthorizationBlocked) as raised:
        AnalysisRateCard.load(malformed_card)

    assert raised.value.code == "rate_card_unavailable"


def test_valid_usage_settles_once_while_untrusted_evidence_releases_nothing():
    spend = policy()
    estimate = spend.estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=rendered_request("Analyze Python."),
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )

    settled = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="request-1",
            endpoint=ENDPOINT,
            model=MODEL,
            input_tokens=100,
            cache_hit_input_tokens=40,
            cache_miss_input_tokens=60,
            output_tokens=200,
            total_tokens=300,
            reasoning_output_tokens=150,
            finish_reason="stop",
        ),
    )
    missing = spend.settle(estimate, None)
    mismatch = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="request-2",
            endpoint=ENDPOINT,
            model="another-model",
            input_tokens=100,
            output_tokens=200,
        ),
    )
    malformed = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="",
            endpoint=ENDPOINT,
            model=MODEL,
            input_tokens=-1,
            output_tokens=200,
        ),
    )
    zero_usage = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="request-zero",
            endpoint=ENDPOINT,
            model=MODEL,
            input_tokens=0,
            output_tokens=0,
        ),
    )
    unreconcilable = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="request-3",
            endpoint=ENDPOINT,
            model=MODEL,
            input_tokens=estimate.input_cost_bound_tokens + 1,
            output_tokens=1,
        ),
    )

    assert settled.valid is True
    assert settled.verified_cost_micros == 65
    assert settled.verified_cost_micros < estimate.worst_case_micros
    assert missing.reason_code == "settlement_evidence_missing"
    assert mismatch.reason_code == "settlement_evidence_mismatch"
    assert malformed.reason_code == "settlement_evidence_malformed"
    assert zero_usage.reason_code == "settlement_evidence_malformed"
    assert unreconcilable.reason_code == "settlement_evidence_unreconcilable"
    assert all(
        outcome.verified_cost_micros is None
        for outcome in (missing, mismatch, malformed, zero_usage, unreconcilable)
    )


@pytest.mark.parametrize(
    "receipt_overrides",
    [
        {"total_tokens": 999},
        {"cache_miss_input_tokens": 999},
        {"reasoning_output_tokens": 201},
        {"total_tokens": -1},
        {"cache_miss_input_tokens": -1},
        {"reasoning_output_tokens": -1},
    ],
)
def test_contradictory_optional_usage_evidence_releases_no_reservation(
    receipt_overrides,
):
    spend = policy()
    estimate = spend.estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=rendered_request("Analyze Python."),
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )
    receipt = {
        "provider_request_id": "request-contradictory",
        "endpoint": ENDPOINT,
        "model": MODEL,
        "input_tokens": 100,
        "output_tokens": 200,
        "cache_hit_input_tokens": 40,
        "cache_miss_input_tokens": 60,
        "total_tokens": 300,
        "reasoning_output_tokens": 150,
    }
    receipt.update(receipt_overrides)

    settlement = spend.settle(estimate, AnalysisUsageReceipt(**receipt))

    assert settlement.valid is False
    assert settlement.verified_cost_micros is None
    assert settlement.reason_code in {
        "settlement_evidence_malformed",
        "settlement_evidence_unreconcilable",
    }


def test_settlement_uses_the_call_approval_even_if_the_clock_window_has_closed():
    now = VERIFIED_AT
    spend = AnalysisSpendPolicy(
        AnalysisRateCard.load(),
        clock=lambda: now,
        tokenizer_factory=lambda _approval: lambda _text: 1,
    )
    estimate = spend.estimate(
        endpoint=ENDPOINT,
        model=MODEL,
        rendered_request=rendered_request("Analyze Python."),
        max_output_tokens=ANALYSIS_OUTPUT_TOKEN_BOUND,
    )
    now = AFTER_WINDOW

    settlement = spend.settle(
        estimate,
        AnalysisUsageReceipt(
            provider_request_id="request-after-midnight",
            endpoint=ENDPOINT,
            model=MODEL,
            input_tokens=10,
            output_tokens=10,
        ),
    )

    assert settlement.valid is True
    assert settlement.verified_cost_micros == 5
