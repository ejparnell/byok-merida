import { readFileSync } from "node:fs";

const INVENTORY_URL = new URL("./fixtures/prototype-parity.v1.json", import.meta.url);
const CLASSIFICATIONS = new Set([
  "parity_required",
  "superseded",
  "target_addition",
  "known_defect",
  "deferred",
]);
const COVERAGE_AREAS = new Set([
  "capture_evidence",
  "capture",
  "application_analysis",
  "resume_creation",
  "notion_persistence",
  "evidence_validation",
  "artifact_creation",
  "idempotency",
  "failure_cleanup",
  "privacy",
]);

export function loadParityInventory() {
  return JSON.parse(readFileSync(INVENTORY_URL, "utf8"));
}

export function validateParityInventory(inventory) {
  const errors = [];
  const ids = new Set();

  if (inventory?.schemaVersion !== 1) {
    errors.push("schemaVersion must be 1");
  }
  if (inventory?.contractVersion !== "prototype-parity-v1") {
    errors.push("contractVersion must be prototype-parity-v1");
  }
  if (!Array.isArray(inventory?.fixtures)) {
    return [...errors, "fixtures must be an array"];
  }

  for (const [index, fixture] of inventory.fixtures.entries()) {
    const label = fixture?.id || `fixture[${index}]`;
    requireString(fixture, "id", label, errors);
    requireString(fixture, "title", label, errors);
    requireString(fixture, "authority", label, errors);
    requireString(fixture, "expectedTargetDisposition", label, errors);

    if (ids.has(fixture?.id)) errors.push(`${label}: id must be unique`);
    ids.add(fixture?.id);

    if (!CLASSIFICATIONS.has(fixture?.classification)) {
      errors.push(`${label}: classification is invalid`);
    }
    if (typeof fixture?.prototypeExecutable !== "boolean") {
      errors.push(`${label}: prototypeExecutable must be boolean`);
    }
    if (!Array.isArray(fixture?.coverage) || fixture.coverage.length === 0) {
      errors.push(`${label}: coverage must be non-empty`);
    } else if (fixture.coverage.some((area) => !COVERAGE_AREAS.has(area))) {
      errors.push(`${label}: coverage contains an unknown area`);
    }
    if (!Array.isArray(fixture?.evidenceSources) || fixture.evidenceSources.length === 0) {
      errors.push(`${label}: evidenceSources must be non-empty`);
    }

    const versions = fixture?.versions;
    if (!isRecord(versions) || versions.fixtureSchema !== inventory.schemaVersion) {
      errors.push(`${label}: versions.fixtureSchema must match schemaVersion`);
    }
    if (!isRecord(versions)
      || !("scoringPolicy" in versions)
      || !("normalizationDictionary" in versions)) {
      errors.push(`${label}: versions must name scoring and normalization policies`);
    }

    const observation = fixture?.observation;
    if (!isRecord(observation)) {
      errors.push(`${label}: observation must be an object`);
      continue;
    }
    requireString(observation, "action", `${label}.observation`, errors);
    if (!isRecord(observation.initialState)) {
      errors.push(`${label}: observation.initialState must be an object`);
    }
    if (!isRecord(observation.dependencyOutputs)) {
      errors.push(`${label}: observation.dependencyOutputs must be an object`);
    }
    if (!("expectedOutcome" in observation)) {
      errors.push(`${label}: observation.expectedOutcome is required`);
    }
    if (!Array.isArray(observation.expectedEffects)) {
      errors.push(`${label}: observation.expectedEffects must be an array`);
    }
    if (!isRecord(observation.expectedState)) {
      errors.push(`${label}: observation.expectedState must be an object`);
    }
    if (!isRecord(observation.expectedCallCounts)) {
      errors.push(`${label}: observation.expectedCallCounts must be an object`);
    }
    if (!Array.isArray(observation.forbiddenEffects)) {
      errors.push(`${label}: observation.forbiddenEffects must be an array`);
    }
    if (!isRecord(observation.cleanupResidue)) {
      errors.push(`${label}: observation.cleanupResidue must be an object`);
    }
    if (fixture.prototypeExecutable && typeof observation.runner !== "string") {
      errors.push(`${label}: executable observations require a runner`);
    }
  }

  return errors;
}

function requireString(value, key, label, errors) {
  if (typeof value?.[key] !== "string" || value[key].trim() === "") {
    errors.push(`${label}: ${key} must be a non-empty string`);
  }
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
