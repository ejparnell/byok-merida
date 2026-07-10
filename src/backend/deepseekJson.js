import {
  assertSupportedDeepSeekModel,
  DEEPSEEK_DEFAULT_MODEL,
  DEEPSEEK_OPENAI_CHAT_COMPLETIONS_URL,
} from "./deepseekModels.js";

const DEFAULT_MAX_ATTEMPTS = 2;

export class DeepSeekJsonClient {
  constructor({
    apiKey,
    model = DEEPSEEK_DEFAULT_MODEL,
    fetchImpl = fetch,
    logger = console,
    logPrefix = "deepseek",
    missingApiKeyMessage = "DEEPSEEK_API_KEY is required.",
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
  }) {
    this.apiKey = apiKey;
    this.model = assertSupportedDeepSeekModel(model);
    this.fetch = fetchImpl;
    this.logger = logger;
    this.logPrefix = logPrefix;
    this.missingApiKeyMessage = missingApiKeyMessage;
    this.maxAttempts = maxAttempts;
  }

  async requestJson({
    label,
    maxTokens,
    messagesForAttempt,
    logContext = {},
  }) {
    if (!this.apiKey) {
      throw new Error(this.missingApiKeyMessage);
    }

    let lastEmptyResponse = null;

    for (let attempt = 1; attempt <= this.maxAttempts; attempt += 1) {
      const retry = attempt > 1;
      const requestBody = this.buildRequestBody({
        messages: messagesForAttempt({ retry, attempt }),
        maxTokens,
      });
      this.logRequest({ attempt, label, requestBody, logContext });

      const response = await this.fetch(DEEPSEEK_OPENAI_CHAT_COMPLETIONS_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });
      const payload = await response.json().catch(() => ({}));
      const responseSummary = summarizeResponse(response, payload);

      this.logger.log(`[${this.logPrefix}] DeepSeek response`, {
        label,
        attempt,
        ...responseSummary,
      });

      if (!response.ok) {
        throw new Error(payload.message || payload.error?.message || `DeepSeek ${label} request failed with ${response.status}`);
      }

      const content = payload.choices?.[0]?.message?.content || "";
      if (!String(content).trim()) {
        lastEmptyResponse = responseSummary;
        this.logger.warn(`[${this.logPrefix}] DeepSeek returned empty content`, {
          label,
          attempt,
          willRetry: attempt < this.maxAttempts,
          finishReason: responseSummary.finishReason,
          choiceCount: responseSummary.choiceCount,
        });
        continue;
      }

      this.logger.log(`[${this.logPrefix}] DeepSeek content preview`, {
        label,
        attempt,
        contentPreview: preview(content, 900),
      });

      try {
        return {
          content,
          json: JSON.parse(content),
        };
      } catch {
        throw new Error(`DeepSeek ${label} response was not valid JSON.`);
      }
    }

    throw new Error(`DeepSeek ${label} returned empty content after ${this.maxAttempts} attempts.${lastEmptyResponse?.finishReason ? ` Last finish reason: ${lastEmptyResponse.finishReason}.` : ""}`);
  }

  buildRequestBody({ messages, maxTokens }) {
    return {
      model: this.model,
      messages,
      response_format: { type: "json_object" },
      max_tokens: maxTokens,
      stream: false,
      thinking: { type: "disabled" },
    };
  }

  logRequest({ attempt, label, requestBody, logContext }) {
    const systemPrompt = requestBody.messages.find((message) => message.role === "system")?.content || "";
    const userPrompt = requestBody.messages.find((message) => message.role === "user")?.content || "";

    this.logger.log(`[${this.logPrefix}] DeepSeek request`, {
      label,
      attempt,
      endpoint: DEEPSEEK_OPENAI_CHAT_COMPLETIONS_URL,
      model: requestBody.model,
      responseFormat: requestBody.response_format,
      maxTokens: requestBody.max_tokens,
      thinking: requestBody.thinking,
      systemPromptLength: systemPrompt.length,
      userPromptLength: userPrompt.length,
      ...logContext,
    });
  }
}

export function preview(value, maxLength) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}...` : text;
}

export function tail(value, maxLength) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `...${text.slice(-maxLength).trimStart()}` : "";
}

function summarizeResponse(response, payload) {
  const choice = payload.choices?.[0] || {};
  const content = choice.message?.content || "";

  return {
    ok: response.ok,
    status: response.status,
    choiceCount: Array.isArray(payload.choices) ? payload.choices.length : 0,
    finishReason: choice.finish_reason || "",
    contentLength: String(content).length,
    usage: payload.usage ? {
      promptTokens: payload.usage.prompt_tokens,
      completionTokens: payload.usage.completion_tokens,
      totalTokens: payload.usage.total_tokens,
    } : undefined,
  };
}
