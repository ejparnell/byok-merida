import { loadConfig } from "./config.js";
import { createJobPostingsAdapter } from "../features/jobPostings/backend/routes.js";
import { createResumesAdapter } from "../features/resumes/backend/routes.js";

export function createRouteAdapters({
  config = loadConfig(),
  jobPostings = {},
  resumes = {},
} = {}) {
  const {
    adapter: jobPostingsAdapter,
    ...jobPostingsOptions
  } = jobPostings;
  const {
    adapter: resumesAdapter,
    ...resumesOptions
  } = resumes;

  return {
    jobPostings: jobPostingsAdapter || createJobPostingsAdapter({
      config,
      ...jobPostingsOptions,
    }),
    resumes: resumesAdapter || createResumesAdapter({
      config,
      ...resumesOptions,
    }),
  };
}
