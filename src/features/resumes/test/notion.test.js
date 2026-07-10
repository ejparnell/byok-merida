import test from "node:test";
import assert from "node:assert/strict";
import {
  buildResumeName,
  publicResumeQueueItem,
  ResumeNotionClient,
  validateJobPostingResumeRelation,
  validateResumeDatabaseSchema,
  validateResumeWorkflowSchema,
} from "../lib/notion.js";
import {
  APPLICATION_STATUS_TO_APPLY,
  NOTION_PROPERTIES,
} from "../../jobPostings/types/contracts.js";
import {
  JOB_POSTING_RESUME_RELATION,
  RESUME_PROPERTIES,
} from "../types/contracts.js";

test("validateResumeWorkflowSchema accepts matching resume relations", () => {
  const result = validateResumeWorkflowSchema({
    jobPostingDatabase: { properties: validJobPostingProperties() },
    resumeDatabase: { properties: validResumeProperties() },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
  });

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateResumeDatabaseSchema requires Name and Job Posting relation", () => {
  const missing = validateResumeDatabaseSchema({ properties: {} }, {
    jobPostingDatabase: { properties: validJobPostingProperties() },
    jobPostingDatabaseId: "job-db",
  });
  assert.equal(missing.valid, false);
  assert.match(missing.errors.join(" "), /Name/);
  assert.match(missing.errors.join(" "), /Job Posting/);

  const wrongRelation = validateResumeDatabaseSchema({
    properties: {
      ...validResumeProperties(),
      [RESUME_PROPERTIES.JOB_POSTING]: relation("other-db"),
    },
  }, {
    jobPostingDatabase: { properties: validJobPostingProperties() },
    jobPostingDatabaseId: "job-db",
  });
  assert.equal(wrongRelation.valid, false);
  assert.match(wrongRelation.errors.join(" "), /relation target/);
});

test("validateJobPostingResumeRelation requires Resumes relation to the Resume database", () => {
  const missing = validateJobPostingResumeRelation({ properties: {} }, {
    resumeDatabase: { properties: validResumeProperties() },
    resumeDatabaseId: "resume-db",
  });
  assert.equal(missing.valid, false);
  assert.match(missing.errors.join(" "), /Resumes/);

  const wrongRelation = validateJobPostingResumeRelation({
    properties: {
      [JOB_POSTING_RESUME_RELATION]: relation("other-db"),
    },
  }, {
    resumeDatabase: { properties: validResumeProperties() },
    resumeDatabaseId: "resume-db",
  });
  assert.equal(wrongRelation.valid, false);
  assert.match(wrongRelation.errors.join(" "), /relation target/);
});

test("relation validation accepts current Notion data_source_id targets", () => {
  const result = validateResumeWorkflowSchema({
    jobPostingDatabase: {
      id: "job-db",
      data_sources: [{ id: "job-source" }],
      properties: validJobPostingProperties({ resumeRelation: relation("resume-source", { key: "data_source_id" }) }),
    },
    resumeDatabase: {
      id: "resume-db",
      data_sources: [{ id: "resume-source" }],
      properties: validResumeProperties({ jobPostingRelation: relation("job-source", { key: "data_source_id" }) }),
    },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
  });

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("relation validation warns instead of failing when only data_source_id is visible", () => {
  const result = validateResumeWorkflowSchema({
    jobPostingDatabase: {
      id: "job-db",
      properties: validJobPostingProperties({ resumeRelation: relation("resume-source", { key: "data_source_id" }) }),
    },
    resumeDatabase: {
      id: "resume-db",
      properties: validResumeProperties({ jobPostingRelation: relation("job-source", { key: "data_source_id" }) }),
    },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
  });

  assert.equal(result.valid, true);
  assert.equal(result.warnings.filter((warning) => warning.includes("data_source_id")).length, 2);
});

test("publicResumeQueueItem extracts company, title, and resume name from properties", () => {
  const item = publicResumeQueueItem(jobPostingPage({
    companyName: "Example Health",
    jobTitle: "Frontend Engineer",
  }));

  assert.equal(item.companyName, "Example Health");
  assert.equal(item.jobTitle, "Frontend Engineer");
  assert.equal(item.resumeName, "Frontend Engineer at Example Health");
});

test("buildResumeName requires company and job title", () => {
  assert.equal(buildResumeName({ companyName: "Example", jobTitle: "Engineer" }), "Engineer at Example");
  assert.equal(buildResumeName({ companyName: "", jobTitle: "Engineer" }), "");
  assert.equal(buildResumeName({ companyName: "Example", jobTitle: "" }), "");
});

test("ResumeNotionClient queries the Resume Creation Queue", async () => {
  const requests = [];
  const client = new ResumeNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, body: JSON.parse(options.body) });
      return jsonResponse({
        results: [
          jobPostingPage({
            id: "page-1",
            companyName: "Example",
            jobTitle: "Engineer",
          }),
        ],
        has_more: false,
      });
    },
  });

  const items = await client.findResumeCreationQueueItems(10);

  assert.equal(items.length, 1);
  assert.equal(items[0].resumeName, "Engineer at Example");
  assert.match(requests[0].url, /\/databases\/job-db\/query$/);
  assert.equal(requests[0].body.filter.and[0].select.equals, APPLICATION_STATUS_TO_APPLY);
  assert.equal(requests[0].body.filter.and[1].checkbox.equals, true);
  assert.equal(requests[0].body.filter.and[2].relation.is_empty, true);
});

test("ResumeNotionClient commits a generated Resume body before attaching the relation", async () => {
  const requests = [];
  const blocks = [notionBlock("analysis-heading", "heading_2", "Resume Fit Analysis")];
  const client = new ResumeNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : undefined });
      if (url.includes("/blocks/resume-page/children")) {
        return jsonResponse({});
      }
      return jsonResponse({
        id: "resume-page",
        url: "https://notion.so/resume-page",
        properties: {
          [RESUME_PROPERTIES.NAME]: title("Engineer at Example"),
        },
      });
    },
  });

  const resume = await client.createJobSpecificResume({
    resumeName: "Engineer at Example",
    jobPostingPageId: "job-page",
    blocks,
  });

  assert.equal(resume.url, "https://notion.so/resume-page");
  assert.equal(requests[0].body.properties[RESUME_PROPERTIES.JOB_POSTING], undefined);
  assert.equal(requests[1].method, "PATCH");
  assert.match(requests[1].url, /\/blocks\/resume-page\/children$/);
  assert.deepEqual(requests[1].body.children, blocks);
  assert.equal(requests[2].method, "PATCH");
  assert.match(requests[2].url, /\/pages\/resume-page$/);
  assert.equal(requests[2].body.properties[RESUME_PROPERTIES.JOB_POSTING].relation[0].id, "job-page");
});

test("ResumeNotionClient archives the unlinked draft when body commit fails", async () => {
  const requests = [];
  const client = new ResumeNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : undefined });
      if (url.includes("/blocks/resume-page/children")) {
        return jsonResponse({ message: "Append failed." }, { ok: false, status: 500 });
      }
      return jsonResponse({
        id: "resume-page",
        url: "https://notion.so/resume-page",
        properties: {
          [RESUME_PROPERTIES.NAME]: title("Engineer at Example"),
        },
      });
    },
  });

  await assert.rejects(
    () => client.createJobSpecificResume({
      resumeName: "Engineer at Example",
      jobPostingPageId: "job-page",
      blocks: [notionBlock("analysis-heading", "heading_2", "Resume Fit Analysis")],
    }),
    /Append failed/,
  );

  assert.equal(requests.length, 3);
  assert.match(requests[0].url, /\/pages$/);
  assert.match(requests[1].url, /\/blocks\/resume-page\/children$/);
  assert.match(requests[2].url, /\/pages\/resume-page$/);
  assert.equal(requests[2].body.archived, true);
  assert.equal(requests.some((request) => request.body?.properties?.[RESUME_PROPERTIES.JOB_POSTING]), false);
});

test("ResumeNotionClient can recursively read nested page body blocks", async () => {
  const requests = [];
  const client = new ResumeNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    fetchImpl: async (url) => {
      requests.push(url);
      if (url.includes("/blocks/page-id/children")) {
        return jsonResponse({
          results: [
            notionBlock("parent-block", "heading_2", "Experience", { hasChildren: true }),
          ],
          has_more: false,
        });
      }
      if (url.includes("/blocks/parent-block/children")) {
        return jsonResponse({
          results: [
            notionBlock("nested-block", "bulleted_list_item", "Built nested Resume evidence."),
          ],
          has_more: false,
        });
      }
      return jsonResponse({ results: [], has_more: false });
    },
  });

  const blocks = await client.getPageChildren("page-id", { recursive: true });

  assert.equal(blocks.length, 2);
  assert.equal(blocks[0].heading_2.rich_text[0].text.content, "Experience");
  assert.equal(blocks[1].bulleted_list_item.rich_text[0].text.content, "Built nested Resume evidence.");
  assert.equal(blocks[1].resumeDepth, 1);
  assert.equal(requests.length, 2);
});

function validJobPostingProperties({
  resumeRelation = relation("resume-db"),
} = {}) {
  return {
    [NOTION_PROPERTIES.JOB_POSTING]: { type: "title" },
    [NOTION_PROPERTIES.COMPANY_NAME]: { type: "rich_text" },
    [NOTION_PROPERTIES.JOB_TITLE]: { type: "rich_text" },
    [NOTION_PROPERTIES.JOB_URL]: { type: "url" },
    [NOTION_PROPERTIES.LOCATION]: { type: "rich_text" },
    [NOTION_PROPERTIES.APPLICATION_STATUS]: {
      type: "select",
      select: { options: [{ name: APPLICATION_STATUS_TO_APPLY }] },
    },
    [NOTION_PROPERTIES.MATCH_SCORE]: { type: "number" },
    [NOTION_PROPERTIES.APPLICATION_DATE]: { type: "date" },
    [NOTION_PROPERTIES.ANALYZED]: { type: "checkbox" },
    [JOB_POSTING_RESUME_RELATION]: resumeRelation,
  };
}

function validResumeProperties({
  jobPostingRelation = relation("job-db"),
} = {}) {
  return {
    [RESUME_PROPERTIES.NAME]: { type: "title" },
    [RESUME_PROPERTIES.JOB_POSTING]: jobPostingRelation,
  };
}

function jobPostingPage({
  id = "job-page",
  companyName = "Example",
  jobTitle = "Engineer",
  status = APPLICATION_STATUS_TO_APPLY,
  analyzed = true,
  resumes = [],
} = {}) {
  return {
    id,
    url: `https://notion.so/${id}`,
    properties: {
      [NOTION_PROPERTIES.COMPANY_NAME]: richText(companyName),
      [NOTION_PROPERTIES.JOB_TITLE]: richText(jobTitle),
      [NOTION_PROPERTIES.APPLICATION_STATUS]: {
        select: { name: status },
      },
      [NOTION_PROPERTIES.ANALYZED]: {
        checkbox: analyzed,
      },
      [JOB_POSTING_RESUME_RELATION]: {
        type: "relation",
        relation: resumes,
      },
    },
  };
}

function relation(databaseId, { key = "database_id" } = {}) {
  return {
    type: "relation",
    relation: { [key]: databaseId },
  };
}

function title(content) {
  return {
    title: [{ type: "text", plain_text: content, text: { content } }],
  };
}

function richText(content) {
  return {
    rich_text: [{ type: "text", plain_text: content, text: { content } }],
  };
}

function notionBlock(id, type, content, { hasChildren = false } = {}) {
  return {
    id,
    object: "block",
    type,
    has_children: hasChildren,
    [type]: {
      rich_text: [{ type: "text", plain_text: content, text: { content } }],
    },
  };
}

function jsonResponse(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    async json() {
      return payload;
    },
  };
}
