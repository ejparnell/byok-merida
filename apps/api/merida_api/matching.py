from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Literal, Protocol, Sequence


EvidenceStrength = Literal[
    "direct evidence",
    "adjacent evidence",
    "weak evidence",
    "no evidence",
]


class MatchTarget(Protocol):
    name: str
    evidence: str
    importance: str


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    text: str
    source_section: str


@dataclass(frozen=True)
class EvidenceMatch:
    target_name: str
    evidence_id: str | None
    strength: EvidenceStrength
    candidate_rank: float


@dataclass(frozen=True)
class MatchingResult:
    score: int
    matches: tuple[EvidenceMatch, ...]
    scoring_policy: str = "matching-v1"


_STRENGTH_VALUES: dict[EvidenceStrength, float] = {
    "direct evidence": 1.0,
    "adjacent evidence": 0.72,
    "weak evidence": 0.25,
    "no evidence": 0.0,
}

_ALIASES = {
    "postgres": "postgresql",
    "postgres sql": "postgresql",
    "rest api": "rest",
    "restful": "rest",
    "continuous integration": "ci",
    "continuous delivery": "cd",
    "javascript": "js",
    "typescript": "ts",
}


class EvidenceMatchingEngine:
    def score(
        self,
        targets: Sequence[MatchTarget],
        evidence_items: Sequence[EvidenceItem],
    ) -> MatchingResult:
        if not targets:
            raise ValueError("At least one matching target is required.")
        matches = tuple(
            self._strongest_match(target, evidence_items) for target in targets
        )
        weights = tuple(_importance_weight(target.importance) for target in targets)
        weighted_score = sum(
            weight * _STRENGTH_VALUES[match.strength]
            for weight, match in zip(weights, matches, strict=True)
        )
        score = round(100 * weighted_score / sum(weights))
        return MatchingResult(score=max(0, min(100, score)), matches=matches)

    def _strongest_match(
        self, target: MatchTarget, evidence_items: Sequence[EvidenceItem]
    ) -> EvidenceMatch:
        target_text = f"{target.name} {target.evidence}"
        candidates = [
            _candidate(target_text, target.name, item) for item in evidence_items
        ]
        if not candidates:
            return EvidenceMatch(target.name, None, "no evidence", 0.0)
        best = max(candidates, key=lambda candidate: candidate[0])
        rank, overlap, coverage, cosine, item = best
        strength = _classify(rank, bool(overlap), coverage, cosine)
        return EvidenceMatch(
            target_name=target.name,
            evidence_id=item.id if strength != "no evidence" else None,
            strength=strength,
            candidate_rank=round(rank, 4),
        )


def _candidate(
    target_text: str, target_name: str, evidence: EvidenceItem
) -> tuple[float, set[str], float, float, EvidenceItem]:
    target_tokens = _tokens(target_text)
    evidence_tokens = _tokens(evidence.text)
    skill_tokens = _tokens(target_name)
    overlap = skill_tokens & evidence_tokens
    coverage = len(target_tokens & evidence_tokens) / max(1, len(target_tokens))
    cosine = _cosine(target_tokens, evidence_tokens)
    section_hint = bool(skill_tokens & _tokens(evidence.source_section))
    rank = min(
        1.0,
        coverage * 0.45
        + cosine * 0.35
        + min(len(overlap), 3) * 0.12
        + (0.08 if section_hint else 0.0),
    )
    return rank, overlap, coverage, cosine, evidence


def _classify(
    rank: float, has_overlap: bool, coverage: float, cosine: float
) -> EvidenceStrength:
    if (
        has_overlap and (coverage >= 0.35 or cosine >= 0.72 or rank >= 0.60)
    ) or (coverage >= 0.55 and cosine >= 0.35):
        return "direct evidence"
    if (
        (has_overlap and coverage >= 0.25)
        or rank >= 0.38
        or cosine >= 0.50
        or coverage >= 0.35
    ):
        return "adjacent evidence"
    if rank >= 0.22 or coverage >= 0.20:
        return "weak evidence"
    return "no evidence"


def _tokens(value: str) -> set[str]:
    normalized = " ".join(
        re.sub(r"[^a-z0-9+#.]+", " ", str(value).lower()).split()
    )
    normalized = _ALIASES.get(normalized, normalized)
    tokens = set(normalized.split())
    return {_ALIASES.get(token, token) for token in tokens if token}


def _cosine(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    left_counts = Counter(left)
    right_counts = Counter(right)
    dot = sum(left_counts[token] * right_counts[token] for token in left_counts & right_counts)
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    return dot / (left_norm * right_norm)


def _importance_weight(importance: str) -> float:
    if importance == "required":
        return 1.5
    if importance == "preferred":
        return 0.8
    if importance == "signal":
        return 0.65
    return 1.0
