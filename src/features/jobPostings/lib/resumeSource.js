import {
  APPLICATION_STATUS_TO_APPLY,
  JOB_POSTING_RESUME_RELATION,
  NOTION_PROPERTIES,
} from "../types/contracts.js";
import {
  ANALYSIS_HEADING,
  blockPlainText,
  extractJobContentFromBlocks,
} from "./analysisBlocks.js";
import { normalizeText } from "./text.js";

export { JOB_POSTING_RESUME_RELATION };

export function buildResumeCreationQueueFilter() {
  return {
    and: [
      {
        property: NOTION_PROPERTIES.APPLICATION_STATUS,
        select: { equals: APPLICATION_STATUS_TO_APPLY },
      },
      {
        property: NOTION_PROPERTIES.ANALYZED,
        checkbox: { equals: true },
      },
      {
        property: JOB_POSTING_RESUME_RELATION,
        relation: { is_empty: true },
      },
    ],
  };
}

export function publicResumeQueueItem(page) {
  const companyName = richTextProperty(page, NOTION_PROPERTIES.COMPANY_NAME);
  const jobTitle = richTextProperty(page, NOTION_PROPERTIES.JOB_TITLE);

  return {
    id: page.id,
    url: page.url || "",
    companyName,
    jobTitle,
    resumeName: buildResumeName({ companyName, jobTitle }),
  };
}

export function isReadyForResumeCreation(page) {
  const status = page?.properties?.[NOTION_PROPERTIES.APPLICATION_STATUS]?.select?.name || "";
  const analyzed = page?.properties?.[NOTION_PROPERTIES.ANALYZED]?.checkbox === true;

  return status === APPLICATION_STATUS_TO_APPLY && analyzed;
}

export function hasRelatedResume(page) {
  return Boolean(firstRelatedResumeId(page));
}

export function firstRelatedResumeId(page) {
  return page?.properties?.[JOB_POSTING_RESUME_RELATION]?.relation?.[0]?.id || "";
}

export function buildResumeName({ companyName, jobTitle }) {
  const company = String(companyName || "").trim();
  const title = String(jobTitle || "").trim();

  if (!company || !title) {
    return "";
  }

  return `${title} at ${company}`;
}

export function extractAnalyzedJobPostingSource(blocks) {
  return {
    jobContent: extractJobContentFromBlocks(blocks),
    jobPostingAnalysis: extractJobPostingAnalysisFromBlocks(blocks),
  };
}

export function extractJobPostingAnalysisFromBlocks(blocks) {
  return extractSectionText(blocks, ANALYSIS_HEADING);
}

function extractSectionText(blocks, headingText) {
  const lines = [];
  let inSection = false;

  for (const block of blocks || []) {
    if (block.type === "heading_2" && blockPlainText(block).toLowerCase() === headingText.toLowerCase()) {
      inSection = true;
      continue;
    }
    if (!inSection) {
      continue;
    }
    if (block.type === "heading_2") {
      break;
    }
    const text = blockPlainText(block);
    if (text) {
      lines.push(text);
    }
  }

  return normalizeText(lines.join("\n"));
}

function richTextProperty(page, propertyName) {
  return plainText(page?.properties?.[propertyName]?.rich_text);
}

function plainText(parts) {
  return (parts || [])
    .map((part) => part.plain_text || part.text?.content || "")
    .join("")
    .trim();
}
