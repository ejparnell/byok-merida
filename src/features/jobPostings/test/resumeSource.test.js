import test from "node:test";
import assert from "node:assert/strict";
import {
  buildResumeCreationQueueFilter,
  extractAnalyzedJobPostingSource,
  firstRelatedResumeId,
  hasRelatedResume,
  isReadyForResumeCreation,
  publicResumeQueueItem,
} from "../lib/resumeSource.js";
import {
  APPLICATION_STATUS_TO_APPLY,
  JOB_POSTING_RESUME_RELATION,
  NOTION_PROPERTIES,
} from "../types/contracts.js";

test("buildResumeCreationQueueFilter selects analyzed To Apply postings without resumes", () => {
  assert.deepEqual(buildResumeCreationQueueFilter(), {
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
  });
});

test("publicResumeQueueItem projects Job Posting fields for Resume Creation", () => {
  const item = publicResumeQueueItem(jobPostingPage());

  assert.deepEqual(item, {
    id: "page-1",
    url: "https://notion.so/page-1",
    companyName: "Example",
    jobTitle: "Engineer",
    resumeName: "Engineer at Example",
  });
});

test("readiness and related Resume checks use Job Posting properties", () => {
  assert.equal(isReadyForResumeCreation(jobPostingPage()), true);
  assert.equal(isReadyForResumeCreation(jobPostingPage({ analyzed: false })), false);
  assert.equal(hasRelatedResume(jobPostingPage()), false);
  assert.equal(hasRelatedResume(jobPostingPage({ resumes: [{ id: "resume-1" }] })), true);
  assert.equal(firstRelatedResumeId(jobPostingPage({ resumes: [{ id: "resume-1" }] })), "resume-1");
});

test("extractAnalyzedJobPostingSource reads Job Content and Job Posting Analysis sections", () => {
  const source = extractAnalyzedJobPostingSource([
    block("heading_2", "Job Content"),
    block("paragraph", "Build REST APIs."),
    block("heading_2", "Job Posting Analysis"),
    block("paragraph", "The role needs REST APIs."),
    block("heading_2", "Other"),
    block("paragraph", "Ignore me."),
  ]);

  assert.deepEqual(source, {
    jobContent: "Build REST APIs.",
    jobPostingAnalysis: "The role needs REST APIs.",
  });
});

function jobPostingPage({
  companyName = "Example",
  jobTitle = "Engineer",
  status = APPLICATION_STATUS_TO_APPLY,
  analyzed = true,
  resumes = [],
} = {}) {
  return {
    id: "page-1",
    url: "https://notion.so/page-1",
    properties: {
      [NOTION_PROPERTIES.COMPANY_NAME]: richTextProperty(companyName),
      [NOTION_PROPERTIES.JOB_TITLE]: richTextProperty(jobTitle),
      [NOTION_PROPERTIES.APPLICATION_STATUS]: { select: { name: status } },
      [NOTION_PROPERTIES.ANALYZED]: { checkbox: analyzed },
      [JOB_POSTING_RESUME_RELATION]: { relation: resumes },
    },
  };
}

function richTextProperty(content) {
  return {
    rich_text: [{ plain_text: content, text: { content } }],
  };
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
