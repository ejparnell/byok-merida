import assert from 'node:assert/strict'
import test from 'node:test'

import { collectCaptureEvidence } from './activeTabEvidence.ts'

test('active-tab evidence fails truthfully when Chrome page APIs are unavailable', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = undefined

  try {
    await assert.rejects(
      collectCaptureEvidence(),
      /Chrome page access is unavailable/,
    )
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('active-tab evidence carries structured job metadata into the API request', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = {
    tabs: { query: async () => [{ id: 7, url: 'https://example.test/job' }] },
    scripting: {
      executeScript: async () => [
        {
          frameId: 0,
          result: {
            url: 'https://example.test/job',
            title: 'Jobs at Example',
            selectedText: '',
            visibleText: 'Build reliable systems.',
            semanticHtml: '',
            metadataText: 'Platform Engineer Example Remote',
            structuredJobTitle: 'Platform Engineer',
            structuredCompanyName: 'Example',
            structuredLocation: 'Remote',
          },
        },
      ],
    },
  }

  try {
    const { evidence } = await collectCaptureEvidence()
    assert.equal(evidence.structuredJobTitle, 'Platform Engineer')
    assert.equal(evidence.structuredCompanyName, 'Example')
    assert.equal(evidence.structuredLocation, 'Remote')
    assert.equal(evidence.metadataText, 'Platform Engineer Example Remote')
  } finally {
    globalThis.chrome = previousChrome
  }
})

test('active-tab evidence respects per-field and combined API limits', async () => {
  const previousChrome = globalThis.chrome
  globalThis.chrome = {
    tabs: { query: async () => [{ id: 7, url: 'https://example.test/job' }] },
    scripting: {
      executeScript: async () => [
        {
          frameId: 0,
          result: {
            url: 'https://example.test/job',
            title: 'Engineer at Example',
            selectedText: 's'.repeat(130_000),
            visibleText: 'v'.repeat(130_000),
            semanticHtml: 'h'.repeat(130_000),
          },
        },
      ],
    },
  }

  try {
    const { evidence } = await collectCaptureEvidence()
    assert.equal(evidence.selectedText.length, 120_000)
    assert.ok(evidence.visibleText.length <= 120_000)
    assert.ok(evidence.semanticHtml.length <= 120_000)
    assert.ok(
      evidence.selectedText.length +
        evidence.visibleText.length +
        evidence.semanticHtml.length <=
        240_000,
    )
  } finally {
    globalThis.chrome = previousChrome
  }
})
