import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseCaptureEvidence } from "../lib/parser.js";
import { stripHtml } from "../lib/text.js";

test("parseCaptureEvidence prefers selected text and JSON-LD metadata", () => {
  const html = readFileSync(new URL("./fixtures/job-posting.html", import.meta.url), "utf8");
  const evidence = {
    url: "https://example.com/jobs/123?utm_source=mail",
    pageTitle: "Senior Frontend Engineer at Example Health",
    selectedText: stripHtml(html),
    visibleText: "Navigation noise",
    metadata: {
      jsonLd: [{
        "@type": "JobPosting",
        title: "Senior Frontend Engineer",
        hiringOrganization: { name: "Example Health" },
        jobLocationType: "TELECOMMUTE",
        applicantLocationRequirements: { name: "United States" },
      }],
    },
  };

  const parsed = parseCaptureEvidence(evidence);

  assert.equal(parsed.jobPostingTitle, "Senior Frontend Engineer at Example Health");
  assert.equal(parsed.companyName, "Example Health");
  assert.equal(parsed.jobTitle, "Senior Frontend Engineer");
  assert.equal(parsed.location, "Remote - United States");
  assert.equal(parsed.jobUrl, "https://example.com/jobs/123");
  assert.match(parsed.jobContent, /Build patient-facing workflows/);
  assert.equal(parsed.needsReview, false);
});

test("parseCaptureEvidence marks weak generic captures for review", () => {
  const parsed = parseCaptureEvidence({
    url: "https://example.com/jobs/weak",
    pageTitle: "Careers",
    visibleText: "Apply now",
  });

  assert.equal(parsed.needsReview, true);
  assert.match(parsed.parsingNotes.join(" "), /Company name/);
});

test("parseCaptureEvidence accepts frame payloads and falls back to tabUrl", () => {
  const parsed = parseCaptureEvidence({
    tabUrl: "https://example.com/jobs/from-tab?utm_source=mail",
    frames: [{
      frameId: 0,
      url: "",
      pageTitle: "Backend Engineer at Example",
      selectedText: `
Backend Engineer
Company: Example
Location: Remote
Responsibilities
- Build capture APIs.
${"Useful content. ".repeat(60)}
    `,
    }],
  });

  assert.equal(parsed.jobUrl, "https://example.com/jobs/from-tab");
  assert.equal(parsed.jobPostingTitle, "Backend Engineer at Example");
  assert.equal(parsed.evidenceDebug.frameCount, 1);
});

test("parseCaptureEvidence can use job metadata description as review content", () => {
  const parsed = parseCaptureEvidence({
    url: "https://example.com/jobs/metadata-only",
    pageTitle: "Product Engineer at Example",
    visibleText: "",
    semanticHtml: "",
    metadata: {
      jsonLd: [{
        "@type": "JobPosting",
        title: "Product Engineer",
        hiringOrganization: { name: "Example" },
        description: "Build useful product workflows with a small engineering team.",
      }],
    },
  });

  assert.equal(parsed.jobUrl, "https://example.com/jobs/metadata-only");
  assert.match(parsed.jobContent, /Build useful product workflows/);
  assert.equal(parsed.needsReview, true);
});
