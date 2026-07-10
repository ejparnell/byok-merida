import test from "node:test";
import assert from "node:assert/strict";
import {
  buildJobPostingBlocks,
  contentToBlocks,
} from "../lib/notionBlocks.js";

test("contentToBlocks preserves headings and bullet lists", () => {
  const blocks = contentToBlocks(`
Responsibilities
- Build capture workflows.
- Keep Notion pages readable.

Requirements
Experience with browser extensions.
  `);

  assert.equal(blocks[0].type, "heading_3");
  assert.equal(blocks[1].type, "bulleted_list_item");
  assert.equal(blocks[2].type, "bulleted_list_item");
  assert.equal(blocks[3].type, "heading_3");
  assert.equal(blocks[4].type, "paragraph");
});

test("buildJobPostingBlocks includes capture summary and truncation note", () => {
  const longContent = `Responsibilities\n${"A".repeat(51000)}`;
  const result = buildJobPostingBlocks({
    jobUrl: "https://example.com/jobs/1",
    capturedUrl: "https://example.com/jobs/1?utm_source=x",
    jobContent: longContent,
    parsingNotes: [],
  }, new Date("2026-05-26T12:00:00.000Z"));

  const text = JSON.stringify(result.blocks);
  assert.equal(result.truncated, true);
  assert.match(text, /Capture Summary/);
  assert.match(text, /Content Truncated/);
});
