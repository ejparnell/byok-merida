const LOCAL_CONFIG = globalThis.MERIDA_JOB_CAPTURE_CONFIG || {};
const DEFAULT_BACKEND_URL = LOCAL_CONFIG.backendUrl || "http://127.0.0.1:3217";

const elements = {
  statusText: document.querySelector("#statusText"),
  optionsButton: document.querySelector("#optionsButton"),
  fillFormButton: document.querySelector("#fillFormButton"),
  resultPanel: document.querySelector("#resultPanel"),
  reviewForm: document.querySelector("#reviewForm"),
  reviewTitle: document.querySelector("#reviewTitle"),
  reviewCompany: document.querySelector("#reviewCompany"),
  reviewJobTitle: document.querySelector("#reviewJobTitle"),
  reviewLocation: document.querySelector("#reviewLocation"),
  reviewJobUrl: document.querySelector("#reviewJobUrl"),
  reviewContent: document.querySelector("#reviewContent"),
};

let activeParsed = null;

elements.optionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

elements.fillFormButton.addEventListener("click", async () => {
  await fillReviewFormFromCurrentPage();
});

elements.reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await confirmReviewedPosting();
});

void refreshHealth();

async function fillReviewFormFromCurrentPage() {
  setBusy(true);
  hideReview();
  showResult("Working", "Reading the current page...");

  try {
    const { config, evidence } = await collectCurrentPageEvidence("fill-form");
    const result = await postJson(config, "/parse", evidence);
    console.log("backend result", result);
    renderParseResult(result);
  } catch (error) {
    console.error("[Merida Job Capture] fill form failed", error);
    renderActionError(error);
  } finally {
    setBusy(false);
  }
}

async function confirmReviewedPosting() {
  if (!activeParsed) {
    return;
  }

  setBusy(true);
  try {
    const config = await getExtensionConfig();
    const parsed = {
      ...activeParsed,
      jobPostingTitle: elements.reviewTitle.value,
      companyName: elements.reviewCompany.value,
      jobTitle: elements.reviewJobTitle.value,
      location: elements.reviewLocation.value,
      jobUrl: elements.reviewJobUrl.value,
      jobContent: elements.reviewContent.value,
    };

    const result = await postJson(config, "/confirm", { parsed });
    renderCreateResult(result);
  } catch (error) {
    renderBackendOffline(error);
  } finally {
    setBusy(false);
  }
}

async function collectCurrentPageEvidence(actionName) {
  const config = await getExtensionConfig();
  if (!config.captureToken) {
    throw userVisibleError("Capture token is missing. Open options and save the local capture token.");
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    throw userVisibleError("No active tab was found.");
  }

  console.groupCollapsed(`[Merida Job Capture] ${actionName}`);
  try {
    console.log("active tab", {
      id: tab.id,
      url: tab.url,
      title: tab.title,
    });

    let injections;
    try {
      injections = await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        func: collectSourcePageFrameEvidence,
      });
    } catch (error) {
      console.error("page capture injection failed", error);
      throw userVisibleError(`Could not read the current page: ${error.message || error}`);
    }

    console.log("frame injection results", summarizeInjections(injections));

    const evidence = buildCaptureEvidencePayload(injections, tab.url);
    console.log("capture evidence payload", summarizeEvidencePayload(evidence));
    return { config, evidence };
  } finally {
    console.groupEnd();
  }
}

async function refreshHealth() {
  try {
    const config = await getExtensionConfig();
    if (!config.captureToken) {
      elements.statusText.textContent = "Capture token missing.";
      return;
    }

    const health = await getJson(config, "/health?validate=1");
    if (health.ok) {
      elements.statusText.textContent = "Backend online. Notion schema valid.";
      return;
    }

    elements.statusText.textContent = health.errors?.[0] || health.notionSchema?.errors?.[0] || "Backend needs configuration.";
  } catch {
    elements.statusText.textContent = `Backend offline at ${(await getExtensionConfig()).backendUrl}.`;
  }
}

function renderCreateResult(result) {
  hideReview();
  console.log("[Merida Job Capture] render result", result);

  if (result.type === "created") {
    showResult("Created", "The Notion page was created.", result.summary, result.page?.url);
    return;
  }

  if (result.type === "already_captured") {
    showResult("Already Captured", "This Job URL already exists in Notion.", result.summary, result.page?.url);
    return;
  }

  if (result.type === "needs_review") {
    activeParsed = result.parsed;
    showResult("Needs Review", (result.reasons || []).join(" ") || "Review the parsed fields before creating the Notion page.", result.summary);
    showReview(result.parsed);
    return;
  }

  showResult("Failed", failureMessage(result), result.summary);
}

function renderParseResult(result) {
  hideReview();
  console.log("[Merida Job Capture] render parse result", result);

  if (result.type === "parsed") {
    activeParsed = result.parsed;
    const reasons = (result.reasons || []).filter(Boolean).join(" ");
    const message = reasons
      ? `Review and edit the parsed fields before creating the Notion page. ${reasons}`
      : "Review and edit the parsed fields before creating the Notion page.";
    showResult("Form Filled", message, result.summary);
    showReview(result.parsed);
    return;
  }

  showResult("Failed", failureMessage(result), result.summary);
}

function renderBackendOffline(error) {
  showResult("Backend Offline", `Could not reach the local backend. ${error.message || ""}`.trim());
}

function renderActionError(error) {
  if (error?.userVisible) {
    showResult("Failed", error.message);
    return;
  }

  renderBackendOffline(error);
}

function userVisibleError(message) {
  const error = new Error(message);
  error.userVisible = true;
  return error;
}

function failureMessage(result) {
  const base = result.message || result.reason || "Request failed.";
  const errors = Array.isArray(result.errors) && result.errors.length > 0
    ? ` ${result.errors.join(" ")}`
    : "";
  const warnings = Array.isArray(result.warnings) && result.warnings.length > 0
    ? ` ${result.warnings.join(" ")}`
    : "";

  if (!result.debug) {
    return `${base}${errors}${warnings}`;
  }

  const details = [
    `frames=${result.debug.frameCount || 0}`,
    `selected=${result.debug.selectedTextLength || 0}`,
    `visible=${result.debug.visibleTextLength || 0}`,
    `html=${result.debug.semanticHtmlLength || 0}`,
  ].join(", ");
  return `${base}${errors}${warnings} (${details})`;
}

function showReview(parsed) {
  elements.reviewTitle.value = parsed.jobPostingTitle || "";
  elements.reviewCompany.value = parsed.companyName || "";
  elements.reviewJobTitle.value = parsed.jobTitle || "";
  elements.reviewLocation.value = parsed.location || "";
  elements.reviewJobUrl.value = parsed.jobUrl || "";
  elements.reviewContent.value = parsed.jobContent || "";
  elements.reviewForm.hidden = false;
}

function hideReview() {
  activeParsed = null;
  elements.reviewForm.hidden = true;
}

function showResult(title, message, summary, pageUrl) {
  elements.resultPanel.hidden = false;
  elements.resultPanel.innerHTML = "";

  const heading = document.createElement("h2");
  heading.textContent = title;
  elements.resultPanel.append(heading);

  const paragraph = document.createElement("p");
  paragraph.textContent = message;
  elements.resultPanel.append(paragraph);

  if (pageUrl) {
    const link = document.createElement("a");
    link.href = pageUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open Notion page";
    elements.resultPanel.append(link);
  }

  if (summary) {
    elements.resultPanel.append(renderSummary(summary));
  }
}

function renderSummary(summary) {
  const list = document.createElement("dl");
  list.className = "summary";

  for (const [label, value] of [
    ["Job Posting", summary.jobPostingTitle],
    ["Company", summary.companyName],
    ["Job Title", summary.jobTitle],
    ["Location", summary.location],
  ]) {
    if (!value) continue;
    const group = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    group.append(term, description);
    list.append(group);
  }

  return list;
}

function setBusy(isBusy) {
  elements.fillFormButton.disabled = isBusy;
  for (const button of elements.reviewForm.querySelectorAll("button")) {
    button.disabled = isBusy;
  }
}

function buildCaptureEvidencePayload(injections, tabUrl) {
  const frames = Array.isArray(injections)
    ? injections.map((injection) => ({
      frameId: injection.frameId,
      documentId: injection.documentId,
      ...(injection.result || {}),
    })).filter((frame) => Object.keys(frame).length > 2)
    : [];

  return {
    tabUrl: tabUrl || "",
    frames,
  };
}

async function getExtensionConfig() {
  const values = await chrome.storage.local.get(["backendUrl", "captureToken"]);
  return {
    backendUrl: values.backendUrl || LOCAL_CONFIG.backendUrl || DEFAULT_BACKEND_URL,
    captureToken: values.captureToken || LOCAL_CONFIG.captureToken || "",
  };
}

async function getJson(config, path) {
  const response = await fetch(`${config.backendUrl}${path}`, {
    headers: { "X-Capture-Token": config.captureToken },
  });
  return readResponse(response);
}

async function postJson(config, path, body) {
  const response = await fetch(`${config.backendUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Capture-Token": config.captureToken,
    },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

async function readResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || `Request failed with ${response.status}`);
  }
  return payload;
}

function collectSourcePageFrameEvidence() {
  function localJoinUnique(values) {
    const seen = new Set();
    const parts = [];

    for (const value of values) {
      const text = String(value || "").trim();
      if (!text || seen.has(text)) {
        continue;
      }
      seen.add(text);
      parts.push(text);
    }

    return parts.join("\n\n");
  }

  function localCollectMetadata() {
    const meta = {};
    for (const tag of document.querySelectorAll("meta[name], meta[property]")) {
      const key = tag.getAttribute("property") || tag.getAttribute("name");
      const content = tag.getAttribute("content");
      if (key && content) {
        meta[key] = content;
      }
    }

    const jsonLd = [];
    for (const script of document.querySelectorAll("script[type='application/ld+json']")) {
      try {
        jsonLd.push(JSON.parse(script.textContent));
      } catch {
        // Ignore malformed page metadata.
      }
    }

    return {
      meta,
      openGraph: {
        title: meta["og:title"] || "",
        siteName: meta["og:site_name"] || "",
        description: meta["og:description"] || "",
      },
      jsonLd,
    };
  }

  function localCollectShadowText(root) {
    const pieces = [];
    const visit = (node) => {
      if (!node) {
        return;
      }

      if (node.nodeType === Node.ELEMENT_NODE && node.shadowRoot) {
        pieces.push(node.shadowRoot.textContent || "");
        for (const child of node.shadowRoot.querySelectorAll("*")) {
          visit(child);
        }
      }

      if (node.children) {
        for (const child of node.children) {
          visit(child);
        }
      }
    };

    visit(root);
    return pieces.join("\n");
  }

  function localCollectVisibleText() {
    return localJoinUnique([
      document.body?.innerText || "",
      document.documentElement?.innerText || "",
      document.body?.textContent || "",
      document.documentElement?.textContent || "",
      localCollectShadowText(document.documentElement),
    ]);
  }

  function localCollectSemanticHtml() {
    const roots = Array.from(document.querySelectorAll([
      "main",
      "article",
      "[role='main']",
      ".job-description",
      ".description",
      "[data-testid*='job']",
      "[class*='job']",
      "[id*='job']",
    ].join(", ")));
    const semanticRoot = roots.find((node) => (node.innerText || node.textContent || "").trim().length > 80)
      || document.body
      || document.documentElement;

    if (!semanticRoot) {
      return "";
    }

    const semanticClone = semanticRoot.cloneNode(true);
    for (const node of semanticClone.querySelectorAll("script, style, svg, canvas, nav, header, footer, form, button, iframe")) {
      node.remove();
    }

    return semanticClone.innerHTML.slice(0, 200000);
  }

  const selectedText = window.getSelection ? String(window.getSelection()) : "";
  const metadata = localCollectMetadata();
  const semanticHtml = localCollectSemanticHtml();
  const visibleText = localCollectVisibleText();

  const evidence = {
    url: window.location.href,
    pageUrl: document.location.href,
    pageTitle: document.title,
    selectedText,
    visibleText,
    semanticHtml,
    metadata,
  };

  console.log("[Merida Job Capture] frame evidence", {
    url: evidence.url,
    pageTitle: evidence.pageTitle,
    selectedTextLength: evidence.selectedText.length,
    visibleTextLength: evidence.visibleText.length,
    semanticHtmlLength: evidence.semanticHtml.length,
    jsonLdCount: evidence.metadata.jsonLd.length,
    visibleSample: evidence.visibleText.replace(/\s+/g, " ").trim().slice(0, 240),
  });

  return evidence;
}

function summarizeInjections(injections) {
  return (injections || []).map((injection, index) => ({
    index,
    frameId: injection.frameId,
    documentId: injection.documentId,
    url: injection.result?.url || "",
    pageTitle: injection.result?.pageTitle || "",
    selectedTextLength: String(injection.result?.selectedText || "").length,
    visibleTextLength: String(injection.result?.visibleText || "").length,
    semanticHtmlLength: String(injection.result?.semanticHtml || "").length,
    jsonLdCount: Array.isArray(injection.result?.metadata?.jsonLd) ? injection.result.metadata.jsonLd.length : 0,
    visibleSample: sampleText(injection.result?.visibleText),
  }));
}

function summarizeEvidencePayload(evidence) {
  return {
    tabUrl: evidence.tabUrl,
    frameCount: evidence.frames.length,
    frames: evidence.frames.map((frame, index) => ({
      index,
      frameId: frame.frameId,
      documentId: frame.documentId,
      url: frame.url || "",
      pageTitle: frame.pageTitle || "",
      selectedTextLength: String(frame.selectedText || "").length,
      visibleTextLength: String(frame.visibleText || "").length,
      semanticHtmlLength: String(frame.semanticHtml || "").length,
      jsonLdCount: Array.isArray(frame.metadata?.jsonLd) ? frame.metadata.jsonLd.length : 0,
      visibleSample: sampleText(frame.visibleText),
    })),
  };
}

function sampleText(value) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 240);
}
