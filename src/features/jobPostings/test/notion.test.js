import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPageProperties,
  NotionClient,
  validateDatabaseSchema,
} from "../lib/notion.js";
import {
  APPLICATION_STATUS_TO_APPLY,
  NOTION_PROPERTIES,
} from "../types/contracts.js";

test("validateDatabaseSchema accepts the MVP schema", () => {
  const result = validateDatabaseSchema({ properties: validProperties() });

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateDatabaseSchema rejects wrong types and missing To Apply option", () => {
  const properties = validProperties();
  properties[NOTION_PROPERTIES.JOB_URL] = { type: "rich_text" };
  properties[NOTION_PROPERTIES.APPLICATION_STATUS] = {
    type: "select",
    select: { options: [{ name: "Applied" }] },
  };

  const result = validateDatabaseSchema({ properties });

  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /Job URL/);
  assert.match(result.errors.join(" "), /To Apply/);
});

test("validateDatabaseSchema requires the Analyzed checkbox", () => {
  const properties = validProperties();
  delete properties[NOTION_PROPERTIES.ANALYZED];

  const missing = validateDatabaseSchema({ properties });
  assert.equal(missing.valid, false);
  assert.match(missing.errors.join(" "), /Analyzed/);

  properties[NOTION_PROPERTIES.ANALYZED] = { type: "rich_text" };
  const wrongType = validateDatabaseSchema({ properties });
  assert.equal(wrongType.valid, false);
  assert.match(wrongType.errors.join(" "), /checkbox/);
});

test("buildPageProperties sets capture defaults without Match Score or Application Date values", () => {
  const properties = buildPageProperties({
    jobPostingTitle: "Frontend Engineer at Example Health",
    companyName: "Example Health",
    jobTitle: "Frontend Engineer",
    jobUrl: "https://example.com/jobs/1",
    capturedUrl: "https://example.com/jobs/1?utm_source=x",
    location: "Remote",
  }, { properties: validProperties({ includeCapturedUrl: true }) });

  assert.equal(properties[NOTION_PROPERTIES.JOB_POSTING].title[0].text.content, "Frontend Engineer at Example Health");
  assert.equal(properties[NOTION_PROPERTIES.APPLICATION_STATUS].select.name, APPLICATION_STATUS_TO_APPLY);
  assert.equal(properties[NOTION_PROPERTIES.ANALYZED].checkbox, false);
  assert.equal(properties[NOTION_PROPERTIES.CAPTURED_URL].url, "https://example.com/jobs/1?utm_source=x");
  assert.equal(properties[NOTION_PROPERTIES.MATCH_SCORE], undefined);
  assert.equal(properties[NOTION_PROPERTIES.APPLICATION_DATE], undefined);
});

test("NotionClient queries and counts the Analysis Queue", async () => {
  const requests = [];
  const client = new NotionClient({
    token: "secret",
    databaseId: "database",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, body: options.body ? JSON.parse(options.body) : undefined });
      return jsonResponse({
        results: [
          {
            id: "page-1",
            url: "https://notion.so/page-1",
            properties: {
              [NOTION_PROPERTIES.JOB_POSTING]: {
                title: [{ plain_text: "Engineer at Example" }],
              },
            },
          },
        ],
        has_more: false,
      });
    },
  });

  const count = await client.countAnalysisQueue();
  const items = await client.findAnalysisQueueItems(1);

  assert.equal(count, 1);
  assert.equal(items[0].title, "Engineer at Example");
  assert.equal(requests[0].body.filter.and[0].select.equals, APPLICATION_STATUS_TO_APPLY);
  assert.equal(requests[0].body.filter.and[1].checkbox.equals, false);
});

test("NotionClient appends analysis blocks and marks a posting analyzed", async () => {
  const requests = [];
  const client = new NotionClient({
    token: "secret",
    databaseId: "database",
    fetchImpl: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : undefined });
      return jsonResponse({});
    },
  });

  await client.appendPageChildren("page-1", [{ object: "block", type: "paragraph", paragraph: { rich_text: [] } }]);
  await client.markJobPostingAnalyzed("page-1");

  assert.match(requests[0].url, /\/blocks\/page-1\/children$/);
  assert.equal(requests[0].method, "PATCH");
  assert.match(requests[1].url, /\/pages\/page-1$/);
  assert.equal(requests[1].body.properties[NOTION_PROPERTIES.ANALYZED].checkbox, true);
});

function validProperties({ includeCapturedUrl = false } = {}) {
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
    ...(includeCapturedUrl ? { [NOTION_PROPERTIES.CAPTURED_URL]: { type: "url" } } : {}),
  };
}

function jsonResponse(payload) {
  return {
    ok: true,
    async json() {
      return payload;
    },
  };
}
