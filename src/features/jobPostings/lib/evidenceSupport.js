import { normalizeText } from "./text.js";

const DEFAULT_EVIDENCE_STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "be",
  "candidate",
  "candidates",
  "experience",
  "familiarity",
  "for",
  "in",
  "knowledge",
  "of",
  "or",
  "required",
  "systems",
  "the",
  "to",
  "with",
  "working",
]);

const DEFAULT_SHORT_TECH_TOKENS = new Set([
  "ai",
  "api",
  "aws",
  "ci",
  "cd",
  "db",
  "go",
  "gcp",
  "js",
  "qa",
  "r",
  "s3",
  "sql",
  "ui",
  "ux",
]);

export function normalizeEvidenceText(value) {
  return normalizeText(value)
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}+#.]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function textSupportsEvidence(sourceText, {
  evidence,
  alternateEvidence,
  minTokenRatio = 0.7,
  requireAllTokensWhenShort = true,
  stopwords = DEFAULT_EVIDENCE_STOPWORDS,
  shortTokens = DEFAULT_SHORT_TECH_TOKENS,
  wholeToken = true,
} = {}) {
  const normalizedSource = normalizeEvidenceText(sourceText);
  if (!normalizedSource) {
    return false;
  }

  const exactCandidates = [evidence, alternateEvidence]
    .map(normalizeEvidenceText)
    .filter(Boolean);
  if (exactCandidates.some((candidate) => normalizedSource.includes(candidate))) {
    return true;
  }

  const tokens = meaningfulEvidenceTokens(evidence || alternateEvidence, {
    stopwords,
    shortTokens,
  });
  if (tokens.length === 0) {
    return false;
  }

  const supportedCount = tokens
    .filter((token) => textContainsToken(normalizedSource, token, { wholeToken }))
    .length;
  const requiredCount = requireAllTokensWhenShort && tokens.length <= 2
    ? tokens.length
    : Math.ceil(tokens.length * minTokenRatio);

  return supportedCount >= requiredCount;
}

export function meaningfulEvidenceTokens(value, {
  stopwords = DEFAULT_EVIDENCE_STOPWORDS,
  shortTokens = DEFAULT_SHORT_TECH_TOKENS,
} = {}) {
  return normalizeEvidenceText(value)
    .split(" ")
    .filter((token) => token && !stopwords.has(token))
    .filter((token) => token.length > 2 || shortTokens.has(token));
}

export function evidenceOverlapScore(left, right) {
  const leftTokens = new Set(meaningfulEvidenceTokens(left, {
    stopwords: new Set(),
    shortTokens: new Set(),
  }));
  const rightTokens = new Set(meaningfulEvidenceTokens(right, {
    stopwords: new Set(),
    shortTokens: new Set(),
  }));

  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0;
  }

  let overlap = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) {
      overlap += 1;
    }
  }

  return overlap / Math.min(leftTokens.size, rightTokens.size);
}

export function findEvidenceIdsForClaim(claim, evidenceItems, {
  minOverlap = 0.18,
  strongOverlap = 0.6,
  maxMatches = 3,
} = {}) {
  const ranked = (evidenceItems || [])
    .map((item) => ({
      evidenceId: item.id,
      score: evidenceOverlapScore(claim, item.text),
    }))
    .filter((item) => item.evidenceId && item.score >= minOverlap)
    .sort((left, right) => right.score - left.score);

  if (ranked[0]?.score >= strongOverlap) {
    return [ranked[0].evidenceId];
  }

  return ranked
    .slice(0, maxMatches)
    .map((item) => item.evidenceId);
}

export function claimSupportedByEvidence(claim, evidenceTexts, {
  minOverlap = 0.18,
} = {}) {
  const supportText = (evidenceTexts || []).filter(Boolean).join("\n");
  if (!supportText) {
    return false;
  }

  if (evidenceOverlapScore(claim, supportText) >= minOverlap) {
    return true;
  }

  const claimNumbers = extractEvidenceNumbers(claim);
  return claimNumbers.length > 0 && claimNumbers.every((value) => supportText.includes(value));
}

export function extractEvidenceNumbers(value) {
  return Array.from(new Set(String(value || "").match(/\b\d+(?:[.,]\d+)?%?\b/g) || []));
}

function textContainsToken(normalizedText, token, { wholeToken }) {
  if (!wholeToken) {
    return normalizedText.includes(token);
  }

  return new RegExp(`(^|\\s)${escapeRegExp(token)}(\\s|$)`).test(normalizedText);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
