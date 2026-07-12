import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { collectCaptureEvidence } from './activeTabEvidence.ts'

const finalCaptureFixture = JSON.parse(
  readFileSync(
    new URL(
      '../../../api/tests/fixtures/final-parity.v1.json',
      import.meta.url,
    ),
    'utf8',
  ),
).fixtures.find(({ id }) => id === 'CAPTURE-EVIDENCE-001')

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

test('final capture fixture is enforced through the extension collector', async () => {
  const previousChrome = globalThis.chrome
  const observation = finalCaptureFixture.observation
  const [main, selected] = observation.initialState.frames
  globalThis.chrome = {
    tabs: {
      query: async () => [
        { id: 7, url: observation.expectedOutcome.capturedUrl },
      ],
    },
    scripting: {
      executeScript: async () => [
        {
          frameId: main.frameId,
          result: {
            url: main.url,
            title: main.pageTitle,
            selectedText: '',
            visibleText: 'v'.repeat(
              observation.dependencyOutputs.oversizedVisibleTextLength,
            ),
            semanticHtml: '',
            metadataText: '',
            structuredJobTitle: main.metadata.jsonLd[0].title,
            structuredCompanyName:
              main.metadata.jsonLd[0].hiringOrganization.name,
            structuredLocation: 'Remote - United States',
          },
        },
        {
          frameId: selected.frameId,
          result: {
            url: selected.url,
            title: '',
            selectedText: selected.selectedText,
            visibleText: selected.visibleText,
            semanticHtml: selected.semanticHtml,
            metadataText: '',
            structuredJobTitle: '',
            structuredCompanyName: '',
            structuredLocation: '',
          },
        },
      ],
    },
  }

  try {
    const collected = await collectCaptureEvidence()
    assert.equal(collected.source.url, observation.expectedOutcome.capturedUrl)
    assert.equal(
      collected.evidence.structuredCompanyName,
      observation.expectedOutcome.companyName,
    )
    assert.equal(collected.evidence.selectedText, selected.selectedText)
    assert.equal(
      collected.evidence.visibleText.length,
      observation.expectedOutcome.oversizedVisibleTextLength,
    )
  } finally {
    globalThis.chrome = previousChrome
  }
})
