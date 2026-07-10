const SIDE_PANEL_PATH = "popup.html";

configureSidePanel().catch(reportSidePanelError);

chrome.action.onClicked.addListener((tab) => {
  openCapturePanel(tab).catch(reportSidePanelError);
});

chrome.runtime.onInstalled.addListener(() => {
  configureSidePanel().catch(reportSidePanelError);
});

chrome.runtime.onStartup.addListener(() => {
  configureSidePanel().catch(reportSidePanelError);
});

async function configureSidePanel() {
  if (!chrome.sidePanel) {
    return;
  }

  await chrome.sidePanel.setOptions({
    path: SIDE_PANEL_PATH,
    enabled: true,
  });
}

function openCapturePanel(tab) {
  if (!chrome.sidePanel || !tab?.id) {
    return Promise.resolve();
  }

  return chrome.sidePanel.open({
    tabId: tab.id,
  });
}

function reportSidePanelError(error) {
  console.error("[Merida Job Capture] could not open or configure side panel", error);
}
