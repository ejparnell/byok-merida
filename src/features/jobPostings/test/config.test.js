import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig, validateConfig } from "../backend/config.js";

test("loadConfig defaults DeepSeek model to flash", () => {
  const config = loadConfig({
    NOTION_TOKEN: "secret",
    NOTION_DATABASE_ID: "database",
    CAPTURE_TOKEN: "local-token",
    EXTENSION_ORIGIN: "chrome-extension://abc",
    PORT: "3217",
    DEEPSEEK_API_KEY: "",
    DEEPSEEK_MODEL: "",
    DEBUG_ANALYSIS_CONTENT: "0",
  });

  assert.equal(config.deepseekApiKey, "");
  assert.equal(config.deepseekModel, "deepseek-v4-flash");
  assert.equal(config.debugAnalysisContent, false);
});

test("loadConfig supports DeepSeek key and model override", () => {
  const config = loadConfig({
    NOTION_TOKEN: "secret",
    NOTION_DATABASE_ID: "database",
    CAPTURE_TOKEN: "local-token",
    EXTENSION_ORIGIN: "chrome-extension://abc",
    PORT: "3217",
    DEEPSEEK_API_KEY: "deepseek-secret",
    DEEPSEEK_MODEL: "deepseek-v4-pro",
    DEBUG_ANALYSIS_CONTENT: "1",
  });

  assert.equal(config.deepseekApiKey, "deepseek-secret");
  assert.equal(config.deepseekModel, "deepseek-v4-pro");
  assert.equal(config.debugAnalysisContent, true);
});

test("validateConfig rejects deprecated DeepSeek model aliases", () => {
  for (const model of ["deepseek-chat", "deepseek-reasoner"]) {
    const config = loadConfig({
      NOTION_TOKEN: "secret",
      NOTION_DATABASE_ID: "database",
      CAPTURE_TOKEN: "local-token",
      EXTENSION_ORIGIN: "chrome-extension://abc",
      PORT: "3217",
      DEEPSEEK_MODEL: model,
    });

    const result = validateConfig(config);

    assert.equal(result.valid, false);
    assert.match(result.errors.join(" "), /deprecated DeepSeek model alias/);
    assert.match(result.errors.join(" "), /deepseek-v4-flash/);
  }
});

test("validateConfig rejects unsupported DeepSeek model ids", () => {
  const config = loadConfig({
    NOTION_TOKEN: "secret",
    NOTION_DATABASE_ID: "database",
    CAPTURE_TOKEN: "local-token",
    EXTENSION_ORIGIN: "chrome-extension://abc",
    PORT: "3217",
    DEEPSEEK_MODEL: "deepseek-chat-latest",
  });

  const result = validateConfig(config);

  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /DEEPSEEK_MODEL must be one of/);
});

test("loadConfig supports Resume Fit Analysis runtime settings", () => {
  const config = loadConfig({
    NOTION_TOKEN: "secret",
    NOTION_DATABASE_ID: "database",
    NOTION_NOTES_DATABASE_ID: "notes-database",
    CAPTURE_TOKEN: "local-token",
    EXTENSION_ORIGIN: "chrome-extension://abc",
    FIT_RUNTIME_PORT: "3333",
    FIT_RUNTIME_URL: "http://127.0.0.1:3333",
    PYTHON_BIN: "/tmp/python",
  });

  assert.equal(config.notionNotesDatabaseId, "notes-database");
  assert.equal(config.fitRuntimePort, 3333);
  assert.equal(config.fitRuntimeUrl, "http://127.0.0.1:3333");
  assert.equal(config.pythonBin, "/tmp/python");
});
