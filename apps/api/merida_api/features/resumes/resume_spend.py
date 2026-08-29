from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path

from ...shared.provider_spend import (
    ProviderAuthorizationBlocked,
    ProviderSpendPolicy,
    ProviderUsageReceipt,
)
from ..applications.analysis_spend import _pinned_tokenizer


RATE_CARD_PATH = Path(__file__).with_name("resume_rate_card.v1.json")


@dataclass(frozen=True)
class ApprovedResumeModel:
    stage: str
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
    tokenizer_artifact_path: Path
    tokenizer_artifact_sha256: str
    tokenizer_source_revision: str = "60d8d70770c6776ff598c94bb586a859a38244f1"
    tokenizer_source_sha256: str = "8f9f37ca37fdc4f5fd36d5cf4d3b0e8392edb4e894fd10cc0d70b4957c8633cf"


class ResumeRateCard:
    def __init__(self, entries: tuple[ApprovedResumeModel, ...], *, clock=None):
        self._entries = entries
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def load(cls, path: Path = RATE_CARD_PATH, *, clock=None) -> "ResumeRateCard":
        try:
            document = json.loads(path.read_text())
            raw_entries = document["entries"]
            if document.get("schemaVersion") != 1 or len(raw_entries) != 2:
                raise ValueError("invalid Resume rate card")
            entries = []
            for item in raw_entries:
                artifact = (path.parent / item["tokenizerArtifact"]).resolve()
                if hashlib.sha256(artifact.read_bytes()).hexdigest() != item["tokenizerArtifactSha256"]:
                    raise ValueError("tokenizer checksum mismatch")
                verified = date.fromisoformat(item["verifiedOn"])
                valid = date.fromisoformat(item["validThrough"])
                if (valid - verified).days > 30:
                    raise ValueError("approval window exceeds 30 days")
                canonical = json.dumps(item, sort_keys=True, separators=(",", ":")).encode()
                entries.append(ApprovedResumeModel(
                    stage=item["stage"], provider=item["provider"], endpoint=item["endpoint"],
                    model=item["model"], approval_fingerprint=hashlib.sha256(canonical).hexdigest(),
                    max_output_tokens=item["maxOutputTokens"], max_context_tokens=item["maxContextTokens"],
                    protocol_overhead_tokens=item["protocolOverheadTokens"],
                    protocol_maximum_messages=item["protocolMaximumMessages"],
                    cache_hit_input_micros_per_million_tokens=item["cacheHitInputUsdMicrosPerMillionTokens"],
                    cache_miss_input_micros_per_million_tokens=item["cacheMissInputUsdMicrosPerMillionTokens"],
                    output_micros_per_million_tokens=item["reasoningInclusiveOutputUsdMicrosPerMillionTokens"],
                    tokenizer_artifact_path=artifact, tokenizer_artifact_sha256=item["tokenizerArtifactSha256"],
                ))
            if len({(entry.endpoint, entry.model) for entry in entries}) != 2:
                raise ValueError("duplicate Resume approval")
        except Exception as error:
            raise ProviderAuthorizationBlocked("rate_card_unavailable", "Resume pricing approval is unavailable.") from error
        card = cls(tuple(entries), clock=clock)
        for entry in entries:
            card.approved(entry.endpoint, entry.model)
        return card

    def approved(self, endpoint: str, model: str) -> ApprovedResumeModel:
        entry = next((value for value in self._entries if value.endpoint == endpoint and value.model == model), None)
        if entry is None:
            raise ProviderAuthorizationBlocked("model_not_approved", "Resume model is not approved.")
        document = json.loads(RATE_CARD_PATH.read_text())
        raw = next(value for value in document["entries"] if value["model"] == model)
        today = self._clock().astimezone(timezone.utc).date()
        if not date.fromisoformat(raw["verifiedOn"]) <= today <= date.fromisoformat(raw["validThrough"]):
            raise ProviderAuthorizationBlocked("pricing_approval_expired", "Resume pricing approval is not current.")
        return entry


class ResumeSpendPolicy(ProviderSpendPolicy):
    def __init__(self, card: ResumeRateCard):
        super().__init__(card.approved, _pinned_tokenizer)


ResumeUsageReceipt = ProviderUsageReceipt
