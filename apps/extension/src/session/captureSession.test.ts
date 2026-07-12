import assert from 'node:assert/strict'
import test from 'node:test'

import { createCaptureSession } from './captureSession.ts'

test('reviewed fields survive a failed confirmation and are sent with in-memory job content', async () => {
  const client = {
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Example',
        role: 'Engineer',
        location: 'Remote',
        jobContentPreview: 'Build reliable systems',
      },
    }),
    confirm: async (draft) => {
      assert.equal(draft.jobContent, 'Build reliable systems with Python')
      return {
        ok: false,
        status: 'blocked',
        errors: ['Workspace unavailable'],
      }
    },
  }
  const evidence = {
    url: 'https://example.test/job',
    title: 'Engineer at Example',
    visibleText: 'Build reliable systems with Python',
  }
  const session = createCaptureSession(client)
  await session.prepare(evidence, { tabId: 7, url: evidence.url })
  session.updateReview('role', 'Senior Engineer')

  await session.confirm()

  const state = session.getState()
  assert.equal(state.phase, 'reviewing')
  assert.equal(state.review.role, 'Senior Engineer')
  assert.deepEqual(state.errors, ['Workspace unavailable'])
})

test('starting a new capture requires discard confirmation when review is dirty', async () => {
  const client = {
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Example',
        role: 'Engineer',
        location: '',
        jobContentPreview: 'Content',
      },
    }),
  }
  const session = createCaptureSession(client)
  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Content' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  session.updateReview('companyName', 'Edited Example')

  const outcome = await session.prepare(
    { url: 'https://other.test/job', visibleText: 'Other' },
    { tabId: 2, url: 'https://other.test/job' },
  )

  assert.equal(outcome, 'discard_confirmation_required')
  assert.equal(session.getState().review.companyName, 'Edited Example')
})

test('semantic-only evidence is converted to readable in-memory Job Content on confirm', async () => {
  let confirmed = null
  const client = {
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Example',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
    confirm: async (draft) => {
      confirmed = draft
      return { ok: true, result: 'created', application: { id: 'app-1' } }
    },
  }
  const session = createCaptureSession(client)
  const evidence = {
    url: 'https://example.test/job',
    semanticHtml:
      '<article><h1>Engineer</h1><p>Build reliable systems.</p></article>',
  }

  await session.prepare(evidence, { tabId: 1, url: evidence.url })
  await session.confirm()

  assert.equal(confirmed.jobContent, 'Engineer Build reliable systems.')
})
