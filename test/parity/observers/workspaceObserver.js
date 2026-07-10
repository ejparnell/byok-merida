import { validateRelationTarget } from "../../../src/lib/notionRelations.js";
import { buildPageProperties } from "../../../src/features/jobPostings/lib/notion.js";
import { buildJobPostingBlocks } from "../../../src/features/jobPostings/lib/notionBlocks.js";
import { blockText, createCallCounter } from "./observerSupport.js";

export function observeWorkspaceFixture(fixture) {
  if (fixture.observation.runner !== "notion_compatibility") {
    throw new Error(`Unsupported workspace runner: ${fixture.observation.runner}`);
  }
  const calls = createCallCounter();
  const database = {
    id: "applications-database",
    data_sources: [{ id: "applications-data-source" }],
  };
  calls.increment("validateRelationTarget");
  const databaseIdResult = validateRelationTarget({
    property: { relation: { database_id: "applications-database" } },
    configuredDatabase: database,
    configuredDatabaseId: database.id,
    expectedSyncedPropertyName: "Resumes",
  });
  calls.increment("validateRelationTarget");
  const dataSourceIdResult = validateRelationTarget({
    property: { relation: { data_source_id: "applications-data-source" } },
    configuredDatabase: database,
    configuredDatabaseId: database.id,
    expectedSyncedPropertyName: "Resumes",
  });
  calls.increment("validateRelationTarget");
  const wrongInverseResult = validateRelationTarget({
    property: {
      relation: {
        database_id: "applications-database",
        dual_property: { synced_property_name: "Wrong Name" },
      },
    },
    configuredDatabase: database,
    configuredDatabaseId: database.id,
    expectedSyncedPropertyName: "Resumes",
  });
  const parsed = fixture.observation.initialState.parsedApplication;
  calls.increment("buildPageProperties");
  const properties = buildPageProperties(parsed);
  calls.increment("buildJobPostingBlocks");
  const { blocks } = buildJobPostingBlocks(parsed, new Date("2026-01-01T00:00:00.000Z"));

  return {
    outcome: {
      databaseIdAccepted: databaseIdResult.errors.length === 0,
      dataSourceIdAccepted: dataSourceIdResult.errors.length === 0,
      wrongInverseRejected: wrongInverseResult.errors.length === 1,
    },
    effects: [],
    state: {
      physicalPropertyNames: Object.keys(properties).sort(),
      stableBodyHeadings: blocks
        .filter((block) => block.type.startsWith("heading_"))
        .map(blockText)
        .filter((heading) => ["Capture Summary", "Job Content"].includes(heading)),
    },
    callCounts: calls.snapshot([
      "validateRelationTarget",
      "buildPageProperties",
      "buildJobPostingBlocks",
    ]),
    cleanupResidue: {},
  };
}
