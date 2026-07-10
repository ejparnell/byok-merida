import { normalizeText, stripHtml, toPlainSingleLine } from "./text.js";
import { getCapturedUrlPair } from "./url.js";

const TEXT_LIMITS = {
  selectedText: 300000,
  visibleText: 300000,
  semanticHtml: 200000,
};

export function createCaptureEvidence(input) {
  const payload = asObject(input);
  const validationWarnings = [];
  const framePayload = Array.isArray(payload.frames);
  const frames = normalizeFrames(payload, validationWarnings);
  const primary = frames[0] || normalizeFrameEvidence(payload, {}, validationWarnings);
  const merged = mergeFrames(frames.length ? frames : [primary], payload, {
    framePayload,
    validationWarnings,
  });
  const url = selectEvidenceUrl({ payload, frames, primary, framePayload });
  const { jobUrl, capturedUrl } = getCapturedUrlPair(url);
  const selectedText = normalizeText(merged.selectedText);
  const visibleText = normalizeText(merged.visibleText);
  const htmlText = normalizeText(stripHtml(merged.semanticHtml));
  const metadataText = normalizeText(extractMetadataText(merged.metadata));
  const structuredMetadata = extractStructuredMetadata(merged.metadata);
  const debug = createDebug({
    payload,
    framePayload,
    frames,
    url,
    pageTitle: merged.pageTitle,
    selectedText,
    visibleText,
    htmlText,
    semanticHtml: merged.semanticHtml,
    metadataText,
    metadata: merged.metadata,
    validationWarnings,
  });

  return {
    url,
    jobUrl,
    capturedUrl,
    tabUrl: toText(payload.tabUrl),
    pageUrl: merged.pageUrl,
    pageTitle: merged.pageTitle,
    selectedText,
    visibleText,
    semanticHtml: merged.semanticHtml,
    metadata: merged.metadata,
    structuredMetadata,
    content: {
      selectedText,
      visibleText,
      htmlText,
      metadataText,
      preferredText: selectedText || visibleText || htmlText || metadataText,
    },
    debug,
    summary: {
      url,
      tabUrl: toText(payload.tabUrl),
      pageTitle: merged.pageTitle,
      frameCount: debug.frameCount,
      selectedTextLength: selectedText.length,
      visibleTextLength: visibleText.length,
      semanticHtmlLength: merged.semanticHtml.length,
      jsonLdCount: Array.isArray(merged.metadata?.jsonLd) ? merged.metadata.jsonLd.length : 0,
      selectedSample: debug.selectedSample,
      visibleSample: debug.visibleSample,
      validationWarnings,
    },
  };
}

function normalizeFrames(payload, validationWarnings) {
  if (Array.isArray(payload.frames)) {
    return payload.frames
      .map((frame) => normalizeFramePayload(frame, validationWarnings))
      .filter(hasFrameEvidence);
  }

  if (payload.frames !== undefined) {
    validationWarnings.push("Capture Evidence frames must be an array.");
  }

  return [normalizeFrameEvidence(payload, {}, validationWarnings)].filter(hasFrameEvidence);
}

function normalizeFramePayload(frame, validationWarnings) {
  const frameObject = asObject(frame);
  const evidence = asObject(frameObject.result || frameObject);
  return normalizeFrameEvidence(evidence, {
    frameId: frameObject.frameId,
    documentId: frameObject.documentId,
  }, validationWarnings);
}

function normalizeFrameEvidence(evidence, adapterDebug, validationWarnings) {
  return {
    frameId: adapterDebug.frameId,
    documentId: adapterDebug.documentId,
    url: toText(evidence.url),
    pageUrl: toText(evidence.pageUrl),
    capturedUrl: toText(evidence.capturedUrl),
    pageTitle: toPlainSingleLine(evidence.pageTitle),
    selectedText: limitText(toText(evidence.selectedText), TEXT_LIMITS.selectedText, "selectedText", validationWarnings),
    visibleText: limitText(toText(evidence.visibleText), TEXT_LIMITS.visibleText, "visibleText", validationWarnings),
    semanticHtml: limitText(toText(evidence.semanticHtml), TEXT_LIMITS.semanticHtml, "semanticHtml", validationWarnings),
    metadata: normalizeMetadata(evidence.metadata),
    debug: asObject(evidence.debug),
  };
}

function mergeFrames(frames, payload, { framePayload, validationWarnings }) {
  const selectedText = joinUnique(frames.map((frame) => frame.selectedText));
  const visibleText = joinUnique(frames.map((frame) => frame.visibleText));
  const semanticHtml = joinUnique(frames.map((frame) => frame.semanticHtml));

  return {
    pageUrl: firstPresent(frames.map((frame) => frame.pageUrl)),
    pageTitle: firstPresent(frames.map((frame) => frame.pageTitle)),
    selectedText: limitText(selectedText, TEXT_LIMITS.selectedText, "selectedText", validationWarnings),
    visibleText: limitText(visibleText, TEXT_LIMITS.visibleText, "visibleText", validationWarnings),
    semanticHtml: limitText(semanticHtml, TEXT_LIMITS.semanticHtml, "semanticHtml", validationWarnings),
    metadata: mergeMetadata([
      ...(framePayload ? [payload.metadata] : []),
      ...frames.map((frame) => frame.metadata),
    ]),
  };
}

function selectEvidenceUrl({ payload, frames, primary, framePayload }) {
  const frameCandidates = [
    primary.url,
    primary.pageUrl,
    primary.capturedUrl,
    ...frames.flatMap((frame) => [frame.url, frame.pageUrl, frame.capturedUrl]),
  ];
  const payloadCandidates = [
    payload.url,
    payload.tabUrl,
    payload.pageUrl,
    payload.capturedUrl,
  ];
  const candidates = framePayload
    ? [payload.tabUrl, ...frameCandidates, ...payloadCandidates]
    : [...payloadCandidates, ...frameCandidates];

  return candidates.find((candidate) => getCapturedUrlPair(candidate).jobUrl)
    || candidates.find(Boolean)
    || "";
}

function createDebug({
  payload,
  framePayload,
  frames,
  url,
  pageTitle,
  selectedText,
  visibleText,
  htmlText,
  semanticHtml,
  metadataText,
  metadata,
  validationWarnings,
}) {
  const payloadDebug = asObject(payload.debug);
  const frameCount = framePayload
    ? frames.length
    : Number(payloadDebug.frameCount || frames.length || 0);

  return {
    ...payloadDebug,
    url,
    pageTitle,
    frameCount,
    selectedTextLength: selectedText.length,
    visibleTextLength: visibleText.length,
    htmlTextLength: htmlText.length,
    semanticHtmlLength: semanticHtml.length,
    metadataTextLength: metadataText.length,
    jsonLdCount: Array.isArray(metadata?.jsonLd) ? metadata.jsonLd.length : 0,
    selectedSample: debugSample(selectedText),
    visibleSample: debugSample(visibleText),
    htmlTextSample: debugSample(htmlText),
    metadataSample: debugSample(metadataText),
    frameSummaries: framePayload ? frames.map(frameSummary) : payloadDebug.frameSummaries,
    validationWarnings,
  };
}

function frameSummary(frame, index) {
  return {
    index,
    frameId: frame.frameId,
    documentId: frame.documentId,
    url: frame.url || "",
    pageTitle: frame.pageTitle || "",
    selectedTextLength: frame.selectedText.length,
    visibleTextLength: frame.visibleText.length,
    semanticHtmlLength: frame.semanticHtml.length,
    jsonLdCount: Array.isArray(frame.metadata?.jsonLd) ? frame.metadata.jsonLd.length : 0,
    visibleSample: debugSample(frame.visibleText),
  };
}

function extractStructuredMetadata(metadata) {
  const result = {
    jobTitle: "",
    companyName: "",
    location: "",
    matched: false,
  };

  const jsonLdEntries = Array.isArray(metadata?.jsonLd) ? metadata.jsonLd : [];
  const jobPosting = jsonLdEntries.flatMap(flattenJsonLd).find(isJobPostingJsonLd);

  if (jobPosting) {
    result.jobTitle = toPlainSingleLine(jobPosting.title || jobPosting.name);
    result.companyName = toPlainSingleLine(
      jobPosting.hiringOrganization?.name
        || jobPosting.organization?.name
        || jobPosting.employerOverview?.name,
    );
    result.location = toPlainSingleLine(formatJsonLdLocation(jobPosting));
    result.matched = true;
  }

  if (!result.jobTitle) {
    result.jobTitle = toPlainSingleLine(metadata?.openGraph?.title || metadata?.meta?.title);
  }

  if (!result.companyName) {
    result.companyName = toPlainSingleLine(metadata?.openGraph?.siteName || metadata?.meta?.site_name);
  }

  return result;
}

function extractMetadataText(metadata) {
  const parts = [
    metadata?.openGraph?.description,
    metadata?.meta?.description,
    metadata?.meta?.["twitter:description"],
  ];

  for (const entry of Array.isArray(metadata?.jsonLd) ? metadata.jsonLd.flatMap(flattenJsonLd) : []) {
    if (isJobPostingJsonLd(entry)) {
      parts.push(entry.description);
      parts.push(entry.responsibilities);
      parts.push(entry.qualifications);
      parts.push(entry.skills);
    }
  }

  return parts.filter(Boolean).join("\n\n");
}

function normalizeMetadata(metadata) {
  return {
    meta: asObject(metadata?.meta),
    openGraph: asObject(metadata?.openGraph),
    jsonLd: Array.isArray(metadata?.jsonLd) ? metadata.jsonLd : [],
  };
}

function mergeMetadata(metadataEntries) {
  const merged = {
    meta: {},
    openGraph: {},
    jsonLd: [],
  };

  for (const metadata of metadataEntries) {
    const normalized = normalizeMetadata(metadata);
    Object.assign(merged.meta, normalized.meta);
    Object.assign(merged.openGraph, normalized.openGraph);
    merged.jsonLd.push(...normalized.jsonLd);
  }

  return merged;
}

function flattenJsonLd(entry) {
  if (!entry) {
    return [];
  }

  if (Array.isArray(entry)) {
    return entry.flatMap(flattenJsonLd);
  }

  if (Array.isArray(entry["@graph"])) {
    return [entry, ...entry["@graph"].flatMap(flattenJsonLd)];
  }

  return [entry];
}

function isJobPostingJsonLd(entry) {
  const type = entry?.["@type"];
  const types = Array.isArray(type) ? type : [type];
  return types.some((value) => String(value || "").toLowerCase() === "jobposting");
}

function formatJsonLdLocation(jobPosting) {
  if (jobPosting.jobLocationType === "TELECOMMUTE") {
    const requirement = Array.isArray(jobPosting.applicantLocationRequirements)
      ? jobPosting.applicantLocationRequirements.map((item) => item?.name).filter(Boolean).join(", ")
      : jobPosting.applicantLocationRequirements?.name;
    return requirement ? `Remote - ${requirement}` : "Remote";
  }

  const locations = Array.isArray(jobPosting.jobLocation)
    ? jobPosting.jobLocation
    : [jobPosting.jobLocation].filter(Boolean);

  return locations
    .map((location) => {
      const address = location?.address || location;
      return [
        address?.addressLocality,
        address?.addressRegion,
        address?.addressCountry,
      ].filter(Boolean).join(", ");
    })
    .filter(Boolean)
    .join("; ");
}

function firstPresent(values) {
  return values.map((value) => toPlainSingleLine(value)).find(Boolean) || "";
}

function joinUnique(values) {
  const seen = new Set();
  const parts = [];

  for (const value of values) {
    const text = toText(value).trim();
    if (!text || seen.has(text)) {
      continue;
    }
    seen.add(text);
    parts.push(text);
  }

  return parts.join("\n\n");
}

function limitText(value, maxLength, label, validationWarnings) {
  const text = toText(value);
  if (text.length <= maxLength) {
    return text;
  }

  validationWarnings.push(`${label} exceeded ${maxLength} characters and was truncated.`);
  return text.slice(0, maxLength);
}

function hasFrameEvidence(frame) {
  return Boolean(
    frame.url
      || frame.pageUrl
      || frame.capturedUrl
      || frame.pageTitle
      || frame.selectedText
      || frame.visibleText
      || frame.semanticHtml
      || frame.metadata?.jsonLd?.length
      || Object.keys(frame.metadata?.meta || {}).length
      || Object.keys(frame.metadata?.openGraph || {}).length,
  );
}

function debugSample(value) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 240);
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function toText(value) {
  return String(value || "");
}
