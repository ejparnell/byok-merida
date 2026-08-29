"""Context-neutral conservative provider-spend arithmetic.

Workflow contexts own approvals and durable ledgers.  This module owns only the
pure request-bound and receipt-settlement policy shared by those contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Protocol


TOKENS_PER_RATE_UNIT = 1_000_000


class ProviderSpendPolicyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ProviderAuthorizationBlocked(ProviderSpendPolicyError):
    pass


class ProviderContextLimitExceeded(ProviderSpendPolicyError):
    pass


class ApprovedProviderModel(Protocol):
    provider: str
    endpoint: str
    model: str
    approval_fingerprint: str
    max_output_tokens: int
    max_context_tokens: int
    protocol_overhead_tokens: int
    protocol_maximum_messages: int
    cache_hit_input_micros_per_million_tokens: int
    cache_miss_input_micros_per_million_tokens: int
    output_micros_per_million_tokens: int


@dataclass(frozen=True)
class ProviderCostEstimate:
    provider: str
    endpoint: str
    model: str
    approval_fingerprint: str
    request_fingerprint: str
    tokenizer_tokens: int
    utf8_bytes: int
    protocol_overhead_tokens: int
    input_cost_bound_tokens: int
    max_output_tokens: int
    cache_hit_input_micros_per_million_tokens: int
    cache_miss_input_micros_per_million_tokens: int
    output_micros_per_million_tokens: int
    worst_case_micros: int


@dataclass(frozen=True)
class ProviderUsageReceipt:
    provider_request_id: str
    endpoint: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit_input_tokens: int = 0
    cache_miss_input_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class ProviderSettlement:
    valid: bool
    verified_cost_micros: int | None
    reason_code: str | None


class ProviderSpendPolicy:
    def __init__(
        self,
        approval: Callable[[str, str], ApprovedProviderModel],
        tokenizer_factory: Callable[[ApprovedProviderModel], Callable[[str], int]],
        *,
        context_code: str = "source_context_exceeded",
    ):
        self._approval = approval
        self._tokenizer_factory = tokenizer_factory
        self._context_code = context_code

    def estimate(
        self,
        *,
        endpoint: str,
        model: str,
        rendered_request: bytes,
        max_output_tokens: int,
    ) -> ProviderCostEstimate:
        text, document = _decode_request(rendered_request)
        entry = self._approval(endpoint, model)
        if max_output_tokens != entry.max_output_tokens:
            raise ProviderAuthorizationBlocked(
                "output_bound_not_approved", "The output bound is not approved."
            )
        _validate_envelope(document, entry, max_output_tokens)
        try:
            tokenizer_tokens = self._tokenizer_factory(entry)(text)
            if type(tokenizer_tokens) is not int or tokenizer_tokens < 0:
                raise ValueError("invalid tokenizer result")
        except Exception as error:
            raise ProviderAuthorizationBlocked(
                "tokenizer_unavailable", "The approved tokenizer is unavailable."
            ) from error
        utf8_bytes = len(rendered_request)
        input_bound = max(tokenizer_tokens, utf8_bytes) + entry.protocol_overhead_tokens
        if input_bound + max_output_tokens > entry.max_context_tokens:
            raise ProviderContextLimitExceeded(
                self._context_code, "The source exceeds the approved model context."
            )
        input_cost = ceiling_divide(
            input_bound * entry.cache_miss_input_micros_per_million_tokens,
            TOKENS_PER_RATE_UNIT,
        )
        output_cost = ceiling_divide(
            max_output_tokens * entry.output_micros_per_million_tokens,
            TOKENS_PER_RATE_UNIT,
        )
        return ProviderCostEstimate(
            provider=entry.provider,
            endpoint=entry.endpoint,
            model=entry.model,
            approval_fingerprint=entry.approval_fingerprint,
            request_fingerprint=hashlib.sha256(rendered_request).hexdigest(),
            tokenizer_tokens=tokenizer_tokens,
            utf8_bytes=utf8_bytes,
            protocol_overhead_tokens=entry.protocol_overhead_tokens,
            input_cost_bound_tokens=input_bound,
            max_output_tokens=max_output_tokens,
            cache_hit_input_micros_per_million_tokens=entry.cache_hit_input_micros_per_million_tokens,
            cache_miss_input_micros_per_million_tokens=entry.cache_miss_input_micros_per_million_tokens,
            output_micros_per_million_tokens=entry.output_micros_per_million_tokens,
            worst_case_micros=input_cost + output_cost,
        )

    def settle(
        self,
        estimate: ProviderCostEstimate,
        receipt: ProviderUsageReceipt | None,
    ) -> ProviderSettlement:
        if receipt is None:
            return ProviderSettlement(False, None, "settlement_evidence_missing")
        if not _receipt_shape_valid(receipt):
            return ProviderSettlement(False, None, "settlement_evidence_malformed")
        if receipt.endpoint != estimate.endpoint or receipt.model != estimate.model:
            return ProviderSettlement(False, None, "settlement_evidence_mismatch")
        if not _receipt_reconciles(estimate, receipt):
            return ProviderSettlement(False, None, "settlement_evidence_unreconcilable")
        cache_miss = receipt.input_tokens - receipt.cache_hit_input_tokens
        cost = ceiling_divide(
            cache_miss * estimate.cache_miss_input_micros_per_million_tokens
            + receipt.cache_hit_input_tokens
            * estimate.cache_hit_input_micros_per_million_tokens
            + receipt.output_tokens * estimate.output_micros_per_million_tokens,
            TOKENS_PER_RATE_UNIT,
        )
        if cost > estimate.worst_case_micros:
            return ProviderSettlement(False, None, "settlement_evidence_unreconcilable")
        return ProviderSettlement(True, cost, None)


def _decode_request(value: bytes) -> tuple[str, dict]:
    try:
        text = value.decode("utf-8")
        document = json.loads(text)
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderAuthorizationBlocked(
            "request_not_rendered", "The exact rendered request is required."
        ) from error
    if not value or not isinstance(document, dict):
        raise ProviderAuthorizationBlocked(
            "request_not_rendered", "The exact rendered request is required."
        )
    return text, document


def _validate_envelope(
    document: dict, entry: ApprovedProviderModel, max_output_tokens: int
) -> None:
    if document.get("model") != entry.model:
        raise ProviderAuthorizationBlocked(
            "request_model_mismatch", "The rendered request model is not approved."
        )
    if document.get("max_tokens") != max_output_tokens:
        raise ProviderAuthorizationBlocked(
            "request_output_bound_mismatch", "The rendered output bound differs."
        )
    messages = document.get("messages")
    valid_messages = (
        isinstance(messages, list)
        and 2 <= len(messages) <= entry.protocol_maximum_messages
        and all(
            isinstance(message, dict)
            and isinstance(message.get("content"), str)
            and message.get("role") == ("system" if index == 0 else "user")
            for index, message in enumerate(messages)
        )
    )
    if (
        not valid_messages
        or document.get("stream") is not False
        or document.get("reasoning_effort") != "high"
        or document.get("thinking") != {"type": "enabled"}
        or document.get("response_format") != {"type": "json_object"}
    ):
        raise ProviderAuthorizationBlocked(
            "request_protocol_mismatch", "The request protocol is not approved."
        )


def _receipt_shape_valid(receipt: ProviderUsageReceipt) -> bool:
    return bool(
        isinstance(receipt.provider_request_id, str)
        and receipt.provider_request_id.strip()
        and type(receipt.input_tokens) is int
        and receipt.input_tokens > 0
        and type(receipt.output_tokens) is int
        and receipt.output_tokens > 0
        and _nonnegative(receipt.cache_hit_input_tokens)
        and (receipt.cache_miss_input_tokens is None or _nonnegative(receipt.cache_miss_input_tokens))
        and (receipt.total_tokens is None or _nonnegative(receipt.total_tokens))
        and (receipt.reasoning_output_tokens is None or _nonnegative(receipt.reasoning_output_tokens))
        and receipt.cache_hit_input_tokens <= receipt.input_tokens
    )


def _receipt_reconciles(
    estimate: ProviderCostEstimate, receipt: ProviderUsageReceipt
) -> bool:
    return not (
        receipt.input_tokens > estimate.input_cost_bound_tokens
        or receipt.output_tokens > estimate.max_output_tokens
        or (
            receipt.total_tokens is not None
            and receipt.total_tokens != receipt.input_tokens + receipt.output_tokens
        )
        or (
            receipt.cache_miss_input_tokens is not None
            and receipt.cache_hit_input_tokens + receipt.cache_miss_input_tokens
            != receipt.input_tokens
        )
        or (
            receipt.reasoning_output_tokens is not None
            and receipt.reasoning_output_tokens > receipt.output_tokens
        )
    )


def ceiling_divide(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def _nonnegative(value: object) -> bool:
    return type(value) is int and value >= 0
