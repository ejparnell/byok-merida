import assert from 'node:assert/strict'
import test from 'node:test'

import { createCaptureSession } from './captureSession.ts'

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))
const wait = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

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

  assert.deepEqual(phases.slice(0, 3), ['reading', 'parsing', 'reviewing'])
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

test('prepared Reviews check Notion matches without blocking confirmation', async () => {
  const requests = []
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Acme',
        role: 'Senior Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
    matches: async (companyName, role) => {
      requests.push({ companyName, role })
      return {
        ok: true,
        result: 'matched',
        matches: [
          {
            id: 'app-acme',
            title: 'Senior Engineer at Acme',
            companyName: 'Acme',
            role: 'Senior Engineer',
            applicationStatus: 'Applied',
            url: 'https://www.notion.so/app-acme',
          },
        ],
        validationFailures: [],
        errors: [],
      }
    },
  })

  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems.' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  await flush()

  assert.deepEqual(requests, [{ companyName: 'Acme', role: 'Senior Engineer' }])
  assert.deepEqual(session.getState().captureMatch, {
    status: 'matched',
    matches: [
      {
        id: 'app-acme',
        title: 'Senior Engineer at Acme',
        companyName: 'Acme',
        role: 'Senior Engineer',
        applicationStatus: 'Applied',
        url: 'https://www.notion.so/app-acme',
      },
    ],
  })
})

test('edited match fields debounce the check and ignore stale results', async () => {
  let resolveInitial
  const requests = []
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Acme',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
    matches: (companyName, role) => {
      requests.push({ companyName, role })
      if (requests.length === 1)
        return new Promise((resolve) => {
          resolveInitial = resolve
        })
      return Promise.resolve({
        ok: true,
        result: 'unmatched',
        matches: [],
        validationFailures: [],
        errors: [],
      })
    },
  })

  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems.' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  session.updateReview('role', 'Staff Engineer')
  resolveInitial({
    ok: true,
    result: 'matched',
    matches: [
      {
        id: 'stale',
        title: 'Engineer at Acme',
        companyName: 'Acme',
        role: 'Engineer',
        applicationStatus: 'Applied',
        url: 'https://www.notion.so/stale',
      },
    ],
    validationFailures: [],
    errors: [],
  })
  await flush()

  assert.deepEqual(session.getState().captureMatch, { status: 'checking' })
  assert.equal(requests.length, 1)

  await wait(320)

  assert.deepEqual(requests, [
    { companyName: 'Acme', role: 'Engineer' },
    { companyName: 'Acme', role: 'Staff Engineer' },
  ])
  assert.deepEqual(session.getState().captureMatch, { status: 'unmatched' })
})

test('a stale failed lookup cannot replace an incomplete match state', async () => {
  let rejectInitial
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Acme',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
    matches: () =>
      new Promise((_, reject) => {
        rejectInitial = reject
      }),
  })

  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems.' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  session.updateReview('companyName', '')
  rejectInitial(new Error('Notion is unavailable.'))
  await flush()

  assert.deepEqual(session.getState().captureMatch, { status: 'incomplete' })
})

test('an unavailable Notion match can be retried without changing the Review', async () => {
  let attempts = 0
  const session = createCaptureSession({
    prepare: async () => ({
      ok: true,
      result: 'prepared',
      draft: {
        jobUrl: 'https://example.test/job',
        companyName: 'Acme',
        role: 'Engineer',
        location: null,
        jobContentPreview: 'Build reliable systems.',
      },
    }),
    matches: async () => {
      attempts += 1
      if (attempts === 1) throw new Error('Notion is unavailable.')
      return {
        ok: true,
        result: 'unmatched',
        matches: [],
        validationFailures: [],
        errors: [],
      }
    },
  })

  await session.prepare(
    { url: 'https://example.test/job', visibleText: 'Build reliable systems.' },
    { tabId: 1, url: 'https://example.test/job' },
  )
  await flush()
  assert.deepEqual(session.getState().captureMatch, {
    status: 'unavailable',
    error: 'Notion is unavailable.',
  })

  session.retryCaptureMatch()
  await flush()

  assert.equal(session.getState().review?.companyName, 'Acme')
  assert.deepEqual(session.getState().captureMatch, { status: 'unmatched' })
})
