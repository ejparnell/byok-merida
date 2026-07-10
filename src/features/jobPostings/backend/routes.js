import {
  getAnalysisStatus,
  runAnalysisBatch,
} from "./analysisService.js";
import {
  captureJobPosting,
  confirmJobPosting,
  prepareJobPostingReview,
} from "./captureService.js";
import { renderAnalysisPage } from "./analysisPage.js";
import { createCaptureEvidence } from "../lib/captureEvidence.js";
import { NotionClient } from "../lib/notion.js";

export function createJobPostingsAdapter({
  config,
  notionClient = new NotionClient({
    token: config.notionToken,
    databaseId: config.notionDatabaseId,
  }),
  analysisAnalyzer,
} = {}) {
  return {
    async validateNotionSchema() {
      return notionClient.validateDatabaseSchema();
    },
    routes: [
      {
        method: "GET",
        path: "/analysis",
        token: "none",
        async handle({ sendHtml }) {
          sendHtml(renderAnalysisPage());
        },
      },
      {
        method: "GET",
        path: "/analysis/status",
        token: "none",
        async handle({ sendJson }) {
          const result = await getAnalysisStatus({ config, notionClient });
          sendJson(200, result);
        },
      },
      {
        method: "POST",
        path: "/analysis/run",
        token: "same-origin",
        async handle(context) {
          const body = await context.readJson();
          await handleAnalysisRun(context, {
            config,
            notionClient,
            analysisAnalyzer,
            limit: body.limit,
          });
        },
      },
      {
        method: "POST",
        path: "/capture",
        token: "required",
        async handle({ readJson, sendJson }) {
          const evidence = await readJson();
          if (config.debugCapture) {
            console.log("[job-capture] /capture evidence", createCaptureEvidence(evidence).summary);
          }
          const result = await captureJobPosting(evidence, { notionClient, debug: config.debugCapture });
          if (config.debugCapture) {
            console.log("[job-capture] /capture result", summarizeResultForLog(result));
          }
          sendJson(200, result);
        },
      },
      {
        method: "POST",
        path: "/parse",
        token: "required",
        async handle({ readJson, sendJson }) {
          const evidence = await readJson();
          if (config.debugCapture) {
            console.log("[job-capture] /parse evidence", createCaptureEvidence(evidence).summary);
          }
          const result = prepareJobPostingReview(evidence, { debug: config.debugCapture });
          if (config.debugCapture) {
            console.log("[job-capture] /parse result", summarizeResultForLog(result));
          }
          sendJson(200, result);
        },
      },
      {
        method: "POST",
        path: "/confirm",
        token: "required",
        async handle({ readJson, sendJson }) {
          const body = await readJson();
          if (config.debugCapture) {
            console.log("[job-capture] /confirm request", summarizeConfirmedForLog(body?.parsed || body));
          }
          const result = await confirmJobPosting(body?.parsed || body, { notionClient, debug: config.debugCapture });
          if (config.debugCapture) {
            console.log("[job-capture] /confirm result", summarizeResultForLog(result));
          }
          sendJson(200, result);
        },
      },
    ],
  };
}

async function handleAnalysisRun({ streamNdjson }, {
  config,
  notionClient,
  analysisAnalyzer,
  limit,
}) {
  await streamNdjson(async (emit) => {
    try {
      await runAnalysisBatch({
        limit,
        config,
        notionClient,
        ...(analysisAnalyzer ? { analyzer: analysisAnalyzer } : {}),
        emit,
      });
    } catch (error) {
      console.error("[job-analysis] run failed", { message: error.message });
      await emit({
        type: "run_finished",
        requested: limit,
        total: 0,
        totals: { analyzed: 0, skipped: 0, failed: 0, repaired: 0 },
        message: error.message || "Analysis run failed.",
      });
    }
  });
}

function summarizeConfirmedForLog(parsed) {
  return {
    jobPostingTitle: parsed?.jobPostingTitle || "",
    jobUrl: parsed?.jobUrl || "",
    companyName: parsed?.companyName || "",
    jobTitle: parsed?.jobTitle || "",
    location: parsed?.location || "",
    jobContentLength: String(parsed?.jobContent || "").length,
  };
}

function summarizeResultForLog(result) {
  return {
    type: result?.type || "",
    reason: result?.reason || "",
    message: result?.message || "",
    errors: result?.errors || undefined,
    warnings: result?.warnings || undefined,
    summary: result?.summary || {},
    debug: result?.debug || undefined,
  };
}
