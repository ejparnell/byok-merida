import { mkdir, unlink, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { blockPlainText } from "../../jobPostings/lib/analysisBlocks.js";

const PAGE_WIDTH = 612;
const PAGE_HEIGHT = 792;
const MARGIN_X = 54;
const MARGIN_TOP = 54;
const MARGIN_BOTTOM = 54;
const CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2);
const DEFAULT_EXPORT_DIR = "export";
const EXPORT_PERSON_NAME = "ElizabethParnell";

export class ResumePdfExporter {
  constructor({
    rootDir = process.cwd(),
    exportDir = DEFAULT_EXPORT_DIR,
  } = {}) {
    this.rootDir = rootDir;
    this.exportDir = exportDir;
  }

  async save({ jobPosting, resumeBlocks }) {
    const fileName = buildResumePdfFileName({
      companyName: jobPosting?.companyName,
    });
    const directory = resolve(this.rootDir, this.exportDir);
    const path = resolve(directory, fileName);

    await mkdir(directory, { recursive: true });
    try {
      await writeFile(path, buildResumePdf(resumeBlocks));
    } catch (error) {
      await unlink(path).catch(() => {});
      throw error;
    }

    return {
      path,
      relativePath: `${this.exportDir}/${fileName}`,
      fileName,
    };
  }

  async remove(exportedPdf) {
    if (!exportedPdf?.path) {
      return;
    }

    await unlink(exportedPdf.path).catch((error) => {
      if (error?.code !== "ENOENT") {
        throw error;
      }
    });
  }
}

export function createResumePdfExporter(options = {}) {
  return new ResumePdfExporter(options);
}

export function buildResumePdfFileName({ companyName }) {
  const company = compactCompanyName(companyName) || "Company";
  return `${company}-${EXPORT_PERSON_NAME}.pdf`;
}

export function buildResumePdf(blocks) {
  const pages = layoutResumeBlocks(blocks);
  return renderPdf(pages);
}

function layoutResumeBlocks(blocks) {
  const pages = [[]];
  let y = PAGE_HEIGHT - MARGIN_TOP;

  const currentPage = () => pages[pages.length - 1];
  const addPage = () => {
    pages.push([]);
    y = PAGE_HEIGHT - MARGIN_TOP;
  };
  const ensureSpace = (height) => {
    if (y - height < MARGIN_BOTTOM) {
      addPage();
    }
  };
  const addTextLine = ({
    text,
    x = MARGIN_X,
    align = "left",
    font = "regular",
    size = 10,
    lineHeight = 12,
  }) => {
    ensureSpace(lineHeight);
    currentPage().push({
      type: "text",
      text: normalizePdfText(text),
      x,
      y,
      align,
      font,
      size,
    });
    y -= lineHeight;
  };

  const addWrappedText = ({
    text,
    x = MARGIN_X,
    width = CONTENT_WIDTH,
    prefix = "",
    continuationIndent = 0,
    align = "left",
    font = "regular",
    size = 10,
    lineHeight = 12,
  }) => {
    const lines = wrapText(`${prefix}${normalizePdfText(text)}`, {
      width,
      size,
      firstPrefixLength: prefix.length,
    });

    for (let index = 0; index < lines.length; index += 1) {
      addTextLine({
        text: lines[index],
        x: index === 0 ? x : x + continuationIndent,
        align,
        font,
        size,
        lineHeight,
      });
    }
  };

  for (const block of blocks || []) {
    const text = blockPlainText(block);
    if (!text) {
      continue;
    }

    if (block.type === "heading_1") {
      ensureSpace(30);
      addTextLine({
        text,
        align: "center",
        font: "bold",
        size: 17,
        lineHeight: 21,
      });
      y -= 3;
      continue;
    }

    if (block.type === "heading_2") {
      ensureSpace(30);
      y -= 8;
      addTextLine({
        text,
        font: "bold",
        size: 11,
        lineHeight: 14,
      });
      y -= 4;
      continue;
    }

    if (block.type === "heading_3") {
      ensureSpace(22);
      y -= 4;
      addTextLine({
        text,
        font: "bold",
        size: 10,
        lineHeight: 13,
      });
      continue;
    }

    if (block.type === "bulleted_list_item" || block.type === "numbered_list_item") {
      addWrappedText({
        text,
        x: MARGIN_X + 12,
        width: CONTENT_WIDTH - 12,
        prefix: "- ",
        continuationIndent: 12,
        size: 9.5,
        lineHeight: 12,
      });
      continue;
    }

    const bold = isBoldBlock(block);
    addWrappedText({
      text,
      align: isContactLine(text) ? "center" : "left",
      font: bold ? "bold" : "regular",
      size: isContactLine(text) ? 9 : 10,
      lineHeight: isContactLine(text) ? 14 : 12,
    });
  }

  return pages;
}

function renderPdf(pages) {
  const objects = [];
  objects[1] = "";
  objects[2] = "";
  objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";
  objects[4] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>";
  const pageIds = [];

  for (const page of pages) {
    const stream = renderContentStream(page);
    const contentId = objects.length;
    objects[contentId] = `<< /Length ${Buffer.byteLength(stream, "ascii")} >>\nstream\n${stream}\nendstream`;
    const pageId = objects.length;
    pageIds.push(pageId);
    objects[pageId] = [
      "<< /Type /Page",
      "/Parent 2 0 R",
      `/MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}]`,
      "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >>",
      `/Contents ${contentId} 0 R`,
      ">>",
    ].join(" ");
  }

  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageIds.length} >>`;

  const chunks = ["%PDF-1.4\n"];
  const offsets = [0];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(chunks.join(""), "ascii");
    chunks.push(`${id} 0 obj\n${objects[id]}\nendobj\n`);
  }

  const xrefOffset = Buffer.byteLength(chunks.join(""), "ascii");
  chunks.push(`xref\n0 ${objects.length}\n`);
  chunks.push("0000000000 65535 f \n");
  for (let id = 1; id < objects.length; id += 1) {
    chunks.push(`${String(offsets[id]).padStart(10, "0")} 00000 n \n`);
  }
  chunks.push([
    "trailer",
    `<< /Size ${objects.length} /Root 1 0 R >>`,
    "startxref",
    String(xrefOffset),
    "%%EOF",
    "",
  ].join("\n"));

  return Buffer.from(chunks.join(""), "ascii");
}

function renderContentStream(operations) {
  const lines = ["0 0 0 rg", "0 0 0 RG"];
  for (const operation of operations) {
    if (operation.type === "line") {
      lines.push("0.5 w");
      lines.push(`${operation.x1.toFixed(2)} ${operation.y1.toFixed(2)} m ${operation.x2.toFixed(2)} ${operation.y2.toFixed(2)} l S`);
      continue;
    }

    const font = operation.font === "bold" ? "F2" : "F1";
    const textWidth = estimateTextWidth(operation.text, operation.size);
    const x = operation.align === "center"
      ? (PAGE_WIDTH - textWidth) / 2
      : operation.x;
    lines.push("BT");
    lines.push(`/${font} ${operation.size} Tf`);
    lines.push(`1 0 0 1 ${x.toFixed(2)} ${operation.y.toFixed(2)} Tm`);
    lines.push(`(${escapePdfText(operation.text)}) Tj`);
    lines.push("ET");
  }
  return lines.join("\n");
}

function wrapText(text, {
  width,
  size,
  firstPrefixLength = 0,
}) {
  const normalized = normalizePdfText(text);
  const words = normalized.split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";

  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (estimateTextWidth(candidate, size) <= width || !line) {
      line = candidate;
      continue;
    }
    lines.push(line);
    line = firstPrefixLength > 0 && lines.length === 0
      ? word
      : word;
  }

  if (line) {
    lines.push(line);
  }

  return lines.length > 0 ? lines : [""];
}

function estimateTextWidth(text, size) {
  return normalizePdfText(text).length * size * 0.48;
}

function compactCompanyName(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(/\s+/)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join("");
}

function isBoldBlock(block) {
  const typed = block?.[block.type];
  const richText = typed?.rich_text || [];
  return richText.length > 0 && richText.every((part) => part.annotations?.bold === true);
}

function isContactLine(text) {
  return /\|/.test(text) && /@/.test(text);
}

function normalizePdfText(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u2010-\u2015]/g, "-")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[^\x20-\x7E]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function escapePdfText(value) {
  return normalizePdfText(value)
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}
