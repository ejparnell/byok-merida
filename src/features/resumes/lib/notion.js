import {
  JOB_POSTING_RESUME_RELATION,
  buildResumeCreationQueueFilter,
  buildResumeName,
  firstRelatedResumeId,
  hasRelatedResume,
  isReadyForResumeCreation,
  publicResumeQueueItem,
} from "../../jobPostings/lib/resumeSource.js";
import { validateDatabaseSchema as validateJobPostingDatabaseSchema } from "../../jobPostings/lib/notion.js";
import { validateRelationTarget } from "../../../lib/notionRelations.js";
import { RESUME_PROPERTIES } from "../types/contracts.js";

const NOTION_VERSION = "2022-06-28";
const DEFAULT_QUEUE_LIMIT = 100;

export class ResumeNotionClient {
  constructor({
    token,
    jobPostingDatabaseId,
    resumeDatabaseId,
    fetchImpl = fetch,
  }) {
    this.token = token;
    this.jobPostingDatabaseId = jobPostingDatabaseId;
    this.resumeDatabaseId = resumeDatabaseId;
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

  async validateResumeWorkflowSchema() {
    const [jobPostingDatabase, resumeDatabase] = await Promise.all([
      this.getJobPostingDatabase(),
      this.getResumeDatabase(),
    ]);

    return validateResumeWorkflowSchema({
      jobPostingDatabase,
      resumeDatabase,
      jobPostingDatabaseId: this.jobPostingDatabaseId,
      resumeDatabaseId: this.resumeDatabaseId,
    });
  }

  async findResumeCreationQueueItems(limit = DEFAULT_QUEUE_LIMIT) {
    const items = [];
    let cursor = undefined;

    while (items.length < limit) {
      const response = await this.queryResumeCreationQueuePage({
        pageSize: Math.min(100, limit - items.length),
        startCursor: cursor,
      });

      for (const page of response.results || []) {
        items.push(publicResumeQueueItem(page));
      }

      if (!response.has_more || !response.next_cursor) {
        break;
      }

      cursor = response.next_cursor;
    }

    return items;
  }

  async queryResumeCreationQueuePage({ pageSize, startCursor }) {
    return this.request(`/databases/${this.jobPostingDatabaseId}/query`, {
      method: "POST",
      body: {
        filter: buildResumeCreationQueueFilter(),
        page_size: pageSize,
        ...(startCursor ? { start_cursor: startCursor } : {}),
      },
    });
  }

  async getJobPostingPage(pageId) {
    return this.request(`/pages/${pageId}`);
  }

  async getResumePage(pageId) {
    return this.request(`/pages/${pageId}`);
  }

  async findRelatedResume(jobPostingPage) {
    const resumeId = firstRelatedResumeId(jobPostingPage);
    if (!resumeId) {
      return null;
    }

    const page = await this.getResumePage(resumeId);
    return publicResumePage(page);
  }

  async findMasterResumePages() {
    const response = await this.request(`/databases/${this.resumeDatabaseId}/query`, {
      method: "POST",
      body: {
        filter: {
          property: RESUME_PROPERTIES.NAME,
          title: { equals: "Master Resume" },
        },
        page_size: 2,
      },
    });

    return (response.results || []).map(publicResumePage);
  }

  async getPageChildren(pageId, { recursive = false, maxDepth = 8 } = {}) {
    const children = await this.getBlockChildren(pageId);
    if (!recursive) {
      return children;
    }

    return this.flattenChildren(children, { depth: 0, maxDepth });
  }

  async getBlockChildren(blockId) {
    const children = [];
    let cursor = undefined;

    do {
      const params = new URLSearchParams({ page_size: "100" });
      if (cursor) {
        params.set("start_cursor", cursor);
      }

      const response = await this.request(`/blocks/${blockId}/children?${params.toString()}`);
      children.push(...(response.results || []));
      cursor = response.has_more ? response.next_cursor : undefined;
    } while (cursor);

    return children;
  }

  async flattenChildren(blocks, { depth, maxDepth }) {
    const output = [];

    for (const block of blocks || []) {
      output.push(depth === 0 ? block : { ...block, resumeDepth: depth });

      if (!block.has_children || depth >= maxDepth || !block.id) {
        continue;
      }

      const nested = await this.getBlockChildren(block.id);
      output.push(...await this.flattenChildren(nested, {
        depth: depth + 1,
        maxDepth,
      }));
    }

    return output;
  }

  async createUnlinkedJobSpecificResume({ resumeName, blocks }) {
    const draft = await createJobSpecificResumeDraft(this, { resumeName });

    try {
      await appendPageChildren(this, draft.id, blocks);
      return draft;
    } catch (error) {
      await archiveResumePage(this, draft.id).catch(() => {});
      throw error;
    }
  }

  async attachResumeToJobPosting({ resumePageId, jobPostingPageId }) {
    return attachResumeToJobPosting(this, {
      resumePageId,
      jobPostingPageId,
    });
  }

  async archiveResumePage(pageId) {
    await archiveResumePage(this, pageId);
  }

  async createJobSpecificResume({ resumeName, jobPostingPageId, blocks }) {
    const draft = await this.createUnlinkedJobSpecificResume({ resumeName, blocks });

    try {
      return await this.attachResumeToJobPosting({
        resumePageId: draft.id,
        jobPostingPageId,
      });
    } catch (error) {
      await this.archiveResumePage(draft.id).catch(() => {});
      throw error;
    }
  }
}

async function appendPageChildren(client, pageId, children) {
  for (const batch of chunk(children, 90)) {
    await client.request(`/blocks/${pageId}/children`, {
      method: "PATCH",
      body: { children: batch },
    });
  }
}

async function attachResumeToJobPosting(client, { resumePageId, jobPostingPageId }) {
  const page = await client.request(`/pages/${resumePageId}`, {
    method: "PATCH",
    body: {
      properties: {
        [RESUME_PROPERTIES.JOB_POSTING]: {
          relation: [{ id: jobPostingPageId }],
        },
      },
    },
  });

  return publicResumePage(page);
}

async function archiveResumePage(client, pageId) {
  await client.request(`/pages/${pageId}`, {
    method: "PATCH",
    body: { archived: true },
  });
}

async function createJobSpecificResumeDraft(client, { resumeName }) {
  const page = await client.request("/pages", {
    method: "POST",
    body: {
      parent: { database_id: client.resumeDatabaseId },
      properties: buildResumeDraftProperties({ resumeName }),
    },
  });

  return publicResumePage(page);
}

export function validateResumeWorkflowSchema({
  jobPostingDatabase,
  resumeDatabase,
  jobPostingDatabaseId,
  resumeDatabaseId,
}) {
  const jobPostingSchema = validateJobPostingDatabaseSchema(jobPostingDatabase);
  const resumeSchema = validateResumeDatabaseSchema(resumeDatabase, {
    jobPostingDatabase,
    jobPostingDatabaseId,
  });
  const jobPostingRelation = validateJobPostingResumeRelation(jobPostingDatabase, {
    resumeDatabase,
    resumeDatabaseId,
  });
  const errors = [
    ...jobPostingSchema.errors,
    ...resumeSchema.errors,
    ...jobPostingRelation.errors,
  ];

  return {
    valid: errors.length === 0,
    errors,
    warnings: [
      ...jobPostingSchema.warnings,
      ...resumeSchema.warnings,
      ...jobPostingRelation.warnings,
    ],
  };
}

export function validateResumeDatabaseSchema(database, {
  jobPostingDatabase,
  jobPostingDatabaseId,
}) {
  const properties = database?.properties || {};
  const errors = [];
  const warnings = [];

  const name = properties[RESUME_PROPERTIES.NAME];
  if (!name) {
    errors.push(`Missing Notion property "${RESUME_PROPERTIES.NAME}".`);
  } else if (name.type !== "title") {
    errors.push(`Notion property "${RESUME_PROPERTIES.NAME}" must be title, found ${name.type}.`);
  }

  const jobPosting = properties[RESUME_PROPERTIES.JOB_POSTING];
  if (!jobPosting) {
    errors.push(`Missing Notion property "${RESUME_PROPERTIES.JOB_POSTING}".`);
  } else if (jobPosting.type !== "relation") {
    errors.push(`Notion property "${RESUME_PROPERTIES.JOB_POSTING}" must be relation, found ${jobPosting.type}.`);
  } else {
    const relation = validateRelationTarget({
      property: jobPosting,
      configuredDatabase: jobPostingDatabase,
      configuredDatabaseId: jobPostingDatabaseId,
      expectedSyncedPropertyName: JOB_POSTING_RESUME_RELATION,
    });
    errors.push(...relation.errors.map((error) => `${RESUME_PROPERTIES.JOB_POSTING}: ${error}`));
    warnings.push(...relation.warnings.map((warning) => `${RESUME_PROPERTIES.JOB_POSTING}: ${warning}`));
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

export function validateJobPostingResumeRelation(database, {
  resumeDatabase,
  resumeDatabaseId,
}) {
  const properties = database?.properties || {};
  const errors = [];
  const warnings = [];
  const resumes = properties[JOB_POSTING_RESUME_RELATION];

  if (!resumes) {
    errors.push(`Missing Notion property "${JOB_POSTING_RESUME_RELATION}".`);
  } else if (resumes.type !== "relation") {
    errors.push(`Notion property "${JOB_POSTING_RESUME_RELATION}" must be relation, found ${resumes.type}.`);
  } else {
    const relation = validateRelationTarget({
      property: resumes,
      configuredDatabase: resumeDatabase,
      configuredDatabaseId: resumeDatabaseId,
      expectedSyncedPropertyName: RESUME_PROPERTIES.JOB_POSTING,
    });
    errors.push(...relation.errors.map((error) => `${JOB_POSTING_RESUME_RELATION}: ${error}`));
    warnings.push(...relation.warnings.map((warning) => `${JOB_POSTING_RESUME_RELATION}: ${warning}`));
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

export {
  buildResumeName,
  hasRelatedResume,
  isReadyForResumeCreation,
  publicResumeQueueItem,
};

export function publicResumePage(page) {
  return {
    id: page.id,
    url: page.url || "",
    name: titleProperty(page, RESUME_PROPERTIES.NAME),
  };
}

function buildResumeDraftProperties({ resumeName }) {
  return {
    [RESUME_PROPERTIES.NAME]: {
      title: richText(resumeName),
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

function richText(content) {
  const value = String(content || "");
  if (!value) {
    return [];
  }

  return [{ type: "text", text: { content: value.slice(0, 2000) } }];
}

function chunk(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}
