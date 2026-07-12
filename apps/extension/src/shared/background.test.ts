import assert from 'node:assert/strict'
import test from 'node:test'

test('extension action restores the tab-scoped panel configuration from the legacy capture extension', async () => {
  const previousChrome = globalThis.chrome
  let onInstalled: (() => void) | undefined
  let onStartup: (() => void) | undefined
  let onClicked: ((tab: chrome.tabs.Tab) => void) | undefined
  const panelBehaviorConfigurations: unknown[] = []
  const panelOptionConfigurations: unknown[] = []
  const panelOpens: unknown[] = []

  globalThis.chrome = {
    runtime: {
      onInstalled: {
        addListener: (listener) => {
          onInstalled = listener
        },
      },
      onStartup: {
        addListener: (listener) => {
          onStartup = listener
        },
      },
    },
    action: {
      onClicked: {
        addListener: (listener) => {
          onClicked = listener
        },
      },
    },
    sidePanel: {
      setPanelBehavior: async (configuration) => {
        panelBehaviorConfigurations.push(configuration)
      },
      setOptions: async (configuration) => {
        panelOptionConfigurations.push(configuration)
      },
      open: async (configuration) => {
        panelOpens.push(configuration)
      },
    },
  } as typeof chrome

  try {
    await import(
      new URL('../../public/background.js?test', import.meta.url).href
    )
    onInstalled?.()
    onStartup?.()
    assert.deepEqual(panelBehaviorConfigurations, [
      { openPanelOnActionClick: false },
      { openPanelOnActionClick: false },
      { openPanelOnActionClick: false },
    ])
    assert.deepEqual(panelOptionConfigurations, [
      { path: 'index.html', enabled: true },
      { path: 'index.html', enabled: true },
      { path: 'index.html', enabled: true },
    ])

    onClicked?.({ id: 7, windowId: 3 } as chrome.tabs.Tab)
    assert.deepEqual(panelOpens, [{ tabId: 7 }])
  } finally {
    globalThis.chrome = previousChrome
  }
})
