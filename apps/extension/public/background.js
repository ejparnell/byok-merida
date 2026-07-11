chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {})
})

chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId != null) chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {})
})
