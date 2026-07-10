import test from "node:test";
import assert from "node:assert/strict";
import { createCaptureEvidence } from "../lib/captureEvidence.js";

test("createCaptureEvidence merges frame payloads behind one interface", () => {
  const evidence = createCaptureEvidence({
    tabUrl: "https://example.com/jobs/123?utm_source=mail",
    frames: [
      {
        frameId: 0,
        documentId: "document-1",
        url: "https://jobs.example.com/embed",
        pageTitle: "Senior Backend Engineer at Example Labs",
        visibleText: "Navigation\nApply now",
        metadata: {
          jsonLd: [{
            "@type": "JobPosting",
            title: "Senior Backend Engineer",
            hiringOrganization: { name: "Example Labs" },
            jobLocationType: "TELECOMMUTE",
            applicantLocationRequirements: { name: "United States" },
          }],
        },
      },
      {
        frameId: 1,
        documentId: "document-2",
        url: "https://example.com/jobs/123?utm_campaign=share",
        selectedText: "Senior Backend Engineer\nCompany: Example Labs",
        visibleText: "Responsibilities\nBuild reliable APIs.",
        semanticHtml: "<main><h1>Senior Backend Engineer</h1><p>Build reliable APIs.</p></main>",
        metadata: {
          meta: { description: "Build reliable APIs." },
          openGraph: { siteName: "Example Labs" },
        },
      },
    ],
  });

  assert.equal(evidence.jobUrl, "https://example.com/jobs/123");
  assert.equal(evidence.structuredMetadata.jobTitle, "Senior Backend Engineer");
  assert.equal(evidence.structuredMetadata.companyName, "Example Labs");
  assert.equal(evidence.structuredMetadata.location, "Remote - United States");
  assert.match(evidence.content.selectedText, /Senior Backend Engineer/);
  assert.match(evidence.content.visibleText, /Build reliable APIs/);
  assert.match(evidence.content.htmlText, /Build reliable APIs/);
  assert.equal(evidence.summary.frameCount, 2);
  assert.equal(evidence.debug.frameSummaries[1].frameId, 1);
});

test("createCaptureEvidence preserves legacy merged payload behavior", () => {
  const evidence = createCaptureEvidence({
    url: "https://example.com/jobs/legacy?utm_source=mail",
    tabUrl: "https://example.com/jobs/from-tab",
    pageTitle: "Product Engineer at Example",
    selectedText: "Product Engineer\nCompany: Example\nLocation: Remote",
    debug: {
      frameCount: 3,
    },
  });

  assert.equal(evidence.jobUrl, "https://example.com/jobs/legacy");
  assert.equal(evidence.pageTitle, "Product Engineer at Example");
  assert.equal(evidence.content.preferredText, "Product Engineer\nCompany: Example\nLocation: Remote");
  assert.equal(evidence.summary.frameCount, 3);
});

test("createCaptureEvidence validates and limits large text payloads", () => {
  const evidence = createCaptureEvidence({
    url: "https://example.com/jobs/large",
    visibleText: "x".repeat(300005),
  });

  assert.equal(evidence.content.visibleText.length, 300000);
  assert.match(evidence.summary.validationWarnings.join(" "), /visibleText exceeded 300000/);
});
