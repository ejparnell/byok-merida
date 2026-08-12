import assert from 'node:assert/strict'
import test from 'node:test'

import { createDashboardSession } from './dashboardSession.ts'

const dashboardSnapshot = () => ({
  health: { checks: { analysis: 'ready', resumes: 'ready' } },
  settings: {
    models: { analysis: 'analysis-test', resumes: 'resume-test' },
  },
  analysisQueue: {
    queueCount: 3,
    items: [],
    pagination: { nextCursor: null },
  },
  resumeQueue: {
    queueCount: 0,
    items: [],
    pagination: { nextCursor: null },
  },
  errors: [],
})

const analysisRun = (overrides = {}) => ({
  runId: 'run-1',
  lifecycle: 'queued',
  outcome: null,
  reasonCode: null,
  target: 5,
  attemptBudget: 10,
  progress: {
    completions: 0,
    repaired: 0,
    evaluated: 0,
    skipped: 0,
    failed: 0,
    indeterminate: 0,
  },
  spend: {
    ceilingMicros: 500000,
    committedMicros: 0,
    verifiedCostMicros: 0,
    activeReservationMicros: 0,
    indeterminateReservationMicros: 0,
    remainingAuthorizedMicros: 500000,
  },
  candidates: [],
  createdAt: '2026-08-12T12:00:00Z',
  updatedAt: '2026-08-12T12:00:00Z',
  startedAt: null,
  finishedAt: null,
  ...overrides,
})

const response = (run) => ({
  ok: true,
  run,
  validationFailures: [],
  errors: [],
})

class ManualPollScheduler {
  tasks = []

  delays = []

  schedule(task, delayMs) {
    this.tasks.push(task)
    this.delays.push(delayMs)
    return task
  }

  cancel(task) {
    this.tasks = this.tasks.filter((candidate) => candidate !== task)
  }

  async runNext() {
    const task = this.tasks.shift()
    assert.ok(task, 'expected a scheduled poll')
    await task()
  }
}

const dashboardClient = (overrides = {}) => ({
  loadDashboard: async () => dashboardSnapshot(),
  getActiveAnalysisRun: async () => ({
    ok: true,
    run: null,
    validationFailures: [],
    errors: [],
  }),
  getAnalysisRun: async () => response(analysisRun()),
  runAnalysis: async () => response(analysisRun()),
  cancelAnalysisRun: async () =>
    response(analysisRun({ lifecycle: 'cancelling' })),
  createResume: async () => ({
    ok: true,
    result: 'already_created',
    resume: { url: 'https://example.test/resume' },
    note: null,
    pdf: null,
  }),
  ...overrides,
})

test('intentional start creates one key, clamps the target, and begins polling', async () => {
  const calls = []
  let keyCalls = 0
  const scheduler = new ManualPollScheduler()
  const client = dashboardClient({
    runAnalysis: async (target, idempotencyKey) => {
      calls.push([target, idempotencyKey])
      return response(analysisRun({ target }))
    },
  })
  const session = createDashboardSession(client, undefined, {
    scheduler,
    createIdempotencyKey: () => {
      keyCalls += 1
      return 'analysis-start-1'
    },
    pollIntervalMs: 750,
  })

  await session.runAnalysis(99)

  assert.deepEqual(calls, [[10, 'analysis-start-1']])
  assert.equal(keyCalls, 1)
  assert.equal(session.getState().analysisRun.runId, 'run-1')
  assert.equal(session.getState().analysisStarting, false)
  assert.equal(scheduler.tasks.length, 1)
  assert.deepEqual(scheduler.delays, [750])
})

test('fractional targets are normalized to an integer before start', async () => {
  const calls = []
  const client = dashboardClient({
    runAnalysis: async (target, idempotencyKey) => {
      calls.push([target, idempotencyKey])
      return response(analysisRun({ target }))
    },
  })
  const session = createDashboardSession(client, undefined, {
    scheduler: new ManualPollScheduler(),
    createIdempotencyKey: () => 'fractional-start',
  })

  await session.runAnalysis(1.9)

  assert.deepEqual(calls, [[1, 'fractional-start']])
})

test('a numeric target below the range clamps to one', async () => {
  const calls = []
  const client = dashboardClient({
    runAnalysis: async (target, idempotencyKey) => {
      calls.push([target, idempotencyKey])
      return response(analysisRun({ target }))
    },
  })
  const session = createDashboardSession(client, undefined, {
    scheduler: new ManualPollScheduler(),
    createIdempotencyKey: () => 'low-target-start',
  })

  await session.runAnalysis(0)

  assert.deepEqual(calls, [[1, 'low-target-start']])
})

test('load reconnects to an active run and polls the durable identity', async () => {
  const polled = []
  const scheduler = new ManualPollScheduler()
  const active = analysisRun({ runId: 'run-active', lifecycle: 'running' })
  const client = dashboardClient({
    getActiveAnalysisRun: async () => ({
      ok: true,
      run: active,
      validationFailures: [],
      errors: [],
    }),
    getAnalysisRun: async (runId) => {
      polled.push(runId)
      return response(
        analysisRun({
          runId,
          lifecycle: 'running',
          progress: {
            completions: 2,
            repaired: 1,
            evaluated: 4,
            skipped: 1,
            failed: 0,
            indeterminate: 0,
          },
        }),
      )
    },
  })
  const session = createDashboardSession(client, undefined, { scheduler })

  await session.load()
  await scheduler.runNext()

  assert.deepEqual(polled, ['run-active'])
  assert.equal(session.getState().analysisRun.progress.completions, 2)
  assert.equal(scheduler.tasks.length, 1)
})

test('typed active-run conflict follows that run without replaying start', async () => {
  let startCalls = 0
  const scheduler = new ManualPollScheduler()
  const client = dashboardClient({
    runAnalysis: async () => {
      startCalls += 1
      const error = new Error('Another run is active.')
      error.code = 'analysis_run_active'
      error.activeRunId = 'run-existing'
      throw error
    },
    getAnalysisRun: async (runId) =>
      response(analysisRun({ runId, lifecycle: 'running' })),
  })
  const session = createDashboardSession(client, undefined, { scheduler })

  await session.runAnalysis(5)

  assert.equal(startCalls, 1)
  assert.equal(session.getState().analysisRun.runId, 'run-existing')
  assert.deepEqual(session.getState().errors, [])
  assert.equal(scheduler.tasks.length, 1)
})

test('terminal poll persists the result and refreshes both queues at page one', async () => {
  const loads = []
  const scheduler = new ManualPollScheduler()
  const terminal = analysisRun({
    lifecycle: 'finished',
    outcome: 'spend_limited',
    reasonCode: 'reservation_would_exceed_ceiling',
    finishedAt: '2026-08-12T12:01:00Z',
    progress: {
      completions: 2,
      repaired: 1,
      evaluated: 4,
      skipped: 1,
      failed: 1,
      indeterminate: 0,
    },
    spend: {
      ceilingMicros: 500000,
      committedMicros: 480000,
      verifiedCostMicros: 300000,
      activeReservationMicros: 0,
      indeterminateReservationMicros: 180000,
      remainingAuthorizedMicros: 20000,
    },
    candidates: [
      {
        applicationId: 'application-1',
        ordinal: 0,
        state: 'analyzed',
        reasonCode: null,
        startedAt: '2026-08-12T12:00:01Z',
        completedAt: '2026-08-12T12:00:20Z',
      },
      {
        applicationId: 'application-2',
        ordinal: 1,
        state: 'repaired',
        reasonCode: null,
        startedAt: '2026-08-12T12:00:21Z',
        completedAt: '2026-08-12T12:00:30Z',
      },
      {
        applicationId: 'application-3',
        ordinal: 2,
        state: 'skipped',
        reasonCode: 'candidate_no_longer_eligible',
        startedAt: '2026-08-12T12:00:31Z',
        completedAt: '2026-08-12T12:00:35Z',
      },
      {
        applicationId: 'application-4',
        ordinal: 3,
        state: 'failed',
        reasonCode: 'invalid_analysis_output',
        startedAt: '2026-08-12T12:00:36Z',
        completedAt: '2026-08-12T12:00:50Z',
      },
      {
        applicationId: 'application-5',
        ordinal: 4,
        state: 'indeterminate',
        reasonCode: 'provider_outcome_indeterminate',
        startedAt: '2026-08-12T12:00:51Z',
        completedAt: '2026-08-12T12:01:00Z',
      },
    ],
  })
  const client = dashboardClient({
    loadDashboard: async ({ analysisCursor, resumeCursor }) => {
      loads.push([analysisCursor, resumeCursor])
      return dashboardSnapshot()
    },
    getAnalysisRun: async () => response(terminal),
  })
  const session = createDashboardSession(client, undefined, { scheduler })
  session.setCursors('analysis-page', 'resume-page')
  await session.runAnalysis(5)

  await scheduler.runNext()

  await session.load()

  assert.deepEqual(loads, [
    [null, null],
    [null, null],
  ])
  assert.equal(session.getState().analysisRun.outcome, 'spend_limited')
  assert.equal(session.getState().analysisRun.spend.committedMicros, 480000)
  assert.deepEqual(
    session
      .getState()
      .analysisRun.candidates.map((candidate) => candidate.state),
    ['analyzed', 'repaired', 'skipped', 'failed', 'indeterminate'],
  )
  assert.equal(session.getState().analysisCursor, null)
  assert.equal(session.getState().resumeCursor, null)
  assert.equal(scheduler.tasks.length, 0)
})

test('cancel updates the active durable run and continues polling', async () => {
  const calls = []
  const scheduler = new ManualPollScheduler()
  const client = dashboardClient({
    cancelAnalysisRun: async (runId) => {
      calls.push(runId)
      return response(
        analysisRun({ runId, lifecycle: 'cancelling', target: 3 }),
      )
    },
  })
  const session = createDashboardSession(client, undefined, { scheduler })
  await session.runAnalysis(3)

  await session.cancelAnalysisRun()

  assert.deepEqual(calls, ['run-1'])
  assert.equal(session.getState().analysisRun.lifecycle, 'cancelling')
  assert.equal(session.getState().analysisCancelPending, false)
  assert.equal(scheduler.tasks.length, 1)
})

test('transport failure is not retried and leaves a future intentional start possible', async () => {
  let calls = 0
  let keys = 0
  const client = dashboardClient({
    runAnalysis: async () => {
      calls += 1
      throw new Error('Backend unavailable.')
    },
  })
  const session = createDashboardSession(client, undefined, {
    createIdempotencyKey: () => `key-${++keys}`,
  })

  await session.runAnalysis(5)

  assert.equal(calls, 1)
  assert.equal(keys, 1)
  assert.equal(session.getState().analysisStarting, false)
  assert.deepEqual(session.getState().errors, ['Backend unavailable.'])
})

test('invalid queue cursors recover once by loading both first pages', async () => {
  const calls = []
  const client = dashboardClient({
    loadDashboard: async ({ analysisCursor, resumeCursor }) => {
      calls.push([analysisCursor, resumeCursor])
      if (analysisCursor || resumeCursor) {
        const error = new Error('Cursor is invalid or expired.')
        error.code = 'invalid_cursor'
        throw error
      }
      return dashboardSnapshot()
    },
  })
  const session = createDashboardSession(client)
  session.setCursors('stale-analysis', 'stale-resume')

  await session.load()

  assert.deepEqual(calls, [
    ['stale-analysis', 'stale-resume'],
    [null, null],
  ])
  assert.equal(session.getState().analysisCursor, null)
  assert.equal(session.getState().resumeCursor, null)
})

test('created resume resets only the Resume Creation queue and keeps links', async () => {
  const loads = []
  const client = dashboardClient({
    loadDashboard: async ({ analysisCursor, resumeCursor }) => {
      loads.push([analysisCursor, resumeCursor])
      return dashboardSnapshot()
    },
    createResume: async () => ({
      ok: true,
      result: 'created',
      resume: { url: 'https://example.test/resume' },
      note: { url: 'https://example.test/note' },
      pdf: { downloadUrl: '/api/v1/resumes/resume-1/pdf' },
    }),
  })
  const session = createDashboardSession(client)
  session.setCursors('analysis-page', 'resume-page')

  await session.createResume('app-1')

  assert.deepEqual(loads, [['analysis-page', null]])
  assert.equal(
    session.getState().resumeResults['app-1'].pdf.downloadUrl,
    '/api/v1/resumes/resume-1/pdf',
  )
})
