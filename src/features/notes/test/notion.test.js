import test from "node:test";
import assert from "node:assert/strict";
import {
  buildResumeFitAnalysisNoteName,
  NotesNotionClient,
  validateJobPostingNotesRelation,
  validateNotesDatabaseSchema,
  validateNotesWorkflowSchema,
  validateResumeNotesRelation,
} from "../lib/notion.js";
import { NOTION_PROPERTIES } from "../../jobPostings/types/contracts.js";
import { RESUME_PROPERTIES } from "../../resumes/types/contracts.js";
import { NOTES_PROPERTIES, NOTES_RELATION } from "../types/contracts.js";

test("validateNotesWorkflowSchema accepts matching note relations", () => {
  const result = validateNotesWorkflowSchema({
    jobPostingDatabase: { properties: validJobPostingProperties() },
    resumeDatabase: { properties: validResumeProperties() },
    notesDatabase: { properties: validNotesProperties() },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    notesDatabaseId: "notes-db",
  });

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateNotesDatabaseSchema requires Name, Job Posting, and Resume", () => {
  const missing = validateNotesDatabaseSchema({ properties: {} }, {
    jobPostingDatabase: { properties: validJobPostingProperties() },
    resumeDatabase: { properties: validResumeProperties() },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
  });

  assert.equal(missing.valid, false);
  assert.match(missing.errors.join(" "), /Name/);
  assert.match(missing.errors.join(" "), /Job Posting/);
  assert.match(missing.errors.join(" "), /Resume/);

  const wrongResumeRelation = validateNotesDatabaseSchema({
    properties: {
      ...validNotesProperties(),
      [NOTES_PROPERTIES.RESUME]: relation("other-db"),
    },
  }, {
    jobPostingDatabase: { properties: validJobPostingProperties() },
    resumeDatabase: { properties: validResumeProperties() },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
  });

  assert.equal(wrongResumeRelation.valid, false);
  assert.match(wrongResumeRelation.errors.join(" "), /relation target/);
});

test("inverse Notes relations must point back to the Notes database", () => {
  const missingJobRelation = validateJobPostingNotesRelation({ properties: {} }, {
    notesDatabase: { properties: validNotesProperties() },
    notesDatabaseId: "notes-db",
  });
  assert.equal(missingJobRelation.valid, false);
  assert.match(missingJobRelation.errors.join(" "), /Notes/);

  const wrongResumeRelation = validateResumeNotesRelation({
    properties: {
      [NOTES_RELATION]: relation("other-db"),
    },
  }, {
    notesDatabase: { properties: validNotesProperties() },
    notesDatabaseId: "notes-db",
  });
  assert.equal(wrongResumeRelation.valid, false);
  assert.match(wrongResumeRelation.errors.join(" "), /relation target/);
});

test("inverse Notes relation names are validated when Notion exposes them", () => {
  const result = validateNotesWorkflowSchema({
    jobPostingDatabase: {
      properties: validJobPostingProperties({
        notesRelation: relation("notes-db", { syncedPropertyName: "Wrong Name" }),
      }),
    },
    resumeDatabase: { properties: validResumeProperties() },
    notesDatabase: { properties: validNotesProperties() },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    notesDatabaseId: "notes-db",
  });

  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /inverse relation/);
  assert.match(result.errors.join(" "), /Job Posting/);
});

test("relation validation accepts current Notion data_source_id targets", () => {
  const result = validateNotesWorkflowSchema({
    jobPostingDatabase: {
      id: "job-db",
      data_sources: [{ id: "job-source" }],
      properties: validJobPostingProperties({ notesRelation: relation("notes-source", { key: "data_source_id" }) }),
    },
    resumeDatabase: {
      id: "resume-db",
      data_sources: [{ id: "resume-source" }],
      properties: validResumeProperties({ notesRelation: relation("notes-source", { key: "data_source_id" }) }),
    },
    notesDatabase: {
      id: "notes-db",
      data_sources: [{ id: "notes-source" }],
      properties: validNotesProperties({
        jobPostingRelation: relation("job-source", { key: "data_source_id" }),
        resumeRelation: relation("resume-source", { key: "data_source_id" }),
      }),
    },
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    notesDatabaseId: "notes-db",
  });

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("buildResumeFitAnalysisNoteName distinguishes notes from resumes", () => {
  assert.equal(
    buildResumeFitAnalysisNoteName({ jobTitle: "Engineer", companyName: "Example" }),
    "Resume Fit Analysis - Engineer at Example",
  );
  assert.equal(buildResumeFitAnalysisNoteName({ jobTitle: "", companyName: "Example" }), "");
});

test("NotesNotionClient creates a related Resume Fit Analysis Note with body blocks", async () => {
  const requests = [];
  const blocks = [notionBlock("analysis-heading", "heading_2", "Resume Fit Analysis")];
  const client = new NotesNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    notesDatabaseId: "notes-db",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : undefined });
      return jsonResponse({
        id: "note-page",
        url: "https://notion.so/note-page",
        properties: {
          [NOTES_PROPERTIES.NAME]: title("Resume Fit Analysis - Engineer at Example"),
        },
      });
    },
  });

  const note = await client.createResumeFitAnalysisNote({
    noteName: "Resume Fit Analysis - Engineer at Example",
    jobPostingPageId: "job-page",
    resumePageId: "resume-page",
    blocks,
  });

  assert.equal(note.url, "https://notion.so/note-page");
  assert.match(requests[0].url, /\/pages$/);
  assert.equal(requests[0].body.properties[NOTES_PROPERTIES.NAME].title[0].text.content, "Resume Fit Analysis - Engineer at Example");
  assert.equal(requests[0].body.properties[NOTES_PROPERTIES.JOB_POSTING].relation[0].id, "job-page");
  assert.equal(requests[0].body.properties[NOTES_PROPERTIES.RESUME].relation[0].id, "resume-page");
  assert.match(requests[1].url, /\/blocks\/note-page\/children$/);
  assert.deepEqual(requests[1].body.children, blocks);
});

test("NotesNotionClient archives an orphaned note when body append fails", async () => {
  const requests = [];
  const client = new NotesNotionClient({
    token: "secret",
    jobPostingDatabaseId: "job-db",
    resumeDatabaseId: "resume-db",
    notesDatabaseId: "notes-db",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : undefined });
      if (url.includes("/blocks/note-page/children")) {
        return jsonResponse({ message: "Append failed." }, { ok: false, status: 500 });
      }
      return jsonResponse({
        id: "note-page",
        url: "https://notion.so/note-page",
        properties: {
          [NOTES_PROPERTIES.NAME]: title("Resume Fit Analysis - Engineer at Example"),
        },
      });
    },
  });

  await assert.rejects(
    () => client.createResumeFitAnalysisNote({
      noteName: "Resume Fit Analysis - Engineer at Example",
      jobPostingPageId: "job-page",
      resumePageId: "resume-page",
      blocks: [notionBlock("analysis-heading", "heading_2", "Resume Fit Analysis")],
    }),
    /Append failed/,
  );

  assert.equal(requests.length, 3);
  assert.match(requests[2].url, /\/pages\/note-page$/);
  assert.equal(requests[2].body.archived, true);
});

function validJobPostingProperties({
  notesRelation = relation("notes-db", { syncedPropertyName: NOTES_PROPERTIES.JOB_POSTING }),
} = {}) {
  return {
    [NOTION_PROPERTIES.JOB_POSTING]: { type: "title" },
    [NOTES_RELATION]: notesRelation,
  };
}

function validResumeProperties({
  notesRelation = relation("notes-db", { syncedPropertyName: NOTES_PROPERTIES.RESUME }),
} = {}) {
  return {
    [RESUME_PROPERTIES.NAME]: { type: "title" },
    [RESUME_PROPERTIES.JOB_POSTING]: relation("job-db"),
    [NOTES_RELATION]: notesRelation,
  };
}

function validNotesProperties({
  jobPostingRelation = relation("job-db", { syncedPropertyName: NOTES_RELATION }),
  resumeRelation = relation("resume-db", { syncedPropertyName: NOTES_RELATION }),
} = {}) {
  return {
    [NOTES_PROPERTIES.NAME]: { type: "title" },
    [NOTES_PROPERTIES.JOB_POSTING]: jobPostingRelation,
    [NOTES_PROPERTIES.RESUME]: resumeRelation,
  };
}

function relation(databaseId, {
  key = "database_id",
  syncedPropertyName = "",
} = {}) {
  return {
    type: "relation",
    relation: {
      [key]: databaseId,
      ...(syncedPropertyName ? {
        dual_property: { synced_property_name: syncedPropertyName },
      } : {}),
    },
  };
}

function title(content) {
  return {
    title: [{ type: "text", plain_text: content, text: { content } }],
  };
}

function notionBlock(id, type, content) {
  return {
    id,
    object: "block",
    type,
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
