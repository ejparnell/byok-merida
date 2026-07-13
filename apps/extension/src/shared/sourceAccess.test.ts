import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { getSourceAccess, waitForSourceReady } from './sourceAccess.ts'

const manifest = JSON.parse(
  readFileSync(new URL('../../public/manifest.json', import.meta.url), 'utf8'),
)

test('manifest grants persistent HTTP(S) Source Page access', () => {
  assert.ok(manifest.host_permissions.includes('http://*/*'))
  assert.ok(manifest.host_permissions.includes('https://*/*'))
})

test('Source Access exposes a ready HTTP Source Page', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = {
    tabs: {
      query: async () => [
        {
          id: 7,
          url: 'https://jobs.example.test/roles/123',
          status: 'complete',
        },
      ],
    },
  }

  try {
    assert.deepEqual(await getSourceAccess(), {
      status: 'ready',
      source: { tabId: 7, url: 'https://jobs.example.test/roles/123' },
    })
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('Source Access reports a navigating Source Page as waiting', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = {
    tabs: {
      query: async () => [
        {
          id: 7,
          url: 'https://jobs.example.test/roles/123',
          status: 'loading',
        },
      ],
    },
  }

  try {
    assert.deepEqual(await getSourceAccess(), {
      status: 'waiting',
      source: { tabId: 7, url: 'https://jobs.example.test/roles/123' },
    })
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('Source Access rejects Chrome-internal pages without changing backend state', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = {
    tabs: {
      query: async () => [
        { id: 7, url: 'chrome://extensions/', status: 'complete' },
      ],
    },
  }

  try {
    const access = await getSourceAccess()
    assert.equal(access.status, 'restricted')
    assert.match(access.error, /Chrome does not allow this page to be read/)
  } finally {
    globalThis.chrome = previousChrome
  }
})

function chromeEvent() {
  const listeners = new Set<(...args: never[]) => void>()
  return {
    addListener(listener: (...args: never[]) => void) {
      listeners.add(listener)
    },
    removeListener(listener: (...args: never[]) => void) {
      listeners.delete(listener)
    },
    dispatch(...args: never[]) {
      listeners.forEach((listener) => listener(...args))
    },
  }
}

test('pending capture becomes ready when its Source Page finishes loading', async () => {
  const previousChrome = globalThis.chrome
  let tab = {
    id: 7,
    url: 'https://jobs.example.test/roles/123',
    status: 'loading',
  }
  const activated = chromeEvent()
  const updated = chromeEvent()
  globalThis.chrome = {
    tabs: {
      query: async () => [tab],
      onActivated: activated,
      onUpdated: updated,
    },
  }

  try {
    const pending = waitForSourceReady(
      { tabId: 7, url: 'https://jobs.example.test/roles/123' },
      100,
    )
    tab = { ...tab, status: 'complete' }
    updated.dispatch()
    assert.deepEqual(await pending, {
      status: 'ready',
      source: { tabId: 7, url: 'https://jobs.example.test/roles/123' },
    })
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('pending capture cancels when navigation changes its Source Page', async () => {
  const previousChrome = globalThis.chrome
  let tab = {
    id: 7,
    url: 'https://jobs.example.test/roles/123',
    status: 'loading',
  }
  const activated = chromeEvent()
  const updated = chromeEvent()
  globalThis.chrome = {
    tabs: {
      query: async () => [tab],
      onActivated: activated,
      onUpdated: updated,
    },
  }

  try {
    const pending = waitForSourceReady(
      { tabId: 7, url: 'https://jobs.example.test/roles/123' },
      100,
    )
    tab = { ...tab, url: 'https://other.example.test/roles/456' }
    updated.dispatch()
    assert.deepEqual(await pending, { status: 'cancelled' })
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('pending capture times out after the documented readiness window', async () => {
  const previousChrome = globalThis.chrome
  const tab = {
    id: 7,
    url: 'https://jobs.example.test/roles/123',
    status: 'loading',
  }
  const activated = chromeEvent()
  const updated = chromeEvent()
  globalThis.chrome = {
    tabs: {
      query: async () => [tab],
      onActivated: activated,
      onUpdated: updated,
    },
  }

  try {
    assert.deepEqual(
      await waitForSourceReady(
        { tabId: 7, url: 'https://jobs.example.test/roles/123' },
        1,
      ),
      { status: 'timeout' },
    )
  } finally {
    globalThis.chrome = previousChrome
  }
})
