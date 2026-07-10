import { loadConfig } from "../../../src/backend/config.js";
import { createCallCounter } from "./observerSupport.js";

export function observePrivacyFixture(fixture) {
  if (fixture.observation.runner !== "backend_credential_ownership") {
    throw new Error(`Unsupported privacy runner: ${fixture.observation.runner}`);
  }

  const calls = createCallCounter();
  calls.increment("loadConfig");
  const config = loadConfig(fixture.observation.dependencyOutputs.environment);
  const loadedCredentialKeys = ["notionToken", "deepseekApiKey"]
    .filter((key) => Boolean(config[key]));

  return {
    outcome: {
      backendLoadedCredentialKeys: loadedCredentialKeys,
    },
    effects: ["load_backend_environment"],
    state: {
      credentialOwner: fixture.observation.initialState.credentialOwner,
      configuredModel: config.deepseekModel,
    },
    callCounts: calls.snapshot(["loadConfig"]),
    cleanupResidue: {},
  };
}
