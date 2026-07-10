import test from "node:test";
import assert from "node:assert/strict";
import { DeepSeekResumeClient } from "../lib/deepseekResume.js";

test("DeepSeekResumeClient sends v4 model request through DeepSeek's OpenAI-compatible endpoint", async () => {
  let request;
  const client = new DeepSeekResumeClient({
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
                    requirements: [
                      {
                        id: "req-1",
                        text: "Build REST APIs",
                        type: "required skill",
                        category: "APIs & Integrations",
                        importance: "required",
                        evidence: "REST APIs",
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
    logger: { log() {} },
  });

  const requirements = await client.extractFitRequirements({
    jobContent: "Build REST APIs.",
    jobPostingAnalysis: "The role needs REST APIs.",
  });

  assert.equal(request.url, "https://api.deepseek.com/chat/completions");
  assert.equal(request.body.model, "deepseek-v4-pro");
  assert.deepEqual(request.body.response_format, { type: "json_object" });
  assert.deepEqual(request.body.thinking, { type: "disabled" });
  assert.equal(requirements[0].text, "Build REST APIs");
});

test("DeepSeekResumeClient promotes tool requirements found in required Job Content sections", async () => {
  const client = new DeepSeekResumeClient({
    apiKey: "deepseek-secret",
    fetchImpl: async () => ({
      ok: true,
      async json() {
        return {
          choices: [
            {
              message: {
                content: JSON.stringify({
                  requirements: [
                    {
                      id: "req-1",
                      text: "Use React to build frontend workflows",
                      type: "tool/technology",
                      category: "Frameworks & Libraries",
                      importance: "signal",
                      evidence: "React",
                    },
                  ],
                }),
              },
            },
          ],
        };
      },
    }),
    logger: { log() {} },
  });

  const requirements = await client.extractFitRequirements({
    jobContent: [
      "Required Qualifications",
      "- React",
      "- TypeScript",
      "",
      "Preferred Qualifications",
      "- Kubernetes",
    ].join("\n"),
    jobPostingAnalysis: "The role needs React and TypeScript.",
  });

  assert.equal(requirements[0].type, "tool/technology");
  assert.equal(requirements[0].importance, "required");
});

test("DeepSeekResumeClient keeps optional tool requirements preferred", async () => {
  const client = new DeepSeekResumeClient({
    apiKey: "deepseek-secret",
    fetchImpl: async () => ({
      ok: true,
      async json() {
        return {
          choices: [
            {
              message: {
                content: JSON.stringify({
                  requirements: [
                    {
                      id: "req-1",
                      text: "Experience with Kubernetes",
                      type: "tool/technology",
                      category: "DevOps & Tooling",
                      importance: "signal",
                      evidence: "Kubernetes",
                    },
                  ],
                }),
              },
            },
          ],
        };
      },
    }),
    logger: { log() {} },
  });

  const requirements = await client.extractFitRequirements({
    jobContent: [
      "Required Qualifications",
      "- React",
      "- TypeScript",
      "",
      "Nice to have",
      "- Kubernetes",
    ].join("\n"),
    jobPostingAnalysis: "Kubernetes is optional.",
  });

  assert.equal(requirements[0].importance, "preferred");
});

test("DeepSeekResumeClient rejects deprecated DeepSeek model aliases", () => {
  assert.throws(
    () => new DeepSeekResumeClient({
      apiKey: "deepseek-secret",
      model: "deepseek-chat",
    }),
    /deprecated DeepSeek model alias/,
  );
});

test("DeepSeekResumeClient includes the fixed Elizabeth resume template in generation prompts", async () => {
  let request;
  const client = new DeepSeekResumeClient({
    apiKey: "deepseek-secret",
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
                    resume: {
                      name: "Elizabeth Parnell",
                      summary: "Software engineer focused on APIs.",
                      skills: [],
                      roles: [],
                      sections: [],
                    },
                  }),
                },
              },
            ],
          };
        },
      };
    },
    logger: { log() {} },
  });

  await client.generateResume({
    resumeName: "Engineer at Example",
    jobPosting: { jobTitle: "Engineer", companyName: "Example" },
    masterEvidenceItems: [],
    fitScore: { requirements: [] },
    workExperienceRoles: [
      {
        templateId: "clinmatchgo-software-engineer",
        sourceSection: "Software Engineer, ClinMatchGO",
        heading: "Software Engineer, ClinMatchGO",
        title: "Software Engineer",
        organization: "ClinMatchGO",
        dateRange: "2025 - Present",
        bulletEvidenceIds: ["evidence-1"],
      },
    ],
  });

  const userPrompt = request.body.messages.find((message) => message.role === "user").content;

  assert.match(userPrompt, /# Elizabeth Parnell/);
  assert.match(userPrompt, /Boston, MA \| elizabethprnll@gmail.com/);
  assert.match(userPrompt, /ClinMatchGO \| 2025 - Present/);
  assert.match(userPrompt, /Wayfair \| 2018 - 2021/);
  assert.match(userPrompt, /templateId/);
});
