import test from "node:test";
import assert from "node:assert/strict";
import { DeepSeekAnalysisClient } from "../lib/deepseek.js";

test("DeepSeekAnalysisClient sends JSON mode request and validates response", async () => {
  let request;
  const client = new DeepSeekAnalysisClient({
    apiKey: "deepseek-secret",
    model: "deepseek-v4-pro",
    fetchImpl: async (url, options) => {
      request = { url, options, body: JSON.parse(options.body) };
      return {
        ok: true,
        async json() {
          return {
            choices: [
              {
                message: {
                  content: JSON.stringify({
                    summary: ["One.", "Two.", "Three."],
                    skillGroups: [
                      {
                        label: "Databases",
                        signals: [{ name: "PostgreSQL", evidence: "PostgreSQL" }],
                      },
                    ],
                  }),
                },
              },
            ],
          };
        },
      };
    },
  });

  const result = await client.analyzeJobContent("Use PostgreSQL.");

  assert.equal(request.url, "https://api.deepseek.com/chat/completions");
  assert.equal(request.options.headers.Authorization, "Bearer deepseek-secret");
  assert.equal(request.body.model, "deepseek-v4-pro");
  assert.deepEqual(request.body.response_format, { type: "json_object" });
  assert.deepEqual(request.body.thinking, { type: "disabled" });
  assert.equal(result.skillGroups[0].signals[0].name, "PostgreSQL");
});

test("DeepSeekAnalysisClient rejects deprecated DeepSeek model aliases", () => {
  assert.throws(
    () => new DeepSeekAnalysisClient({
      apiKey: "deepseek-secret",
      model: "deepseek-chat",
    }),
    /deprecated DeepSeek model alias/,
  );
});

test("DeepSeekAnalysisClient retries once when JSON mode returns empty content", async () => {
  let calls = 0;
  const logs = [];
  const client = new DeepSeekAnalysisClient({
    apiKey: "deepseek-secret",
    logger: {
      log(label, payload) {
        logs.push({ level: "log", label, payload });
      },
      warn(label, payload) {
        logs.push({ level: "warn", label, payload });
      },
    },
    fetchImpl: async () => {
      calls += 1;
      return {
        ok: true,
        status: 200,
        async json() {
          if (calls === 1) {
            return {
              choices: [{ finish_reason: "stop", message: { content: "" } }],
              usage: { prompt_tokens: 100, completion_tokens: 0, total_tokens: 100 },
            };
          }

          return {
            choices: [
              {
                finish_reason: "stop",
                message: {
                  content: JSON.stringify({
                    summary: ["One.", "Two.", "Three."],
                    skillGroups: [
                      {
                        label: "Databases",
                        signals: [{ name: "PostgreSQL", evidence: "PostgreSQL" }],
                      },
                    ],
                  }),
                },
              },
            ],
          };
        },
      };
    },
  });

  const result = await client.analyzeJobContent("Use PostgreSQL.");

  assert.equal(calls, 2);
  assert.equal(result.skillGroups[0].label, "Databases");
  assert.equal(logs.some((entry) => entry.level === "warn" && entry.label.includes("empty content")), true);
});

test("DeepSeekAnalysisClient surfaces API errors without exposing payloads", async () => {
  const client = new DeepSeekAnalysisClient({
    apiKey: "deepseek-secret",
    fetchImpl: async () => ({
      ok: false,
      status: 429,
      async json() {
        return { error: { message: "Rate limited." } };
      },
    }),
  });

  await assert.rejects(
    () => client.analyzeJobContent("Use PostgreSQL."),
    /Rate limited/,
  );
});
