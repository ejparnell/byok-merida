import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  loadParityInventory,
  validateParityInventory,
} from "./parityContract.js";

test("versioned parity inventory classifies every required migration area", () => {
  const inventory = loadParityInventory();

  assert.deepEqual(summarizeInventory(inventory), {
    schemaVersion: 1,
    contractVersion: "prototype-parity-v1",
    classifications: [
      "deferred",
      "known_defect",
      "parity_required",
      "superseded",
      "target_addition",
    ],
    coverageAreas: [
      "application_analysis",
      "artifact_creation",
      "capture",
      "capture_evidence",
      "evidence_validation",
      "failure_cleanup",
      "idempotency",
      "notion_persistence",
      "privacy",
      "resume_creation",
    ],
  });
});

test("shipped parity fixtures satisfy the observation contract", () => {
  const inventory = loadParityInventory();

  assert.deepEqual(validateParityInventory(inventory), []);
});

test("human parity inventory references every versioned fixture", () => {
  const inventory = loadParityInventory();
  const reportUrl = new URL(
    "../../.scratch/proposed-final-app/assets/prototype-parity-inventory.md",
    import.meta.url,
  );
  const report = readFileSync(reportUrl, "utf8");

  assert.deepEqual(
    inventory.fixtures.filter((fixture) => !report.includes(`| ${fixture.id} |`)).map((fixture) => fixture.id),
    [],
  );
});

test("every human inventory row names a stable fixture contract", () => {
  const inventory = loadParityInventory();
  const fixtureIds = new Set(inventory.fixtures.map((fixture) => fixture.id));
  const reportUrl = new URL(
    "../../.scratch/proposed-final-app/assets/prototype-parity-inventory.md",
    import.meta.url,
  );
  const report = readFileSync(reportUrl, "utf8");
  const sectionNames = [
    "Capture Inventory",
    "Application Analysis Inventory",
    "Resume Creation Inventory",
    "Notion Persistence And Artifact Inventory",
    "Privacy And Observability Inventory",
    "Known Defects",
  ];
  const invalidRows = sectionNames.flatMap((sectionName) => (
    markdownTableRows(markdownSection(report, sectionName))
      .filter((row) => {
        const rowIds = row.match(/[A-Z]+(?:-[A-Z]+)*-\d{3}/g) || [];
        return rowIds.length === 0 || rowIds.some((id) => !fixtureIds.has(id));
      })
      .map((row) => `${sectionName}: ${row}`)
  ));

  assert.deepEqual(invalidRows, []);
});

function markdownSection(markdown, heading) {
  const start = markdown.indexOf(`## ${heading}`);
  const nextHeading = markdown.indexOf("\n## ", start + 3);
  return markdown.slice(start, nextHeading === -1 ? undefined : nextHeading);
}

function markdownTableRows(section) {
  return section
    .split("\n")
    .filter((line) => line.startsWith("|") && !line.includes("---"))
    .slice(1);
}

function summarizeInventory(inventory) {
  return {
    schemaVersion: inventory.schemaVersion,
    contractVersion: inventory.contractVersion,
    classifications: [...new Set(inventory.fixtures.map((fixture) => fixture.classification))].sort(),
    coverageAreas: [...new Set(inventory.fixtures.flatMap((fixture) => fixture.coverage))].sort(),
  };
}
