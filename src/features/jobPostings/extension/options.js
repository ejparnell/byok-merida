const LOCAL_CONFIG = globalThis.MERIDA_JOB_CAPTURE_CONFIG || {};
const DEFAULT_BACKEND_URL = LOCAL_CONFIG.backendUrl || "http://127.0.0.1:3217";

const form = document.querySelector("#optionsForm");
const backendUrl = document.querySelector("#backendUrl");
const captureToken = document.querySelector("#captureToken");
const saveStatus = document.querySelector("#saveStatus");

void loadOptions();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await chrome.storage.local.set({
    backendUrl: backendUrl.value.trim() || DEFAULT_BACKEND_URL,
    captureToken: captureToken.value,
  });
  saveStatus.textContent = "Saved.";
});

async function loadOptions() {
  const values = await chrome.storage.local.get(["backendUrl", "captureToken"]);
  backendUrl.value = values.backendUrl || LOCAL_CONFIG.backendUrl || DEFAULT_BACKEND_URL;
  captureToken.value = values.captureToken || LOCAL_CONFIG.captureToken || "";
}
