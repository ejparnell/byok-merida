import { truncateWithNote, normalizeText, toPlainSingleLine } from "./text.js";

const NOTION_TEXT_LIMIT = 1900;
const JOB_CONTENT_LIMIT = 50000;
const CREATE_CHILD_BATCH_SIZE = 80;
const APPEND_CHILD_BATCH_SIZE = 90;

export function buildJobPostingBlocks(parsed, capturedAt = new Date()) {
  const notes = Array.isArray(parsed.parsingNotes) ? [...parsed.parsingNotes] : [];
  const { text: content, truncated } = truncateWithNote(parsed.jobContent, JOB_CONTENT_LIMIT);

  if (truncated) {
    notes.push("Content Truncated: The job content exceeded the project-defined cap.");
  }

  const blocks = [
    heading("heading_2", "Capture Summary"),
    bullet(`Source: ${parsed.jobUrl}`),
    bullet(`Captured: ${capturedAt.toISOString()}`),
  ];

  if (parsed.capturedUrl) {
    blocks.push(bullet(`Captured URL: ${parsed.capturedUrl}`));
  }

  for (const note of notes) {
    blocks.push(bullet(`Note: ${note}`));
  }

  blocks.push(heading("heading_2", "Job Content"));
  blocks.push(...contentToBlocks(content));

  return {
    blocks,
    truncated,
    initialChildren: blocks.slice(0, CREATE_CHILD_BATCH_SIZE),
    appendBatches: chunk(blocks.slice(CREATE_CHILD_BATCH_SIZE), APPEND_CHILD_BATCH_SIZE),
  };
}

export function contentToBlocks(content) {
  const lines = normalizeText(content).split("\n");
  const blocks = [];
  let paragraphLines = [];

  const flushParagraph = () => {
    const text = normalizeText(paragraphLines.join(" "));
    paragraphLines = [];
    if (!text) return;
    blocks.push(...splitTextBlocks("paragraph", text));
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    const nextLine = lines[index + 1]?.trim() || "";

    if (!line) {
      flushParagraph();
      continue;
    }

    const bulletMatch = line.match(/^[-*\u2022]\s+(.+)$/);
    if (bulletMatch) {
      flushParagraph();
      blocks.push(...splitTextBlocks("bulleted_list_item", bulletMatch[1]));
      continue;
    }

    if (isHeadingLine(line, nextLine)) {
      flushParagraph();
      blocks.push(heading("heading_3", toPlainSingleLine(line, 120).replace(/:$/, "")));
      continue;
    }

    paragraphLines.push(line);
  }

  flushParagraph();

  if (blocks.length === 0) {
    blocks.push(paragraph("No job content was captured."));
  }

  return blocks;
}

export function richText(content) {
  return [{ type: "text", text: { content: String(content || "").slice(0, 2000) } }];
}

function splitTextBlocks(type, text) {
  const normalized = normalizeText(text);
  if (normalized.length <= NOTION_TEXT_LIMIT) {
    return [block(type, normalized)];
  }

  const parts = [];
  for (let offset = 0; offset < normalized.length; offset += NOTION_TEXT_LIMIT) {
    parts.push(block(type, normalized.slice(offset, offset + NOTION_TEXT_LIMIT).trim()));
  }

  return parts;
}

function block(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: richText(content),
    },
  };
}

function paragraph(content) {
  return block("paragraph", content);
}

function bullet(content) {
  return block("bulleted_list_item", content);
}

function heading(type, content) {
  return block(type, content);
}

function isHeadingLine(line, nextLine) {
  if (line.length > 90 || /[.!?]$/.test(line)) {
    return false;
  }

  if (/^(about|overview|responsibilities|requirements|qualifications|benefits|compensation|salary|what you'?ll do|who you are|nice to have|preferred qualifications|application instructions):?$/i.test(line)) {
    return true;
  }

  return Boolean(nextLine.match(/^[-*\u2022]\s+/)) && line.split(/\s+/).length <= 8;
}

function chunk(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}
