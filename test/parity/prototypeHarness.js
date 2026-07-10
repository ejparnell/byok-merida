import { observeCaptureFixture } from "./observers/captureObserver.js";
import { observeAnalysisFixture } from "./observers/analysisObserver.js";
import { observeResumeFixture } from "./observers/resumeObserver.js";
import { observeWorkspaceFixture } from "./observers/workspaceObserver.js";
import { observePrivacyFixture } from "./observers/privacyObserver.js";

const OBSERVERS = new Map([
  ["capture_evidence", observeCaptureFixture],
  ["capture_duplicate", observeCaptureFixture],
  ["capture_parse_only", observeCaptureFixture],
  ["capture_outcome_matrix", observeCaptureFixture],
  ["analysis_failure_isolation", observeAnalysisFixture],
  ["analysis_repair", observeAnalysisFixture],
  ["analysis_validation_persistence_matrix", observeAnalysisFixture],
  ["analysis_queue_contract", observeAnalysisFixture],
  ["resume_evidence_blocked", observeResumeFixture],
  ["resume_existing", observeResumeFixture],
  ["resume_success", observeResumeFixture],
  ["resume_final_attach_failure", observeResumeFixture],
  ["resume_cleanup_matrix", observeResumeFixture],
  ["resume_source_validation_matrix", observeResumeFixture],
  ["resume_claim_guardrails", observeResumeFixture],
  ["notion_compatibility", observeWorkspaceFixture],
  ["backend_credential_ownership", observePrivacyFixture],
]);

export async function runPrototypeObservation(fixture) {
  const observe = OBSERVERS.get(fixture.observation.runner);
  if (!observe) {
    throw new Error(`Unsupported prototype parity runner: ${fixture.observation.runner}`);
  }
  return observe(fixture);
}
