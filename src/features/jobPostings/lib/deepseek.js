import {
  DeepSeekJsonClient,
  preview,
  tail,
} from "../../../backend/deepseekJson.js";
import { validateAnalysis } from "./analysisBlocks.js";

export class DeepSeekAnalysisClient {
  constructor({
    apiKey,
    model,
    fetchImpl = fetch,
    logger = console,
    debugContent = false,
  }) {
    this.logger = logger;
    this.debugContent = debugContent;
    this.deepseek = new DeepSeekJsonClient({
      apiKey,
      model,
      fetchImpl,
      logger,
      logPrefix: "job-analysis",
      missingApiKeyMessage: "DEEPSEEK_API_KEY is required for Job Posting Analysis.",
    });
  }

  async analyzeJobContent(jobContent) {
    const { json, content } = await this.deepseek.requestJson({
      label: "job-analysis",
      maxTokens: 3000,
      messagesForAttempt: ({ retry }) => buildMessages(jobContent, { retry }),
      logContext: {
        jobContentLength: String(jobContent || "").length,
        jobContentPreview: preview(jobContent, 900),
        jobContentTail: tail(jobContent, 400),
        ...(this.debugContent ? { jobContent } : {}),
      },
    });

    try {
      return validateAnalysis(json, jobContent);
    } catch (error) {
      this.logger.warn("[job-analysis] DeepSeek validation failed", {
        message: error.message,
        contentPreview: preview(content, 900),
      });
      throw error;
    }
  }
}

function buildMessages(jobContent, { retry }) {
  return [
    {
      role: "system",
      content: [
        "You analyze job postings for resume tailoring.",
        "Return strict JSON only.",
        "Use only evidence from the provided Job Content.",
        "Do not infer skills that are not explicit or very near synonyms of the posting text.",
        "Exclude generic traits unless tied to a concrete work mode.",
        "Each skill signal must include a short exact evidence phrase copied from Job Content.",
        retry ? "Your previous response was empty; return one non-empty JSON object now." : "",
      ].join(" "),
    },
    {
      role: "user",
      content: [
        "Analyze this Job Content and return json in exactly this shape:",
        "{",
        "  \"summary\": [\"sentence one\", \"sentence two\", \"sentence three\"],",
        "  \"skillGroups\": [",
        "    {",
        "      \"label\": \"Databases\",",
        "      \"signals\": [",
        "        { \"name\": \"PostgreSQL\", \"evidence\": \"PostgreSQL\" }",
        "      ]",
        "    }",
        "  ]",
        "}",
        "",
        "Allowed group labels: Databases, APIs & Integrations, Frameworks & Libraries, Programming Languages, Cloud & Platforms, Testing & Quality, Architecture & Systems, DevOps & Tooling, Workflow & Collaboration, Domain Knowledge, Other.",
        "",
        "Job Content:",
        jobContent,
      ].join("\n"),
    },
  ];
}
