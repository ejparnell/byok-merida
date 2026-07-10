import { REVIEW_CONFIDENCE_THRESHOLD } from "../types/contracts.js";
import { createCaptureEvidence } from "./captureEvidence.js";
import { normalizeText, firstNonEmptyLine, toPlainSingleLine } from "./text.js";

export function parseCaptureEvidence(evidence) {
  const captureEvidence = createCaptureEvidence(evidence);
  const metadata = captureEvidence.structuredMetadata;
  const jobContent = cleanJobContent(captureEvidence.content.preferredText);

  const pageTitle = toPlainSingleLine(captureEvidence.pageTitle);
  const titleParts = splitTitleAndCompany(pageTitle);
  const jobTitle = firstPresent(
    metadata.jobTitle,
    titleParts.jobTitle,
    extractLabeledValue(jobContent, ["job title", "role", "position"]),
    firstLikelyTitleLine(jobContent),
  );
  const companyName = firstPresent(
    metadata.companyName,
    titleParts.companyName,
    extractLabeledValue(jobContent, ["company", "organization"]),
  );
  const location = firstPresent(
    metadata.location,
    extractLabeledValue(jobContent, ["location", "work location"]),
    extractRemoteLocation(jobContent),
  );
  const domain = hostnameFromUrl(captureEvidence.jobUrl || captureEvidence.url);
  const jobPostingTitle = buildJobPostingTitle({ jobTitle, companyName, domain });
  const notes = [];

  if (!captureEvidence.content.selectedText) {
    notes.push("No selected text was provided; parsed from the rendered page.");
  }

  if (!companyName) {
    notes.push("Company name was not confidently parsed.");
  }

  if (!jobTitle) {
    notes.push("Job title was not confidently parsed.");
  }

  if (!location) {
    notes.push("Location was not confidently parsed.");
  }

  if (jobContent.length > 0 && jobContent.length < 400) {
    notes.push("Captured job content is short; hidden sections may need to be expanded.");
  }

  const confidence = calculateConfidence({
    selectedText: captureEvidence.content.selectedText,
    visibleText: captureEvidence.content.visibleText,
    jobContent,
    jobTitle,
    companyName,
    location,
    metadata,
  });

  return {
    jobPostingTitle,
    jobUrl: captureEvidence.jobUrl,
    capturedUrl: captureEvidence.capturedUrl,
    companyName,
    jobTitle,
    location,
    jobContent,
    parsingNotes: notes,
    needsReview: confidence < REVIEW_CONFIDENCE_THRESHOLD,
    confidence,
    evidenceDebug: captureEvidence.debug,
  };
}

export function publicParsedJobPosting(parsed) {
  return {
    jobPostingTitle: parsed.jobPostingTitle || "",
    jobUrl: parsed.jobUrl || "",
    capturedUrl: parsed.capturedUrl || "",
    companyName: parsed.companyName || "",
    jobTitle: parsed.jobTitle || "",
    location: parsed.location || "",
    jobContent: parsed.jobContent || "",
    parsingNotes: Array.isArray(parsed.parsingNotes) ? parsed.parsingNotes : [],
    needsReview: Boolean(parsed.needsReview),
  };
}

export function hasMinimumCreationFields(parsed) {
  return Boolean(
    normalizeText(parsed?.jobPostingTitle)
      && normalizeText(parsed?.jobUrl)
      && normalizeText(parsed?.jobContent),
  );
}

function cleanJobContent(text) {
  return normalizeText(text)
    .split("\n")
    .map((line) => line.trim())
    .filter((line, index, lines) => !(line === "" && lines[index - 1] === ""))
    .join("\n")
    .trim();
}

function splitTitleAndCompany(pageTitle) {
  const title = toPlainSingleLine(pageTitle);
  if (!title) {
    return {};
  }

  const hiringMatch = title.match(/^(.+?)\s+hiring\s+(.+?)(?:\s+in\s+.+)?$/i);
  if (hiringMatch) {
    return {
      companyName: cleanupTitlePart(hiringMatch[1]),
      jobTitle: cleanupTitlePart(hiringMatch[2]),
    };
  }

  const atMatch = title.match(/^(.+?)\s+at\s+(.+?)(?:\s+[|-].+)?$/i);
  if (atMatch) {
    return {
      jobTitle: cleanupTitlePart(atMatch[1]),
      companyName: cleanupTitlePart(atMatch[2]),
    };
  }

  for (const separator of [" | ", " - ", " \u2014 ", " \u2013 "]) {
    if (title.includes(separator)) {
      const [left, right] = title.split(separator).map(cleanupTitlePart);
      if (left && right) {
        return inferTitleCompanyFromPair(left, right);
      }
    }
  }

  return { jobTitle: cleanupTitlePart(title) };
}

function inferTitleCompanyFromPair(left, right) {
  const noisyBrands = /linkedin|indeed|greenhouse|lever|workday|ashby|jobs|careers/i;
  if (noisyBrands.test(right)) {
    return { jobTitle: left };
  }

  if (/\b(engineer|developer|designer|manager|director|analyst|specialist|lead|product|software|frontend|backend|fullstack)\b/i.test(left)) {
    return { jobTitle: left, companyName: right };
  }

  return { jobTitle: right, companyName: left };
}

function cleanupTitlePart(value) {
  return toPlainSingleLine(value)
    .replace(/\b(job|careers?|opening|position)\b$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function extractLabeledValue(text, labels) {
  const lines = normalizeText(text).split("\n");
  for (const line of lines.slice(0, 80)) {
    for (const label of labels) {
      const expression = new RegExp(`^${escapeRegExp(label)}\\s*[:\\-]\\s*(.+)$`, "i");
      const match = line.match(expression);
      if (match?.[1]) {
        return toPlainSingleLine(match[1], 180);
      }
    }
  }

  return "";
}

function firstLikelyTitleLine(text) {
  const line = firstNonEmptyLine(text);
  if (!line || line.length > 140 || /^(about|overview|description|who we are)$/i.test(line)) {
    return "";
  }
  return toPlainSingleLine(line);
}

function extractRemoteLocation(text) {
  const lines = normalizeText(text).split("\n").slice(0, 100);
  const remoteLine = lines.find((line) => /\b(remote|hybrid|onsite|on-site)\b/i.test(line) && line.length < 140);
  return remoteLine ? toPlainSingleLine(remoteLine) : "";
}

function buildJobPostingTitle({ jobTitle, companyName, domain }) {
  if (jobTitle && companyName) {
    return `${jobTitle} at ${companyName}`;
  }

  if (jobTitle) {
    return jobTitle;
  }

  if (companyName) {
    return `Job posting at ${companyName}`;
  }

  return domain ? `Job posting from ${domain}` : "Unparsed job posting";
}

function hostnameFromUrl(input) {
  try {
    return new URL(input).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function calculateConfidence({ selectedText, visibleText, jobContent, jobTitle, companyName, location, metadata }) {
  let score = 0;

  if (selectedText.length >= 300) score += 0.35;
  else if (visibleText.length >= 500) score += 0.25;
  else if (jobContent.length >= 200) score += 0.15;

  if (jobContent.length >= 1000) score += 0.1;
  if (jobTitle) score += 0.2;
  if (companyName) score += 0.15;
  if (location) score += 0.1;
  if (metadata.matched) score += 0.15;

  return Math.min(1, Number(score.toFixed(2)));
}

function firstPresent(...values) {
  return values.map((value) => toPlainSingleLine(value)).find(Boolean) || "";
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
