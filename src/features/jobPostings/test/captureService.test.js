import test from "node:test";
import assert from "node:assert/strict";
import {
  captureJobPosting,
  confirmJobPosting,
  prepareJobPostingReview,
} from "../backend/captureService.js";

test("captureJobPosting returns already_captured when canonical Job URL exists", async () => {
  const notionClient = fakeNotionClient({
    duplicate: { id: "page-1", url: "https://notion.so/page-1" },
  });

  const result = await captureJobPosting(strongEvidence(), { notionClient });

  assert.equal(result.type, "already_captured");
  assert.equal(result.page.url, "https://notion.so/page-1");
});

test("captureJobPosting creates high-confidence posting", async () => {
  const notionClient = fakeNotionClient();

  const result = await captureJobPosting(strongEvidence(), { notionClient });

  assert.equal(result.type, "created");
  assert.equal(notionClient.created.length, 1);
  assert.equal(notionClient.created[0].jobUrl, "https://example.com/jobs/1");
});

test("captureJobPosting returns needs_review for low-confidence posting", async () => {
  const notionClient = fakeNotionClient();

  const result = await captureJobPosting({
    url: "https://example.com/jobs/2",
    pageTitle: "Careers",
    visibleText: "Role\nApply now",
  }, { notionClient });

  assert.equal(result.type, "needs_review");
});

test("prepareJobPostingReview parses evidence without creating a Notion page", () => {
  const result = prepareJobPostingReview(strongEvidence());

  assert.equal(result.type, "parsed");
  assert.equal(result.parsed.jobUrl, "https://example.com/jobs/1");
  assert.equal(result.parsed.companyName, "Example Health");
  assert.equal(result.parsed.jobTitle, "Senior Frontend Engineer");
  assert.match(result.parsed.jobContent, /Build patient-facing workflows/);
});

test("captureJobPosting returns Notion schema validation errors", async () => {
  const notionClient = fakeNotionClient({ schemaValid: false });

  const result = await captureJobPosting(strongEvidence(), { notionClient });

  assert.equal(result.type, "failed");
  assert.equal(result.reason, "invalid_notion_schema");
  assert.deepEqual(result.errors, ["Bad schema"]);
});

test("confirmJobPosting creates edited review payload", async () => {
  const notionClient = fakeNotionClient();

  const result = await confirmJobPosting({
    jobPostingTitle: "Designer at Example",
    jobUrl: "https://example.com/jobs/3?utm_source=x",
    companyName: "Example",
    jobTitle: "Designer",
    location: "Remote",
    jobContent: "Responsibilities\n- Design useful things.",
  }, { notionClient });

  assert.equal(result.type, "created");
  assert.equal(notionClient.created[0].jobUrl, "https://example.com/jobs/3");
});

function fakeNotionClient({ duplicate = null, schemaValid = true } = {}) {
  return {
    created: [],
    async validateDatabaseSchema() {
      return schemaValid
        ? { valid: true, errors: [], warnings: [] }
        : { valid: false, errors: ["Bad schema"], warnings: [] };
    },
    async findExistingJobPosting() {
      return duplicate;
    },
    async createJobPostingPage(parsed) {
      this.created.push(parsed);
      return { id: "created-page", url: "https://notion.so/created-page" };
    },
  };
}

function strongEvidence() {
  return {
    url: "https://example.com/jobs/1?utm_source=email",
    pageTitle: "Senior Frontend Engineer at Example Health",
    selectedText: `
Senior Frontend Engineer
Company: Example Health
Location: Remote - United States

Responsibilities
- Build patient-facing workflows.
- Partner with design and backend engineering.

Requirements
Experience with TypeScript, accessibility, and React.
${"More content. ".repeat(60)}
    `,
  };
}
