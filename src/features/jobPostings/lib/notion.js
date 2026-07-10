import {
  APPLICATION_STATUS_TO_APPLY,
  NOTION_PROPERTIES,
} from "../types/contracts.js";
import { buildJobPostingBlocks } from "./notionBlocks.js";

const NOTION_VERSION = "2022-06-28";

const REQUIRED_SCHEMA = [
  [NOTION_PROPERTIES.JOB_POSTING, "title"],
  [NOTION_PROPERTIES.COMPANY_NAME, "rich_text"],
  [NOTION_PROPERTIES.JOB_TITLE, "rich_text"],
  [NOTION_PROPERTIES.JOB_URL, "url"],
  [NOTION_PROPERTIES.LOCATION, "rich_text"],
  [NOTION_PROPERTIES.APPLICATION_STATUS, "select"],
  [NOTION_PROPERTIES.MATCH_SCORE, "number"],
  [NOTION_PROPERTIES.APPLICATION_DATE, "date"],
  [NOTION_PROPERTIES.ANALYZED, "checkbox"],
];

export class NotionClient {
  constructor({ token, databaseId, fetchImpl = fetch }) {
    this.token = token;
    this.databaseId = databaseId;
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

  async getDatabase() {
    return this.request(`/databases/${this.databaseId}`);
  }

  async validateDatabaseSchema() {
    const database = await this.getDatabase();
    return validateDatabaseSchema(database);
  }

  async findExistingJobPosting(jobUrl) {
    const response = await this.request(`/databases/${this.databaseId}/query`, {
      method: "POST",
      body: {
        filter: {
          property: NOTION_PROPERTIES.JOB_URL,
          url: { equals: jobUrl },
        },
        page_size: 1,
      },
    });

    const existing = response.results?.[0];
    if (!existing) {
      return null;
    }

    return {
      id: existing.id,
      url: existing.url,
    };
  }

  async countAnalysisQueue() {
    let count = 0;
    let cursor = undefined;

    do {
      const response = await this.queryAnalysisQueuePage({
        pageSize: 100,
        startCursor: cursor,
      });
      count += response.results?.length || 0;
      cursor = response.has_more ? response.next_cursor : undefined;
    } while (cursor);

    return count;
  }

  async findAnalysisQueueItems(limit) {
    const items = [];
    let cursor = undefined;

    while (items.length < limit) {
      const response = await this.queryAnalysisQueuePage({
        pageSize: Math.min(100, limit - items.length),
        startCursor: cursor,
      });

      for (const page of response.results || []) {
        items.push(publicAnalysisQueueItem(page));
      }

      if (!response.has_more || !response.next_cursor) {
        break;
      }

      cursor = response.next_cursor;
    }

    return items;
  }

  async queryAnalysisQueuePage({ pageSize, startCursor }) {
    return this.request(`/databases/${this.databaseId}/query`, {
      method: "POST",
      body: {
        filter: {
          and: [
            {
              property: NOTION_PROPERTIES.APPLICATION_STATUS,
              select: { equals: APPLICATION_STATUS_TO_APPLY },
            },
            {
              property: NOTION_PROPERTIES.ANALYZED,
              checkbox: { equals: false },
            },
          ],
        },
        page_size: pageSize,
        ...(startCursor ? { start_cursor: startCursor } : {}),
      },
    });
  }

  async getPageChildren(pageId) {
    const children = [];
    let cursor = undefined;

    do {
      const params = new URLSearchParams({ page_size: "100" });
      if (cursor) {
        params.set("start_cursor", cursor);
      }

      const response = await this.request(`/blocks/${pageId}/children?${params.toString()}`);
      children.push(...(response.results || []));
      cursor = response.has_more ? response.next_cursor : undefined;
    } while (cursor);

    return children;
  }

  async appendPageChildren(pageId, children) {
    for (const batch of chunk(children, 90)) {
      await this.request(`/blocks/${pageId}/children`, {
        method: "PATCH",
        body: { children: batch },
      });
    }
  }

  async markJobPostingAnalyzed(pageId) {
    await this.request(`/pages/${pageId}`, {
      method: "PATCH",
      body: {
        properties: {
          [NOTION_PROPERTIES.ANALYZED]: { checkbox: true },
        },
      },
    });
  }

  async createJobPostingPage(parsed, capturedAt = new Date()) {
    const database = await this.getDatabase();
    const blockSet = buildJobPostingBlocks(parsed, capturedAt);
    const page = await this.request("/pages", {
      method: "POST",
      body: {
        parent: { database_id: this.databaseId },
        properties: buildPageProperties(parsed, database),
        children: blockSet.initialChildren,
      },
    });

    for (const batch of blockSet.appendBatches) {
      await this.request(`/blocks/${page.id}/children`, {
        method: "PATCH",
        body: { children: batch },
      });
    }

    return {
      id: page.id,
      url: page.url,
      truncated: blockSet.truncated,
    };
  }
}

export function validateDatabaseSchema(database) {
  const properties = database?.properties || {};
  const errors = [];
  const warnings = [];

  for (const [propertyName, expectedType] of REQUIRED_SCHEMA) {
    const property = properties[propertyName];
    if (!property) {
      errors.push(`Missing Notion property "${propertyName}".`);
      continue;
    }

    if (property.type !== expectedType) {
      errors.push(`Notion property "${propertyName}" must be ${expectedType}, found ${property.type}.`);
    }
  }

  const capturedUrl = properties[NOTION_PROPERTIES.CAPTURED_URL];
  if (capturedUrl && capturedUrl.type !== "url") {
    errors.push(`Optional Notion property "${NOTION_PROPERTIES.CAPTURED_URL}" must be url when present.`);
  }

  const status = properties[NOTION_PROPERTIES.APPLICATION_STATUS];
  const options = status?.select?.options || [];
  if (status?.type === "select" && !options.some((option) => option.name === APPLICATION_STATUS_TO_APPLY)) {
    errors.push(`Notion property "${NOTION_PROPERTIES.APPLICATION_STATUS}" must include a "${APPLICATION_STATUS_TO_APPLY}" option.`);
  }

  if (!capturedUrl) {
    warnings.push(`Optional Notion property "${NOTION_PROPERTIES.CAPTURED_URL}" is not present; captured URL evidence will be omitted.`);
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

export function buildPageProperties(parsed, database = {}) {
  const properties = database.properties || {};
  const output = {
    [NOTION_PROPERTIES.JOB_POSTING]: {
      title: richText(parsed.jobPostingTitle),
    },
    [NOTION_PROPERTIES.COMPANY_NAME]: {
      rich_text: richText(parsed.companyName || ""),
    },
    [NOTION_PROPERTIES.JOB_TITLE]: {
      rich_text: richText(parsed.jobTitle || ""),
    },
    [NOTION_PROPERTIES.JOB_URL]: {
      url: parsed.jobUrl,
    },
    [NOTION_PROPERTIES.LOCATION]: {
      rich_text: richText(parsed.location || ""),
    },
    [NOTION_PROPERTIES.APPLICATION_STATUS]: {
      select: { name: APPLICATION_STATUS_TO_APPLY },
    },
    [NOTION_PROPERTIES.ANALYZED]: {
      checkbox: false,
    },
  };

  if (parsed.capturedUrl && properties[NOTION_PROPERTIES.CAPTURED_URL]) {
    output[NOTION_PROPERTIES.CAPTURED_URL] = { url: parsed.capturedUrl };
  }

  return output;
}

export function publicAnalysisQueueItem(page) {
  return {
    id: page.id,
    url: page.url || "",
    title: pageTitle(page),
  };
}

function pageTitle(page) {
  const title = page?.properties?.[NOTION_PROPERTIES.JOB_POSTING]?.title || [];
  return title.map((part) => part.plain_text || part.text?.content || "").join("").trim() || "Untitled Job Posting";
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
