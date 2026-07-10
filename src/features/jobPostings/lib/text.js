export function normalizeText(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+$/gm, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim();
}

export function stripHtml(html) {
  return String(html || "")
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, " ")
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, " ")
    .replace(/<\/(p|div|section|article|li|h[1-6]|br)>/gi, "\n")
    .replace(/<li\b[^>]*>/gi, "- ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'");
}

export function firstNonEmptyLine(text) {
  return normalizeText(text)
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean) || "";
}

export function truncateWithNote(text, maxLength) {
  const normalized = normalizeText(text);
  if (normalized.length <= maxLength) {
    return { text: normalized, truncated: false };
  }

  return {
    text: normalized.slice(0, maxLength).trimEnd(),
    truncated: true,
  };
}

export function toPlainSingleLine(value, maxLength = 240) {
  const singleLine = normalizeText(value).replace(/\s*\n+\s*/g, " ");
  return singleLine.length > maxLength
    ? `${singleLine.slice(0, maxLength - 1).trimEnd()}...`
    : singleLine;
}
