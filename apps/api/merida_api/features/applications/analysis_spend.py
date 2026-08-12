from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlparse


ANALYSIS_OUTPUT_TOKEN_BOUND = 8_000
ANALYSIS_SPEND_CEILING_MICROS = 500_000
RATE_CARD_PATH = Path(__file__).with_name("analysis_rate_card.v1.json")
TOKENS_PER_RATE_UNIT = 1_000_000
USD_MICROS_PER_DOLLAR = 1_000_000

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")


class AnalysisSpendPolicyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AnalysisAuthorizationBlocked(AnalysisSpendPolicyError):
    pass


class AnalysisContextLimitExceeded(AnalysisSpendPolicyError):
    pass


@dataclass(frozen=True)
class ApprovedAnalysisModel:
    provider: str
    endpoint: str
    model: str
    source_url: str
    verified_on: date
    valid_through: date
    cache_hit_input_micros_per_million_tokens: int
    cache_miss_input_micros_per_million_tokens: int
    output_micros_per_million_tokens: int
    max_output_tokens: int
    max_context_tokens: int
    tokenizer_artifact_path: Path
    tokenizer_artifact_sha256: str
    tokenizer_source_url: str
    tokenizer_source_revision: str
    tokenizer_source_sha256: str
    protocol_overhead_tokens: int
    protocol_maximum_analysis_messages: int
    protocol_overhead_source_url: str
    protocol_overhead_source_revision: str
    protocol_overhead_source_sha256: str
    approval_fingerprint: str


@dataclass(frozen=True)
class AnalysisCostEstimate:
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
class AnalysisUsageReceipt:
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
class AnalysisSettlement:
    valid: bool
    verified_cost_micros: int | None
    reason_code: str | None


TokenizerFactory = Callable[[ApprovedAnalysisModel], Callable[[str], int]]


class AnalysisRateCard:
    def __init__(self, entries: tuple[ApprovedAnalysisModel, ...]):
        self._entries = entries

    @classmethod
    def load(cls, path: Path = RATE_CARD_PATH) -> "AnalysisRateCard":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise TypeError("rate card must be an object")
            if document.get("schemaVersion") != 1:
                raise ValueError("unsupported schema")
            raw_entries = document["entries"]
            if not isinstance(raw_entries, list):
                raise TypeError("entries must be a list")
            entries = tuple(
                _approved_model(item, artifact_directory=path.parent)
                for item in raw_entries
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise AnalysisAuthorizationBlocked(
                "rate_card_unavailable",
                "The reviewed Analysis rate card is unavailable.",
            ) from error
        if not entries:
            raise AnalysisAuthorizationBlocked(
                "rate_card_unavailable",
                "The reviewed Analysis rate card has no approved models.",
            )
        identities = {(entry.endpoint, entry.model) for entry in entries}
        if len(identities) != len(entries):
            raise AnalysisAuthorizationBlocked(
                "rate_card_unavailable",
                "The reviewed Analysis rate card has duplicate approvals.",
            )
        return cls(entries)

    def approved_model(
        self,
        *,
        endpoint: str,
        model: str,
        at: datetime,
    ) -> ApprovedAnalysisModel:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Rate-card checks require a timezone-aware clock.")
        entry = next(
            (
                candidate
                for candidate in self._entries
                if candidate.endpoint == endpoint and candidate.model == model
            ),
            None,
        )
        if entry is None:
            raise AnalysisAuthorizationBlocked(
                "model_not_approved",
                "The configured Analysis endpoint and model are not approved.",
            )
        current = at.astimezone(timezone.utc).date()
        if current < entry.verified_on or current > entry.valid_through:
            raise AnalysisAuthorizationBlocked(
                "pricing_approval_expired",
                "The configured Analysis pricing approval is not current.",
            )
        return entry


class AnalysisSpendPolicy:
    def __init__(
        self,
        rate_card: AnalysisRateCard,
        *,
        clock: Callable[[], datetime] | None = None,
        tokenizer_factory: TokenizerFactory | None = None,
    ):
        self._rate_card = rate_card
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._tokenizer_factory = tokenizer_factory or _pinned_tokenizer

    def estimate(
        self,
        *,
        endpoint: str,
        model: str,
        rendered_request: bytes,
        max_output_tokens: int,
    ) -> AnalysisCostEstimate:
        rendered_text, request_document = _decode_rendered_request(rendered_request)
        entry = self._rate_card.approved_model(
            endpoint=endpoint,
            model=model,
            at=self._clock(),
        )
        if max_output_tokens != entry.max_output_tokens:
            raise AnalysisAuthorizationBlocked(
                "output_bound_not_approved",
                "The Analysis output bound does not match its reviewed approval.",
            )
        _validate_wire_identity(
            request_document,
            model=model,
            max_output_tokens=max_output_tokens,
            maximum_analysis_messages=entry.protocol_maximum_analysis_messages,
        )
        try:
            tokenizer = self._tokenizer_factory(entry)
            tokenizer_tokens = tokenizer(rendered_text)
            if type(tokenizer_tokens) is not int or tokenizer_tokens < 0:
                raise ValueError("tokenizer did not return a non-negative integer")
        except Exception as error:
            raise AnalysisAuthorizationBlocked(
                "tokenizer_unavailable",
                "The approved Analysis tokenizer is unavailable.",
            ) from error

        utf8_bytes = len(rendered_request)
        input_bound = (
            max(tokenizer_tokens, utf8_bytes) + entry.protocol_overhead_tokens
        )
        if input_bound + max_output_tokens > entry.max_context_tokens:
            raise AnalysisContextLimitExceeded(
                "source_context_exceeded",
                "Job Content exceeds the approved Analysis model context.",
            )
        input_cost = _ceiling_divide(
            input_bound * entry.cache_miss_input_micros_per_million_tokens,
            TOKENS_PER_RATE_UNIT,
        )
        output_cost = _ceiling_divide(
            max_output_tokens * entry.output_micros_per_million_tokens,
            TOKENS_PER_RATE_UNIT,
        )
        return AnalysisCostEstimate(
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
            cache_hit_input_micros_per_million_tokens=(
                entry.cache_hit_input_micros_per_million_tokens
            ),
            cache_miss_input_micros_per_million_tokens=(
                entry.cache_miss_input_micros_per_million_tokens
            ),
            output_micros_per_million_tokens=(
                entry.output_micros_per_million_tokens
            ),
            worst_case_micros=input_cost + output_cost,
        )

    def settle(
        self,
        estimate: AnalysisCostEstimate,
        receipt: AnalysisUsageReceipt | None,
    ) -> AnalysisSettlement:
        if receipt is None:
            return AnalysisSettlement(False, None, "settlement_evidence_missing")
        if (
            not isinstance(receipt.provider_request_id, str)
            or not receipt.provider_request_id.strip()
            or type(receipt.input_tokens) is not int
            or receipt.input_tokens <= 0
            or type(receipt.output_tokens) is not int
            or receipt.output_tokens <= 0
            or not _nonnegative_integer(receipt.cache_hit_input_tokens)
            or (
                receipt.cache_miss_input_tokens is not None
                and not _nonnegative_integer(receipt.cache_miss_input_tokens)
            )
            or (
                receipt.total_tokens is not None
                and not _nonnegative_integer(receipt.total_tokens)
            )
            or (
                receipt.reasoning_output_tokens is not None
                and not _nonnegative_integer(receipt.reasoning_output_tokens)
            )
            or receipt.cache_hit_input_tokens > receipt.input_tokens
        ):
            return AnalysisSettlement(False, None, "settlement_evidence_malformed")
        if receipt.endpoint != estimate.endpoint or receipt.model != estimate.model:
            return AnalysisSettlement(False, None, "settlement_evidence_mismatch")
        if (
            receipt.input_tokens > estimate.input_cost_bound_tokens
            or receipt.output_tokens > estimate.max_output_tokens
            or (
                receipt.total_tokens is not None
                and receipt.total_tokens
                != receipt.input_tokens + receipt.output_tokens
            )
            or (
                receipt.cache_miss_input_tokens is not None
                and receipt.cache_hit_input_tokens
                + receipt.cache_miss_input_tokens
                != receipt.input_tokens
            )
            or (
                receipt.reasoning_output_tokens is not None
                and receipt.reasoning_output_tokens > receipt.output_tokens
            )
        ):
            return AnalysisSettlement(
                False,
                None,
                "settlement_evidence_unreconcilable",
            )

        cache_miss_tokens = receipt.input_tokens - receipt.cache_hit_input_tokens
        cost_numerator = (
            cache_miss_tokens
            * estimate.cache_miss_input_micros_per_million_tokens
            + receipt.cache_hit_input_tokens
            * estimate.cache_hit_input_micros_per_million_tokens
            + receipt.output_tokens * estimate.output_micros_per_million_tokens
        )
        verified_cost = _ceiling_divide(cost_numerator, TOKENS_PER_RATE_UNIT)
        if verified_cost > estimate.worst_case_micros:
            return AnalysisSettlement(
                False,
                None,
                "settlement_evidence_unreconcilable",
            )
        return AnalysisSettlement(True, verified_cost, None)


class UnavailableAnalysisSpendPolicy:
    def __init__(self, code: str = "rate_card_unavailable"):
        self.code = code

    def estimate(self, **_request):
        raise AnalysisAuthorizationBlocked(
            self.code,
            "Analysis spend authorization is unavailable.",
        )

    def settle(self, _estimate, _receipt) -> AnalysisSettlement:
        return AnalysisSettlement(False, None, self.code)


def _approved_model(
    item: object,
    *,
    artifact_directory: Path,
) -> ApprovedAnalysisModel:
    if not isinstance(item, dict):
        raise TypeError("rate-card entry must be an object")
    verified_on = date.fromisoformat(_required_text(item, "verifiedOn"))
    valid_through = date.fromisoformat(_required_text(item, "validThrough"))
    if valid_through != verified_on + timedelta(days=30):
        raise ValueError("approval window must be 30 days")

    cache_hit_rate = _positive_integer(
        item,
        "cacheHitInputUsdMicrosPerMillionTokens",
    )
    cache_miss_rate = _positive_integer(
        item,
        "cacheMissInputUsdMicrosPerMillionTokens",
    )
    output_rate = _positive_integer(
        item,
        "reasoningInclusiveOutputUsdMicrosPerMillionTokens",
    )
    max_output_tokens = _positive_integer(item, "maxOutputTokens")
    max_context_tokens = _positive_integer(item, "maxContextTokens")
    if cache_hit_rate > cache_miss_rate:
        raise ValueError("cache-hit rate cannot exceed cache-miss rate")
    if max_output_tokens != ANALYSIS_OUTPUT_TOKEN_BOUND:
        raise ValueError("rate-card output bound is not approved")
    if max_context_tokens <= max_output_tokens:
        raise ValueError("rate-card context is not usable")

    provider = _required_text(item, "provider")
    endpoint = _required_https_url(item, "endpoint")
    model = _required_text(item, "model")
    source_url = _required_https_url(item, "sourceUrl")

    tokenizer = item["tokenizer"]
    protocol = item["protocolOverhead"]
    if not isinstance(tokenizer, dict) or not isinstance(protocol, dict):
        raise TypeError("rate-card evidence must be an object")
    tokenizer_artifact_name = _safe_artifact_name(
        _required_text(tokenizer, "artifact")
    )
    tokenizer_artifact_sha256 = _required_sha256(
        tokenizer,
        "artifactSha256",
    )
    tokenizer_source_url = _required_https_url(tokenizer, "sourceUrl")
    tokenizer_source_revision = _required_revision(tokenizer, "sourceRevision")
    tokenizer_source_sha256 = _required_sha256(tokenizer, "sourceSha256")
    if tokenizer_source_revision not in tokenizer_source_url:
        raise ValueError("tokenizer source is not revision-pinned")
    tokenizer_artifact_path = artifact_directory / tokenizer_artifact_name
    artifact_bytes = tokenizer_artifact_path.read_bytes()
    if hashlib.sha256(artifact_bytes).hexdigest() != tokenizer_artifact_sha256:
        raise ValueError("tokenizer artifact checksum mismatch")

    protocol_overhead_tokens = _positive_integer(protocol, "tokens")
    maximum_analysis_messages = _positive_integer(
        protocol,
        "maximumAnalysisMessages",
    )
    if maximum_analysis_messages != 3:
        raise ValueError("protocol evidence does not cover Analysis recovery")
    protocol_source_url = _required_https_url(protocol, "sourceUrl")
    protocol_source_revision = _required_revision(protocol, "sourceRevision")
    protocol_source_sha256 = _required_sha256(protocol, "sourceSha256")
    _required_text(protocol, "derivation")
    if protocol_source_revision not in protocol_source_url:
        raise ValueError("protocol source is not revision-pinned")

    canonical_approval = json.dumps(
        item,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ApprovedAnalysisModel(
        provider=provider,
        endpoint=endpoint,
        model=model,
        source_url=source_url,
        verified_on=verified_on,
        valid_through=valid_through,
        cache_hit_input_micros_per_million_tokens=cache_hit_rate,
        cache_miss_input_micros_per_million_tokens=cache_miss_rate,
        output_micros_per_million_tokens=output_rate,
        max_output_tokens=max_output_tokens,
        max_context_tokens=max_context_tokens,
        tokenizer_artifact_path=tokenizer_artifact_path,
        tokenizer_artifact_sha256=tokenizer_artifact_sha256,
        tokenizer_source_url=tokenizer_source_url,
        tokenizer_source_revision=tokenizer_source_revision,
        tokenizer_source_sha256=tokenizer_source_sha256,
        protocol_overhead_tokens=protocol_overhead_tokens,
        protocol_maximum_analysis_messages=maximum_analysis_messages,
        protocol_overhead_source_url=protocol_source_url,
        protocol_overhead_source_revision=protocol_source_revision,
        protocol_overhead_source_sha256=protocol_source_sha256,
        approval_fingerprint=hashlib.sha256(canonical_approval).hexdigest(),
    )


def _decode_rendered_request(rendered_request: bytes) -> tuple[str, dict]:
    if not isinstance(rendered_request, bytes) or not rendered_request:
        raise AnalysisAuthorizationBlocked(
            "request_not_rendered",
            "The exact Analysis provider request is required for authorization.",
        )
    try:
        rendered_text = rendered_request.decode("utf-8")
        document = json.loads(rendered_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisAuthorizationBlocked(
            "request_not_rendered",
            "The exact Analysis provider request is required for authorization.",
        ) from error
    if not isinstance(document, dict):
        raise AnalysisAuthorizationBlocked(
            "request_not_rendered",
            "The exact Analysis provider request is required for authorization.",
        )
    return rendered_text, document


def _validate_wire_identity(
    document: dict,
    *,
    model: str,
    max_output_tokens: int,
    maximum_analysis_messages: int,
) -> None:
    if document.get("model") != model:
        raise AnalysisAuthorizationBlocked(
            "request_model_mismatch",
            "The rendered Analysis request does not use its approved model.",
        )
    if document.get("max_tokens") != max_output_tokens:
        raise AnalysisAuthorizationBlocked(
            "request_output_bound_mismatch",
            "The rendered Analysis request does not use its approved output bound.",
        )
    messages = document.get("messages")
    valid_messages = (
        isinstance(messages, list)
        and 2 <= len(messages) <= maximum_analysis_messages
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
        raise AnalysisAuthorizationBlocked(
            "request_protocol_mismatch",
            "The rendered Analysis request is outside its reviewed protocol evidence.",
        )


def _pinned_tokenizer(approval: ApprovedAnalysisModel) -> Callable[[str], int]:
    tokenizer = _load_pinned_tokenizer(
        str(approval.tokenizer_artifact_path),
        approval.tokenizer_artifact_sha256,
        approval.tokenizer_source_revision,
        approval.tokenizer_source_sha256,
    )

    def count_tokens(text: str) -> int:
        return tokenizer.count(text)

    return count_tokens


@lru_cache(maxsize=8)
def _load_pinned_tokenizer(
    artifact_path: str,
    artifact_sha256: str,
    source_revision: str,
    source_sha256: str,
):
    import regex
    import tiktoken

    compressed = Path(artifact_path).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != artifact_sha256:
        raise ValueError("tokenizer artifact checksum mismatch")
    document = json.loads(gzip.decompress(compressed))
    if (
        document.get("schemaVersion") != 1
        or document.get("sourceRevision") != source_revision
        or document.get("sourceSha256") != source_sha256
    ):
        raise ValueError("tokenizer artifact provenance mismatch")
    raw_patterns = document.get("pretokenizerPatterns")
    if (
        not isinstance(raw_patterns, list)
        or len(raw_patterns) != 3
        or any(not isinstance(pattern, str) or not pattern for pattern in raw_patterns)
    ):
        raise ValueError("tokenizer pre-tokenizer evidence is unavailable")
    mergeable_ranks = _decode_mergeable_ranks(document.get("mergeableRanks"))
    special_tokens = _decode_special_tokens(document.get("specialTokens"))
    ranks = set(mergeable_ranks.values()) | set(special_tokens.values())
    if ranks != set(range(len(ranks))):
        raise ValueError("tokenizer ranks are not complete")
    encoding = tiktoken.Encoding(
        name=f"deepseek-v4-{source_revision[:12]}",
        pat_str=r"(?s).+",
        mergeable_ranks=mergeable_ranks,
        special_tokens=special_tokens,
    )
    return _PinnedDeepSeekTokenizer(
        encoding=encoding,
        pretokenizer_patterns=tuple(regex.compile(pattern) for pattern in raw_patterns),
        special_token_trie=_special_token_trie(special_tokens),
    )


@dataclass(frozen=True)
class _PinnedDeepSeekTokenizer:
    encoding: object
    pretokenizer_patterns: tuple[object, ...]
    special_token_trie: dict

    def count(self, text: str) -> int:
        count = 0
        ordinary_start = 0
        index = 0
        while index < len(text):
            node = self.special_token_trie
            cursor = index
            matched_end: int | None = None
            while cursor < len(text) and text[cursor] in node:
                node = node[text[cursor]]
                cursor += 1
                if "" in node:
                    matched_end = cursor
            if matched_end is None:
                index += 1
                continue
            count += self._count_ordinary(text[ordinary_start:index]) + 1
            index = matched_end
            ordinary_start = matched_end
        return count + self._count_ordinary(text[ordinary_start:])

    def _count_ordinary(self, text: str) -> int:
        if not text:
            return 0
        pieces = [text]
        for pattern in self.pretokenizer_patterns:
            split_pieces: list[str] = []
            for piece in pieces:
                last = 0
                for match in pattern.finditer(piece):
                    if match.start() > last:
                        split_pieces.append(piece[last : match.start()])
                    if match.end() > match.start():
                        split_pieces.append(match.group())
                    last = match.end()
                if last < len(piece):
                    split_pieces.append(piece[last:])
            pieces = split_pieces
        return sum(
            len(self.encoding._encode_single_piece(piece))
            for piece in pieces
            if piece
        )


def _special_token_trie(special_tokens: dict[str, int]) -> dict:
    root: dict = {}
    for token, rank in special_tokens.items():
        node = root
        for character in token:
            node = node.setdefault(character, {})
        node[""] = rank
    return root


def _decode_mergeable_ranks(value: object) -> dict[bytes, int]:
    if not isinstance(value, list):
        raise TypeError("tokenizer mergeable ranks are unavailable")
    result: dict[bytes, int] = {}
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not _nonnegative_integer(item[1])
        ):
            raise TypeError("tokenizer mergeable rank is invalid")
        try:
            token = base64.b64decode(item[0], validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("tokenizer token is invalid") from error
        if not token or token in result:
            raise ValueError("tokenizer token is duplicated")
        result[token] = item[1]
    if len(set(result.values())) != len(result):
        raise ValueError("tokenizer mergeable ranks are duplicated")
    return result


def _decode_special_tokens(value: object) -> dict[str, int]:
    if not isinstance(value, list):
        raise TypeError("tokenizer special tokens are unavailable")
    result: dict[str, int] = {}
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not item[0]
            or not _nonnegative_integer(item[1])
            or item[0] in result
        ):
            raise TypeError("tokenizer special token is invalid")
        result[item[0]] = item[1]
    if len(set(result.values())) != len(result):
        raise ValueError("tokenizer special-token ranks are duplicated")
    return result


def _required_text(item: dict, field: str) -> str:
    value = item[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _required_https_url(item: dict, field: str) -> str:
    value = _required_text(item, field)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{field} must be an HTTPS URL")
    return value


def _required_sha256(item: dict, field: str) -> str:
    value = _required_text(item, field)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a SHA-256 digest")
    return value


def _required_revision(item: dict, field: str) -> str:
    value = _required_text(item, field)
    if _REVISION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be an immutable revision")
    return value


def _safe_artifact_name(value: str) -> str:
    if Path(value).name != value or value in {".", ".."}:
        raise ValueError("tokenizer artifact must be package-local")
    return value


def _positive_integer(item: dict, field: str) -> int:
    value = item[field]
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _ceiling_divide(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def _nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0
