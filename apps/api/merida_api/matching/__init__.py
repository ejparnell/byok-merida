from collections import Counter
from dataclasses import dataclass
from importlib.resources import files
import json
import math
import re
from typing import Literal, Protocol, Sequence


EvidenceStrength = Literal[
    "direct evidence",
    "adjacent evidence",
    "weak evidence",
    "no evidence",
]
SCORING_POLICY_VERSION = "matching-v1"


class MatchTarget(Protocol):
    name: str
    evidence: str
    importance: str


class EvidenceBlock(Protocol):
    kind: str
    text: str


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
    scoring_policy: str


@dataclass(frozen=True)
class ScoringPolicy:
    version: str
    strength_values: dict[EvidenceStrength, float]
    importance_weights: dict[str, float]
    type_weights: dict[str, float]

    def weight_for(self, target: MatchTarget) -> float:
        target_type = getattr(target, "type", "")
        if target.importance == "required" or target_type == "required skill":
            return self.importance_weights["required"]
        if target_type == "responsibility":
            return self.type_weights[target_type]
        if target.importance == "preferred" or target_type == "preferred skill":
            return self.importance_weights["preferred"]
        if target.importance == "signal" or target_type in {
            "domain signal",
            "seniority signal",
            "work-style signal",
        }:
            return self.importance_weights["signal"]
        return self.importance_weights["default"]


@dataclass(frozen=True)
class _Candidate:
    item: EvidenceItem
    rank: float
    overlap: frozenset[str]
    coverage: float
    tfidf_cosine: float


_POLICY = json.loads(
    files(__package__).joinpath("skill_normalization.v1.json").read_text()
)
if _POLICY.get("version") != "skill-normalization-v1":
    raise RuntimeError("Unsupported Matching normalization policy version.")
_ALIASES: dict[str, str] = _POLICY["aliases"]
_STOPWORDS = frozenset(_POLICY["stopwords"])
MATCHING_V1 = ScoringPolicy(
    version=SCORING_POLICY_VERSION,
    strength_values={
        "direct evidence": 1.0,
        "adjacent evidence": 0.72,
        "weak evidence": 0.25,
        "no evidence": 0.0,
    },
    importance_weights={
        "required": 1.5,
        "preferred": 0.8,
        "signal": 0.65,
        "default": 1.0,
    },
    type_weights={
        "required skill": 1.5,
        "responsibility": 1.35,
        "preferred skill": 0.8,
        "domain signal": 0.65,
        "seniority signal": 0.65,
        "work-style signal": 0.65,
    },
)


class EvidenceMatchingEngine:
    def match(
        self,
        targets: Sequence[MatchTarget],
        evidence_items: Sequence[EvidenceItem],
        scoring_policy: ScoringPolicy,
    ) -> MatchingResult:
        if not targets:
            raise ValueError("At least one matching target is required.")
        matches = tuple(
            self._strongest_match(target, evidence_items) for target in targets
        )
        weights = tuple(scoring_policy.weight_for(target) for target in targets)
        weighted_score = sum(
            weight * scoring_policy.strength_values[match.strength]
            for weight, match in zip(weights, matches, strict=True)
        )
        score = round(100 * weighted_score / sum(weights))
        return MatchingResult(
            score=max(0, min(100, score)),
            matches=matches,
            scoring_policy=scoring_policy.version,
        )

    def _strongest_match(
        self, target: MatchTarget, evidence_items: Sequence[EvidenceItem]
    ) -> EvidenceMatch:
        candidates = _ranked_candidates(target, evidence_items)
        if not candidates:
            return EvidenceMatch(target.name, None, "no evidence", 0.0)
        best = candidates[0]
        strength = _classify(
            best.rank,
            bool(best.overlap),
            best.coverage,
            best.tfidf_cosine,
        )
        return EvidenceMatch(
            target_name=target.name,
            evidence_id=best.item.id if strength != "no evidence" else None,
            strength=strength,
            candidate_rank=round(best.rank, 4),
        )

    def ranked_matches(
        self,
        target: MatchTarget,
        evidence_items: Sequence[EvidenceItem],
        *,
        limit: int = 5,
    ) -> tuple[EvidenceMatch, ...]:
        return tuple(
            EvidenceMatch(
                target_name=target.name,
                evidence_id=(
                    candidate.item.id
                    if (
                        strength := _classify(
                            candidate.rank,
                            bool(candidate.overlap),
                            candidate.coverage,
                            candidate.tfidf_cosine,
                        )
                    )
                    != "no evidence"
                    else None
                ),
                strength=strength,
                candidate_rank=round(candidate.rank, 4),
            )
            for candidate in _ranked_candidates(target, evidence_items)[:limit]
        )


def evidence_items_from_blocks(
    record_id: str, blocks: Sequence[EvidenceBlock]
) -> tuple[EvidenceItem, ...]:
    section = "Master Resume"
    evidence = []
    for index, block in enumerate(blocks, start=1):
        if block.kind in {"heading_1", "heading_2", "heading_3"}:
            section = block.text
        evidence.append(
            EvidenceItem(
                id=f"{record_id}:block-{index}",
                text=block.text,
                source_section=section,
            )
        )
    return tuple(evidence)


def _ranked_candidates(
    target: MatchTarget, evidence_items: Sequence[EvidenceItem]
) -> tuple[_Candidate, ...]:
    target_tokens = _tokens(f"{target.name} {target.evidence}")
    skill_tokens = _tokens(target.name)
    evidence_tokens = tuple(_tokens(item.text) for item in evidence_items)
    idf = _idf((target_tokens, *evidence_tokens))
    candidates = []
    fallback = []
    for item, item_tokens in zip(evidence_items, evidence_tokens, strict=True):
        overlap = frozenset(skill_tokens & item_tokens)
        coverage = len(target_tokens & item_tokens) / max(1, len(target_tokens))
        cosine = _tfidf_cosine(target_tokens, item_tokens, idf)
        section_hint = bool(skill_tokens & _tokens(item.source_section))
        rank = min(
            1.0,
            coverage * 0.45
            + cosine * 0.35
            + min(len(overlap), 3) * 0.12
            + (0.08 if section_hint else 0.0),
        )
        candidate = _Candidate(item, rank, overlap, coverage, cosine)
        if overlap or coverage >= 0.12 or cosine >= 0.08 or section_hint:
            candidates.append(candidate)
        elif cosine > 0:
            fallback.append(candidate)
    selected = candidates or fallback
    selected.sort(key=lambda item: (-item.rank, item.item.id))
    return tuple(selected[:8])


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


def _tokens(value: str) -> frozenset[str]:
    normalized = " ".join(
        re.sub(r"[^a-z0-9+#.]+", " ", str(value).lower()).split()
    )
    for alias, canonical in sorted(
        _ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        normalized = re.sub(
            rf"(?<![a-z0-9+#.]){re.escape(alias)}(?![a-z0-9+#.])",
            canonical,
            normalized,
        )
    return frozenset(
        token for token in normalized.split() if token and token not in _STOPWORDS
    )


def _idf(documents: Sequence[frozenset[str]]) -> dict[str, float]:
    document_count = len(documents)
    frequency = Counter(token for document in documents for token in document)
    return {
        token: math.log((1 + document_count) / (1 + count)) + 1
        for token, count in frequency.items()
    }


def _tfidf_cosine(
    left: frozenset[str], right: frozenset[str], idf: dict[str, float]
) -> float:
    if not left or not right:
        return 0.0
    dot = sum(idf[token] ** 2 for token in left & right)
    left_norm = math.sqrt(sum(idf[token] ** 2 for token in left))
    right_norm = math.sqrt(sum(idf[token] ** 2 for token in right))
    return dot / (left_norm * right_norm)
