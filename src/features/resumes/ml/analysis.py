import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "by", "for", "from", "in",
    "into", "is", "of", "on", "or", "that", "the", "to", "with", "you",
    "your", "we", "will", "work", "working", "experience", "skills",
}

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "data" / "skill-normalization.json"


def load_normalization_dictionary(path=DEFAULT_DICTIONARY_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    alias_to_skill = {}
    skills = []
    for entry in data.get("skills", []):
        canonical = entry.get("canonical", "").strip()
        if not canonical:
            continue
        aliases = set(entry.get("aliases", []))
        aliases.add(canonical)
        normalized_aliases = sorted({normalize_phrase(alias) for alias in aliases if alias})
        skill = {
            "canonical": canonical,
            "category": entry.get("category", "Other"),
            "aliases": normalized_aliases,
        }
        skills.append(skill)
        for alias in normalized_aliases:
            alias_to_skill[alias] = skill

    return {
        "version": data.get("version", 1),
        "skills": skills,
        "alias_to_skill": alias_to_skill,
    }


def normalize_phrase(value):
    return " ".join(tokenize(value))


def tokenize(value):
    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(str(value or ""))]
    return [token for token in tokens if token and token not in STOPWORDS]


def extract_signals(text, dictionary):
    normalized = f" {normalize_phrase(text)} "
    found = []
    seen = set()
    for skill in dictionary["skills"]:
        for alias in skill["aliases"]:
            if alias and f" {alias} " in normalized and skill["canonical"] not in seen:
                found.append({
                    "name": skill["canonical"],
                    "category": skill["category"],
                    "matchedAlias": alias,
                })
                seen.add(skill["canonical"])
    return found


def keyword_coverage(requirement_text, evidence_text):
    requirement_tokens = set(tokenize(requirement_text))
    if not requirement_tokens:
        return 0.0
    evidence_tokens = set(tokenize(evidence_text))
    return len(requirement_tokens & evidence_tokens) / len(requirement_tokens)


def vectorize(texts):
    docs = [tokenize(text) for text in texts]
    doc_count = len(docs)
    doc_freq = Counter()
    for tokens in docs:
        doc_freq.update(set(tokens))

    vectors = []
    for tokens in docs:
        counts = Counter(tokens)
        vector = {}
        for token, count in counts.items():
            idf = math.log((1 + doc_count) / (1 + doc_freq[token])) + 1
            vector[token] = count * idf
        vectors.append(vector)
    return vectors


def cosine_similarity(left, right):
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def candidate_matches(requirements, evidence_items, dictionary):
    texts = [requirement_match_text(requirement) for requirement in requirements]
    texts.extend(item_text(item) for item in evidence_items)
    vectors = vectorize(texts)
    requirement_vectors = vectors[:len(requirements)]
    evidence_vectors = vectors[len(requirements):]
    output = []

    for req_index, requirement in enumerate(requirements):
        requirement_text = requirement_match_text(requirement)
        requirement_signals = extract_signals(requirement_signal_text(requirement), dictionary)
        requirement_skill_names = {signal["name"] for signal in requirement_signals}
        matches = []

        for evidence_index, evidence in enumerate(evidence_items):
            evidence_text = item_text(evidence)
            evidence_signals = extract_signals(evidence_text, dictionary)
            evidence_skill_names = {signal["name"] for signal in evidence_signals}
            normalized_overlap = sorted(requirement_skill_names & evidence_skill_names)
            lexical = max(
                keyword_coverage(requirement_text, evidence_text),
                keyword_coverage(requirement_evidence_text(requirement), evidence_text),
            )
            tfidf = cosine_similarity(requirement_vectors[req_index], evidence_vectors[evidence_index])
            section_hint = section_category_hint(requirement, evidence)

            if normalized_overlap or lexical >= 0.12 or tfidf >= 0.08 or section_hint:
                matches.append({
                    "evidenceId": evidence.get("id", f"evidence-{evidence_index + 1}"),
                    "keywordCoverage": round(lexical, 4),
                    "tfidfSimilarity": round(tfidf, 4),
                    "normalizedSkillOverlap": normalized_overlap,
                    "sectionHint": section_hint,
                    "score": round(candidate_score(lexical, tfidf, normalized_overlap, section_hint), 4),
                })

        if not matches:
            for evidence_index, evidence in enumerate(evidence_items):
                evidence_text = item_text(evidence)
                tfidf = cosine_similarity(requirement_vectors[req_index], evidence_vectors[evidence_index])
                if tfidf > 0:
                    matches.append({
                        "evidenceId": evidence.get("id", f"evidence-{evidence_index + 1}"),
                        "keywordCoverage": round(keyword_coverage(requirement_text, evidence_text), 4),
                        "tfidfSimilarity": round(tfidf, 4),
                        "normalizedSkillOverlap": [],
                        "sectionHint": False,
                        "score": round(tfidf * 0.35, 4),
                    })

        matches.sort(key=lambda match: match["score"], reverse=True)
        output.append({
            "requirementId": requirement.get("id", f"requirement-{req_index + 1}"),
            "signals": requirement_signals,
            "matches": matches[:8],
        })

    return output


def score_fit(requirements, evidence_items, candidates, semantic_similarities=None):
    evidence_by_id = {item.get("id", f"evidence-{index + 1}"): item for index, item in enumerate(evidence_items)}
    candidate_by_requirement = {candidate["requirementId"]: candidate for candidate in candidates}
    requirement_scores = []
    category_totals = defaultdict(lambda: {"score": 0.0, "weight": 0.0, "count": 0})
    gaps = []

    for index, requirement in enumerate(requirements):
        requirement_id = requirement.get("id", f"requirement-{index + 1}")
        candidate = candidate_by_requirement.get(requirement_id, {"matches": []})
        matches = []
        best_strength = "no evidence"
        best_score = 0.0

        for match in candidate.get("matches", []):
            evidence = evidence_by_id.get(match.get("evidenceId"))
            if not evidence:
                continue
            semantic = semantic_similarity(requirement_id, match["evidenceId"], match, semantic_similarities)
            combined = combined_score(match, semantic)
            strength = classify_strength(match, semantic, combined)
            best_score = max(best_score, combined)
            best_strength = stronger_strength(best_strength, strength)
            matches.append({
                **match,
                "semanticSimilarity": round(semantic, 4),
                "combinedScore": round(combined, 4),
                "evidenceStrength": strength,
                "evidenceText": evidence.get("text", ""),
                "sourceSection": evidence.get("sourceSection", ""),
            })

        weight = requirement_weight(requirement)
        score_value = strength_score(best_strength) * weight
        category = requirement.get("category") or requirement.get("type") or "Other"
        category_totals[category]["score"] += score_value
        category_totals[category]["weight"] += weight
        category_totals[category]["count"] += 1

        if best_strength in {"weak evidence", "no evidence"}:
            gaps.append({
                "requirementId": requirement_id,
                "text": requirement.get("text", ""),
                "category": category,
                "evidenceStrength": best_strength,
            })

        requirement_scores.append({
            "requirementId": requirement_id,
            "text": requirement.get("text", ""),
            "type": requirement.get("type", ""),
            "category": category,
            "importance": requirement.get("importance", "preferred"),
            "weight": weight,
            "evidenceStrength": best_strength,
            "fitScore": round(score_value, 4),
            "matches": matches[:5],
        })

    total_weight = sum(item["weight"] for item in requirement_scores)
    total_score = sum(item["fitScore"] for item in requirement_scores)
    overall = total_score / total_weight if total_weight else 0.0
    categories = []
    for category, values in sorted(category_totals.items()):
        score = values["score"] / values["weight"] if values["weight"] else 0.0
        categories.append({
            "category": category,
            "fitScore": round(score, 4),
            "requirementCount": values["count"],
        })

    return {
        "overallFitScore": round(overall, 4),
        "categoryScores": categories,
        "requirements": requirement_scores,
        "gaps": gaps,
        "generationAllowed": generation_allowed(requirement_scores),
    }


def item_text(item):
    return str(item.get("text") or item.get("name") or "")


def requirement_match_text(requirement):
    evidence = str(requirement.get("evidence") or "").strip()
    text = item_text(requirement).strip()
    if evidence and text and normalize_phrase(evidence) != normalize_phrase(text):
        return f"{evidence} {text}"
    return evidence or text


def requirement_evidence_text(requirement):
    return str(requirement.get("evidence") or "").strip()


def requirement_signal_text(requirement):
    return " ".join(
        value for value in [
            requirement_match_text(requirement),
            item_text(requirement),
        ]
        if value
    )


def section_category_hint(requirement, evidence):
    left = str(requirement.get("category") or requirement.get("type") or "").lower()
    right = str(evidence.get("sourceSection") or evidence.get("type") or "").lower()
    return bool(left and right and (left in right or right in left))


def candidate_score(lexical, tfidf, normalized_overlap, section_hint):
    return min(1.0, lexical * 0.45 + tfidf * 0.35 + min(len(normalized_overlap), 3) * 0.12 + (0.08 if section_hint else 0))


def semantic_similarity(requirement_id, evidence_id, match, semantic_similarities):
    if not semantic_similarities:
        return float(match.get("tfidfSimilarity", 0.0))
    key = f"{requirement_id}:{evidence_id}"
    if key in semantic_similarities:
        return float(semantic_similarities[key])
    return float(match.get("tfidfSimilarity", 0.0))


def combined_score(match, semantic):
    return min(1.0, match.get("keywordCoverage", 0) * 0.3 + match.get("tfidfSimilarity", 0) * 0.25 + semantic * 0.35 + min(len(match.get("normalizedSkillOverlap", [])), 3) * 0.1)


def classify_strength(match, semantic, combined):
    if match.get("normalizedSkillOverlap") and (match.get("keywordCoverage", 0) >= 0.35 or semantic >= 0.72 or combined >= 0.6):
        return "direct evidence"
    if match.get("keywordCoverage", 0) >= 0.55 and (match.get("tfidfSimilarity", 0) >= 0.35 or semantic >= 0.35):
        return "direct evidence"
    if match.get("normalizedSkillOverlap") and match.get("keywordCoverage", 0) >= 0.25:
        return "adjacent evidence"
    if combined >= 0.38 or semantic >= 0.5 or match.get("keywordCoverage", 0) >= 0.35:
        return "adjacent evidence"
    if combined >= 0.22 or match.get("keywordCoverage", 0) >= 0.2:
        return "weak evidence"
    return "no evidence"


def stronger_strength(left, right):
    order = ["no evidence", "weak evidence", "adjacent evidence", "direct evidence"]
    return right if order.index(right) > order.index(left) else left


def strength_score(strength):
    return {
        "direct evidence": 1.0,
        "adjacent evidence": 0.72,
        "weak evidence": 0.25,
        "no evidence": 0.0,
    }.get(strength, 0.0)


def requirement_weight(requirement):
    importance = str(requirement.get("importance") or "").lower()
    req_type = str(requirement.get("type") or "").lower()
    if importance == "required" or "required" in req_type:
        return 1.5
    if "responsibility" in req_type:
        return 1.35
    if "preferred" in req_type:
        return 0.8
    if "domain" in req_type or "seniority" in req_type or "work-style" in req_type:
        return 0.65
    return 1.0


def generation_allowed(requirement_scores):
    required = [
        item for item in requirement_scores
        if item["importance"] == "required" or "required" in item["type"] or "responsibility" in item["type"]
    ]
    supported_required = [
        item for item in required
        if item["evidenceStrength"] in {"direct evidence", "adjacent evidence"}
    ]
    supported_any = [
        item for item in requirement_scores
        if item["evidenceStrength"] in {"direct evidence", "adjacent evidence"}
    ]
    if not supported_any:
        return False
    if required and not supported_required:
        return False
    return True
