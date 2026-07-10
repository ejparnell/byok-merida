import test from "node:test";
import assert from "node:assert/strict";
import { DeepSeekJsonClient } from "../deepseekJson.js";

test("DeepSeekJsonClient sends JSON mode requests through the DeepSeek endpoint", async () => {
  let request;
  const client = new DeepSeekJsonClient({
    apiKey: "deepseek-secret",
    model: "deepseek-v4-pro",
    logger: quietLogger(),
    fetchImpl: async (url, options) => {
      request = { url, options, body: JSON.parse(options.body) };
      return jsonResponse({ value: true });
    },
  });

  const result = await client.requestJson({
    label: "test-json",
    maxTokens: 123,
    messagesForAttempt: () => [{ role: "user", content: "Return JSON." }],
  });

  assert.equal(request.url, "https://api.deepseek.com/chat/completions");
  assert.equal(request.options.headers.Authorization, "Bearer deepseek-secret");
  assert.equal(request.body.model, "deepseek-v4-pro");
  assert.deepEqual(request.body.response_format, { type: "json_object" });
  assert.deepEqual(request.body.thinking, { type: "disabled" });
  assert.equal(request.body.max_tokens, 123);
  assert.deepEqual(result.json, { value: true });
});

test("DeepSeekJsonClient retries empty content with retry-aware messages", async () => {
  let calls = 0;
  const client = new DeepSeekJsonClient({
    apiKey: "deepseek-secret",
    logger: quietLogger(),
    fetchImpl: async () => {
      calls += 1;
      return calls === 1
        ? jsonResponse("", { finishReason: "stop" })
        : jsonResponse({ ok: true });
    },
  });

  const result = await client.requestJson({
    label: "retry-json",
    maxTokens: 100,
    messagesForAttempt: ({ retry }) => [
      { role: "system", content: retry ? "Retry with JSON." : "Return JSON." },
    ],
  });

  assert.equal(calls, 2);
  assert.deepEqual(result.json, { ok: true });
});

test("DeepSeekJsonClient reports invalid JSON with the request label", async () => {
  const client = new DeepSeekJsonClient({
    apiKey: "deepseek-secret",
    logger: quietLogger(),
    fetchImpl: async () => jsonResponse("{"),
  });

  await assert.rejects(
    () => client.requestJson({
      label: "bad-json",
      maxTokens: 100,
      messagesForAttempt: () => [{ role: "user", content: "Return JSON." }],
    }),
    /bad-json response was not valid JSON/,
  );
});

function jsonResponse(content, { ok = true, status = 200, finishReason = "stop" } = {}) {
  const responseContent = typeof content === "string" ? content : JSON.stringify(content);
  return {
    ok,
    status,
    async json() {
      return {
        choices: [
          {
            finish_reason: finishReason,
            message: { content: responseContent },
          },
        ],
      };
    },
  };
}

function quietLogger() {
  return {
    log() {},
    warn() {},
  };
}
