export function createCallCounter() {
  const counts = new Map();
  return {
    increment(name) {
      counts.set(name, (counts.get(name) || 0) + 1);
    },
    snapshot(names) {
      return Object.fromEntries(names.map((name) => [name, counts.get(name) || 0]));
    },
  };
}

export function prototypeConfig(overrides = {}) {
  return {
    notionToken: "notion-secret",
    notionDatabaseId: "applications-database",
    captureToken: "capture-token",
    extensionOrigin: "chrome-extension://example",
    port: 3217,
    deepseekApiKey: "deepseek-secret",
    deepseekModel: "deepseek-v4-flash",
    ...overrides,
  };
}

export function resumeConfig(overrides = {}) {
  return prototypeConfig({
    notionResumeDatabaseId: "resumes-database",
    notionNotesDatabaseId: "notes-database",
    fitRuntimeUrl: "http://127.0.0.1:3218",
    fitRuntimePort: 3218,
    ...overrides,
  });
}

export function quietLogger() {
  return { log() {}, warn() {}, error() {} };
}

export function notionBlock(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: [{ type: "text", plain_text: content, text: { content } }],
    },
  };
}

export function richText(content) {
  return {
    rich_text: [{ type: "text", plain_text: content, text: { content } }],
  };
}

export function blockText(block) {
  return (block?.[block.type]?.rich_text || [])
    .map((part) => part.plain_text || part.text?.content || "")
    .join("")
    .trim();
}
