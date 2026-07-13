import assert from 'node:assert/strict'
import test from 'node:test'

import { createCaptureSession } from './captureSession.ts'

test('reading is observable before Application parsing begins', async () => {
  const phases = []
  const session = createCaptureSession(
    {
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
    },
    (state) => phases.push(state.phase),
  )

  session.beginReading()
  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems' },
    { tabId: 7, url: 'https://example.test/job' },
  )

  assert.deepEqual(phases, ['reading', 'parsing', 'reviewing'])
})

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
      assert.equal(draft.jobContent, 'Edited job content with enough detail')
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
  session.updateReview('jobContent', 'Edited job content with enough detail')

  await session.confirm()

  const state = session.getState()
  assert.equal(state.phase, 'reviewing')
  assert.equal(state.review.role, 'Senior Engineer')
  assert.equal(state.review.jobContent, 'Edited job content with enough detail')
  assert.deepEqual(state.errors, ['Workspace unavailable'])
})

test('edited Job Content is sent in confirmation and cleared after success', async () => {
  let confirmed = null
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Example',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Original preview',
      },
    }),
    confirm: async (draft) => {
      confirmed = draft
      return { ok: true, result: 'created', application: { id: 'app-1' } }
    },
  })
  await session.prepare(
    {
      url: 'https://example.test/job',
      visibleText: 'Original readable Job Content with enough detail.',
    },
    { tabId: 1, url: 'https://example.test/job' },
  )
  assert.equal(
    session.getState().review.jobContent,
    'Original readable Job Content with enough detail.',
  )

  session.updateReview(
    'jobContent',
    'Edited readable Job Content that should be saved to Notion.',
  )
  await session.confirm()

  assert.equal(
    confirmed.jobContent,
    'Edited readable Job Content that should be saved to Notion.',
  )
  assert.equal(session.getState().review, null)
  assert.equal(session.getState().evidence, null)
})

test('edited Job Content must remain readable before confirmation', async () => {
  let confirmCalled = false
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Example',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Original preview',
      },
    }),
    confirm: async () => {
      confirmCalled = true
      return { ok: true, result: 'created', application: { id: 'app-1' } }
    },
  })
  await session.prepare(
    {
      url: 'https://example.test/job',
      visibleText: 'Original readable Job Content with enough detail.',
    },
    { tabId: 1, url: 'https://example.test/job' },
  )

  session.updateReview('jobContent', 'Too short')
  const result = await session.confirm()

  assert.equal(confirmCalled, false)
  assert.deepEqual(result, {
    ok: false,
    result: 'needs_review',
    missing: ['jobContent'],
  })
  assert.deepEqual(session.getState().missingFields, ['jobContent'])
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

test('reading cannot bypass discard confirmation for a dirty review', async () => {
  const session = createCaptureSession({
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
  })
  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Content' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  session.updateReview('companyName', 'Edited Example')

  session.beginReading()
  const outcome = await session.prepare(
    { url: 'https://other.test/job', visibleText: 'Other' },
    { tabId: 2, url: 'https://other.test/job' },
  )

  assert.equal(outcome, 'discard_confirmation_required')
  assert.equal(session.getState().phase, 'reviewing')
  assert.equal(session.getState().review.companyName, 'Edited Example')
})

test('source mismatch clears when the Review source becomes active again', async () => {
  const session = createCaptureSession({
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
  })
  const source = { tabId: 1, url: 'https://example.test/job' }
  await session.prepare({ url: source.url, visibleText: 'Content' }, source)

  session.sourceChanged({ tabId: 2, url: 'https://other.test/job' })
  assert.equal(session.getState().sourceChanged, true)

  session.sourceChanged(source)
  assert.equal(session.getState().sourceChanged, false)
})

test('cancelling a page read restores the preserved Review', async () => {
  const session = createCaptureSession({
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
  })
  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Content' },
    { tabId: 1, url: 'https://example.test/job' },
  )

  session.beginReading()
  session.cancelReading()

  const state = session.getState()
  assert.equal(state.phase, 'reviewing')
  assert.equal(state.review?.companyName, 'Example')
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

test('prepare review reasons and missing fields remain visible in session state', async () => {
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'needs_review',
      needsReview: true,
      reviewReasons: ['Company Name could not be parsed.'],
      missingFields: ['companyName'],
      validationFailures: [
        { kind: 'request', field: 'companyName', message: 'Review required.' },
      ],
      errors: [],
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: null,
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
  })

  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems.' },
    { tabId: 1, url: 'https://example.test/job' },
  )

  const state = session.getState()
  assert.deepEqual(state.reviewReasons, ['Company Name could not be parsed.'])
  assert.deepEqual(state.missingFields, ['companyName'])
  assert.deepEqual(state.errors, [
    'Company Name could not be parsed.',
    'Review required.',
  ])
})
