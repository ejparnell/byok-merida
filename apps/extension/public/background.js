const SIDE_PANEL_PATH = 'index.html'

configureSidePanel().catch(reportSidePanelError)

chrome.action.onClicked.addListener((tab) => {
  if (tab.id != null) chrome.sidePanel.open({ tabId: tab.id }).catch(() => {})
})

chrome.runtime.onInstalled.addListener(() => {
  configureSidePanel().catch(reportSidePanelError)
})

chrome.runtime.onStartup.addListener(() => {
  configureSidePanel().catch(reportSidePanelError)
})

function configureSidePanel() {
  return Promise.all([
    chrome.sidePanel.setOptions({ path: SIDE_PANEL_PATH, enabled: true }),
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }),
  ])
}

function reportSidePanelError(error) {
  console.error('[Merida Application Capture] could not configure side panel', error)
}
