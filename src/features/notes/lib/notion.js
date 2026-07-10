import { richText } from "../../jobPostings/lib/notionBlocks.js";
import { validateRelationTarget } from "../../../lib/notionRelations.js";
import { NOTES_PROPERTIES, NOTES_RELATION } from "../types/contracts.js";

const NOTION_VERSION = "2022-06-28";

export class NotesNotionClient {
  constructor({
    token,
    jobPostingDatabaseId,
    resumeDatabaseId,
    notesDatabaseId,
    fetchImpl = fetch,
  }) {
    this.token = token;
    this.jobPostingDatabaseId = jobPostingDatabaseId;
    this.resumeDatabaseId = resumeDatabaseId;
    this.notesDatabaseId = notesDatabaseId;
    this.fetch = fetchImpl;
  }

  async request(path, { method = "GET", body } = {}) {
    const response = await this.fetch(`https://api.notion.com/v1${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const message = payload.message || `Notion request failed with ${response.status}`;
      const error = new Error(message);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return payload;
  }

  async getJobPostingDatabase() {
    return this.request(`/databases/${this.jobPostingDatabaseId}`);
  }

  async getResumeDatabase() {
    return this.request(`/databases/${this.resumeDatabaseId}`);
  }

  async getNotesDatabase() {
    return this.request(`/databases/${this.notesDatabaseId}`);
  }

  async validateNotesWorkflowSchema() {
    const [jobPostingDatabase, resumeDatabase, notesDatabase] = await Promise.all([
      this.getJobPostingDatabase(),
      this.getResumeDatabase(),
      this.getNotesDatabase(),
    ]);

    return validateNotesWorkflowSchema({
      jobPostingDatabase,
      resumeDatabase,
      notesDatabase,
      jobPostingDatabaseId: this.jobPostingDatabaseId,
      resumeDatabaseId: this.resumeDatabaseId,
      notesDatabaseId: this.notesDatabaseId,
    });
  }

  async createResumeFitAnalysisNote({
    noteName,
    jobPostingPageId,
    resumePageId,
    blocks,
  }) {
    const page = await this.request("/pages", {
      method: "POST",
      body: {
        parent: { database_id: this.notesDatabaseId },
        properties: buildResumeFitAnalysisNoteProperties({
          noteName,
          jobPostingPageId,
          resumePageId,
        }),
      },
    });
    const note = publicNotePage(page);

    try {
      await appendPageChildren(this, note.id, blocks);
      return note;
    } catch (error) {
      await this.archiveNote(note.id).catch(() => {});
      throw error;
    }
  }

  async archiveNote(noteId) {
    await this.request(`/pages/${noteId}`, {
      method: "PATCH",
      body: { archived: true },
    });
  }
}

export function validateNotesWorkflowSchema({
  jobPostingDatabase,
  resumeDatabase,
  notesDatabase,
  jobPostingDatabaseId,
  resumeDatabaseId,
  notesDatabaseId,
}) {
  const notesSchema = validateNotesDatabaseSchema(notesDatabase, {
    jobPostingDatabase,
    resumeDatabase,
    jobPostingDatabaseId,
    resumeDatabaseId,
  });
  const jobPostingRelation = validateJobPostingNotesRelation(jobPostingDatabase, {
    notesDatabase,
    notesDatabaseId,
  });
  const resumeRelation = validateResumeNotesRelation(resumeDatabase, {
    notesDatabase,
    notesDatabaseId,
  });
  const errors = [
    ...notesSchema.errors,
    ...jobPostingRelation.errors,
    ...resumeRelation.errors,
  ];

  return {
    valid: errors.length === 0,
    errors,
    warnings: [
      ...notesSchema.warnings,
      ...jobPostingRelation.warnings,
      ...resumeRelation.warnings,
    ],
  };
}

export function validateNotesDatabaseSchema(database, {
  jobPostingDatabase,
  resumeDatabase,
  jobPostingDatabaseId,
  resumeDatabaseId,
}) {
  const properties = database?.properties || {};
  const errors = [];
  const warnings = [];

  const name = properties[NOTES_PROPERTIES.NAME];
  if (!name) {
    errors.push(`Missing Notion property "${NOTES_PROPERTIES.NAME}".`);
  } else if (name.type !== "title") {
    errors.push(`Notion property "${NOTES_PROPERTIES.NAME}" must be title, found ${name.type}.`);
  }

  const jobPosting = properties[NOTES_PROPERTIES.JOB_POSTING];
  if (!jobPosting) {
    errors.push(`Missing Notion property "${NOTES_PROPERTIES.JOB_POSTING}".`);
  } else if (jobPosting.type !== "relation") {
    errors.push(`Notion property "${NOTES_PROPERTIES.JOB_POSTING}" must be relation, found ${jobPosting.type}.`);
  } else {
    const relation = validateRelationTarget({
      property: jobPosting,
      configuredDatabase: jobPostingDatabase,
      configuredDatabaseId: jobPostingDatabaseId,
      expectedSyncedPropertyName: NOTES_RELATION,
    });
    errors.push(...relation.errors.map((error) => `${NOTES_PROPERTIES.JOB_POSTING}: ${error}`));
    warnings.push(...relation.warnings.map((warning) => `${NOTES_PROPERTIES.JOB_POSTING}: ${warning}`));
  }

  const resume = properties[NOTES_PROPERTIES.RESUME];
  if (!resume) {
    errors.push(`Missing Notion property "${NOTES_PROPERTIES.RESUME}".`);
  } else if (resume.type !== "relation") {
    errors.push(`Notion property "${NOTES_PROPERTIES.RESUME}" must be relation, found ${resume.type}.`);
  } else {
    const relation = validateRelationTarget({
      property: resume,
      configuredDatabase: resumeDatabase,
      configuredDatabaseId: resumeDatabaseId,
      expectedSyncedPropertyName: NOTES_RELATION,
    });
    errors.push(...relation.errors.map((error) => `${NOTES_PROPERTIES.RESUME}: ${error}`));
    warnings.push(...relation.warnings.map((warning) => `${NOTES_PROPERTIES.RESUME}: ${warning}`));
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

export function validateJobPostingNotesRelation(database, {
  notesDatabase,
  notesDatabaseId,
}) {
  return validateInverseNotesRelation({
    database,
    relationPropertyName: NOTES_RELATION,
    configuredDatabase: notesDatabase,
    configuredDatabaseId: notesDatabaseId,
    expectedSyncedPropertyName: NOTES_PROPERTIES.JOB_POSTING,
  });
}

export function validateResumeNotesRelation(database, {
  notesDatabase,
  notesDatabaseId,
}) {
  return validateInverseNotesRelation({
    database,
    relationPropertyName: NOTES_RELATION,
    configuredDatabase: notesDatabase,
    configuredDatabaseId: notesDatabaseId,
    expectedSyncedPropertyName: NOTES_PROPERTIES.RESUME,
  });
}

export function buildResumeFitAnalysisNoteName({ jobTitle, companyName }) {
  const title = String(jobTitle || "").trim();
  const company = String(companyName || "").trim();

  if (!title || !company) {
    return "";
  }

  return `Resume Fit Analysis - ${title} at ${company}`;
}

export function publicNotePage(page) {
  return {
    id: page.id,
    url: page.url || "",
    name: titleProperty(page, NOTES_PROPERTIES.NAME),
  };
}

function validateInverseNotesRelation({
  database,
  relationPropertyName,
  configuredDatabase,
  configuredDatabaseId,
  expectedSyncedPropertyName,
}) {
  const properties = database?.properties || {};
  const errors = [];
  const warnings = [];
  const relationProperty = properties[relationPropertyName];

  if (!relationProperty) {
    errors.push(`Missing Notion property "${relationPropertyName}".`);
  } else if (relationProperty.type !== "relation") {
    errors.push(`Notion property "${relationPropertyName}" must be relation, found ${relationProperty.type}.`);
  } else {
    const relation = validateRelationTarget({
      property: relationProperty,
      configuredDatabase,
      configuredDatabaseId,
      expectedSyncedPropertyName,
    });
    errors.push(...relation.errors.map((error) => `${relationPropertyName}: ${error}`));
    warnings.push(...relation.warnings.map((warning) => `${relationPropertyName}: ${warning}`));
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

async function appendPageChildren(client, pageId, children) {
  for (const batch of chunk(children, 90)) {
    await client.request(`/blocks/${pageId}/children`, {
      method: "PATCH",
      body: { children: batch },
    });
  }
}

function buildResumeFitAnalysisNoteProperties({
  noteName,
  jobPostingPageId,
  resumePageId,
}) {
  return {
    [NOTES_PROPERTIES.NAME]: {
      title: richText(noteName),
    },
    [NOTES_PROPERTIES.JOB_POSTING]: {
      relation: [{ id: jobPostingPageId }],
    },
    [NOTES_PROPERTIES.RESUME]: {
      relation: [{ id: resumePageId }],
    },
  };
}

function titleProperty(page, propertyName) {
  return plainText(page?.properties?.[propertyName]?.title);
}

function plainText(parts) {
  return (parts || [])
    .map((part) => part.plain_text || part.text?.content || "")
    .join("")
    .trim();
}

function chunk(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}
