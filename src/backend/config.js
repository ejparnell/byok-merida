import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  normalizeDeepSeekModel,
  validateDeepSeekModel,
} from "./deepseekModels.js";

export function loadConfig(env = process.env) {
  const fileEnv = readDotEnv(resolve(process.cwd(), ".env"));
  const merged = { ...fileEnv, ...env };

  return {
    notionToken: merged.NOTION_TOKEN || "",
    notionDatabaseId: merged.NOTION_DATABASE_ID || "",
    notionResumeDatabaseId: merged.NOTION_RESUME_DATABASE_ID || "",
    notionNotesDatabaseId: merged.NOTION_NOTES_DATABASE_ID || "",
    captureToken: merged.CAPTURE_TOKEN || "",
    extensionOrigin: merged.EXTENSION_ORIGIN || "",
    port: Number(merged.PORT || 3217),
    fitRuntimePort: Number(merged.FIT_RUNTIME_PORT || 3218),
    fitRuntimeUrl: merged.FIT_RUNTIME_URL || `http://127.0.0.1:${merged.FIT_RUNTIME_PORT || 3218}`,
    pythonBin: merged.PYTHON_BIN || ".venv/bin/python",
    deepseekApiKey: merged.DEEPSEEK_API_KEY || "",
    deepseekModel: normalizeDeepSeekModel(merged.DEEPSEEK_MODEL),
    debugCapture: merged.DEBUG_CAPTURE !== "0",
    debugAnalysisContent: merged.DEBUG_ANALYSIS_CONTENT === "1",
  };
}

export function validateConfig(config) {
  const errors = [];

  if (!config.notionToken) errors.push("NOTION_TOKEN is required.");
  if (!config.notionDatabaseId) errors.push("NOTION_DATABASE_ID is required.");
  if (!config.captureToken) errors.push("CAPTURE_TOKEN is required.");
  if (!config.extensionOrigin) errors.push("EXTENSION_ORIGIN is required for browser CORS.");
  if (!Number.isInteger(config.port) || config.port <= 0) errors.push("PORT must be a positive integer.");
  if (config.fitRuntimePort !== undefined && (!Number.isInteger(config.fitRuntimePort) || config.fitRuntimePort <= 0)) {
    errors.push("FIT_RUNTIME_PORT must be a positive integer.");
  }
  const modelResult = validateDeepSeekModel(config.deepseekModel);
  if (!modelResult.valid) {
    errors.push(modelResult.error);
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

function readDotEnv(path) {
  if (!existsSync(path)) {
    return {};
  }

  const output = {};
  const content = readFileSync(path, "utf8");

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const separator = trimmed.indexOf("=");
    if (separator === -1) {
      continue;
    }

    const key = trimmed.slice(0, separator).trim();
    const rawValue = trimmed.slice(separator + 1).trim();
    output[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }

  return output;
}
