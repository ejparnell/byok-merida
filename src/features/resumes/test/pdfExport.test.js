import test from "node:test";
import assert from "node:assert/strict";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  ResumePdfExporter,
  buildResumePdf,
  buildResumePdfFileName,
} from "../lib/pdfExport.js";

test("buildResumePdfFileName compacts the company name into the requested export name", () => {
  assert.equal(
    buildResumePdfFileName({ companyName: "Example Health" }),
    "ExampleHealth-ElizabethParnell.pdf",
  );
  assert.equal(
    buildResumePdfFileName({ companyName: "" }),
    "Company-ElizabethParnell.pdf",
  );
});

test("buildResumePdf returns a valid-looking PDF buffer from resume blocks", () => {
  const pdf = buildResumePdf(sampleResumeBlocks());
  const content = pdf.toString("ascii");

  assert.equal(content.startsWith("%PDF-1.4"), true);
  assert.match(content, /\/Helvetica/);
  assert.match(content, /Elizabeth Parnell/);
  assert.doesNotMatch(content, /\n0\.5 w\n/);
  assert.doesNotMatch(content, /\n[\d.]+ [\d.]+ m [\d.]+ [\d.]+ l S\n/);
  assert.match(content, /%%EOF/);
  assert.ok(pdf.length > 1000);
});

test("ResumePdfExporter writes and removes the local export PDF", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "merida-resume-pdf-"));
  const exporter = new ResumePdfExporter({ rootDir });

  try {
    const exported = await exporter.save({
      jobPosting: { companyName: "Example Health" },
      resumeBlocks: sampleResumeBlocks(),
    });

    assert.equal(exported.fileName, "ExampleHealth-ElizabethParnell.pdf");
    assert.equal(exported.relativePath, "export/ExampleHealth-ElizabethParnell.pdf");

    const pdf = await readFile(exported.path);
    assert.equal(pdf.toString("ascii", 0, 8), "%PDF-1.4");

    await exporter.remove(exported);
    await assert.rejects(() => access(exported.path), { code: "ENOENT" });
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});

function sampleResumeBlocks() {
  return [
    block("heading_1", "Elizabeth Parnell"),
    block("paragraph", "elizabeth@example.com | linkedin.com/in/elizabeth"),
    block("heading_2", "Summary"),
    block("paragraph", "Engineer focused on REST APIs and applicant workflows."),
    block("heading_2", "Experience"),
    block("heading_3", "Software Engineer, ClinMatchGO"),
    block("bulleted_list_item", "Built REST APIs backed by PostgreSQL."),
  ];
}

function block(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: [{ type: "text", plain_text: content, text: { content } }],
    },
  };
}
