import {
  createResumeForJobPosting,
  getResumeStatus,
} from "./resumeService.js";
import { renderResumesPage } from "./resumesPage.js";
import { ResumeNotionClient } from "../lib/notion.js";
import { createResumePdfExporter } from "../lib/pdfExport.js";
import { NotesNotionClient } from "../../notes/lib/notion.js";

export function createResumesAdapter({
  config,
  resumeClient = new ResumeNotionClient({
    token: config.notionToken,
    jobPostingDatabaseId: config.notionDatabaseId,
    resumeDatabaseId: config.notionResumeDatabaseId,
  }),
  notesClient = new NotesNotionClient({
    token: config.notionToken,
    jobPostingDatabaseId: config.notionDatabaseId,
    resumeDatabaseId: config.notionResumeDatabaseId,
    notesDatabaseId: config.notionNotesDatabaseId,
  }),
  resumeFitAnalysis,
  fitRuntimeClient,
  resumeLlm,
  resumePdfExporter = createResumePdfExporter(),
} = {}) {
  return {
    routes: [
      {
        method: "GET",
        path: "/resumes",
        token: "none",
        async handle({ sendHtml }) {
          sendHtml(renderResumesPage());
        },
      },
      {
        method: "GET",
        path: "/resumes/status",
        token: "none",
        async handle({ sendJson }) {
          const result = await getResumeStatus({
            config,
            resumeClient,
            notesClient,
            ...(resumeFitAnalysis ? { resumeFitAnalysis } : {}),
            ...(fitRuntimeClient ? { fitRuntimeClient } : {}),
          });
          sendJson(200, result);
        },
      },
      {
        method: "POST",
        path: "/resumes/create",
        token: "same-origin",
        async handle({ readJson, sendJson }) {
          const body = await readJson();
          const result = await createResumeForJobPosting({
            jobPostingPageId: body.jobPostingPageId,
            config,
            resumeClient,
            notesClient,
            ...(resumeFitAnalysis ? { resumeFitAnalysis } : {}),
            ...(fitRuntimeClient ? { fitRuntimeClient } : {}),
            ...(resumeLlm ? { resumeLlm } : {}),
            resumePdfExporter,
          });
          sendJson(200, result);
        },
      },
    ],
  };
}
