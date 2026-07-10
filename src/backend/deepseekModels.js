export const DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash";
export const DEEPSEEK_SUPPORTED_MODELS = Object.freeze([
  "deepseek-v4-flash",
  "deepseek-v4-pro",
]);
export const DEEPSEEK_DEPRECATED_MODEL_ALIASES = Object.freeze([
  "deepseek-chat",
  "deepseek-reasoner",
]);
export const DEEPSEEK_MODEL_DEPRECATION_DATE = "2026-07-24 15:59 UTC";

// DeepSeek's v4 models use the OpenAI-compatible chat-completions endpoint.
// "chat" here is the endpoint shape, not the deprecated `deepseek-chat` model alias.
export const DEEPSEEK_OPENAI_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions";

const supportedModelSet = new Set(DEEPSEEK_SUPPORTED_MODELS);
const deprecatedAliasSet = new Set(DEEPSEEK_DEPRECATED_MODEL_ALIASES);

export function normalizeDeepSeekModel(value) {
  const model = String(value || "").trim();
  return model || DEEPSEEK_DEFAULT_MODEL;
}

export function validateDeepSeekModel(value) {
  const model = normalizeDeepSeekModel(value);

  if (deprecatedAliasSet.has(model)) {
    return {
      valid: false,
      model,
      error: `DEEPSEEK_MODEL=${model} uses a deprecated DeepSeek model alias. Use ${DEEPSEEK_SUPPORTED_MODELS.join(" or ")} instead; DeepSeek deprecates ${DEEPSEEK_DEPRECATED_MODEL_ALIASES.join(" and ")} on ${DEEPSEEK_MODEL_DEPRECATION_DATE}.`,
    };
  }

  if (!supportedModelSet.has(model)) {
    return {
      valid: false,
      model,
      error: `DEEPSEEK_MODEL must be one of ${DEEPSEEK_SUPPORTED_MODELS.join(", ")}.`,
    };
  }

  return {
    valid: true,
    model,
    error: "",
  };
}

export function assertSupportedDeepSeekModel(value) {
  const result = validateDeepSeekModel(value);
  if (!result.valid) {
    throw new Error(result.error);
  }
  return result.model;
}
