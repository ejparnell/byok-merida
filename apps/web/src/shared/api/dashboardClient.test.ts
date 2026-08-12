import assert from 'node:assert/strict'
import test from 'node:test'

import { createDashboardClient } from './dashboardClient.ts'

const payloads = {
  '/api/v1/health': {
    ok: true,
    checks: { analysis: 'ready', resumes: 'ready' },
  },
  '/api/v1/operator/settings': {
    ok: true,
    models: { analysis: 'deepseek-v4-flash', resumes: 'deepseek-v4-pro' },
    configured: { notion: true, deepseek: true },
  },
  '/api/v1/applications/analysis/queue': {
    ok: true,
    queueCount: 0,
    items: [],
    pagination: { limit: 5, nextCursor: null, hasMore: false },
  },
  '/api/v1/resumes/queue': {
    ok: true,
    queueCount: 0,
    items: [],
    pagination: { limit: 5, nextCursor: null, hasMore: false },
  },
}

test('dashboard adapter uses the shared client without sending capture credentials', async () => {
  const requests = []
  const fetch = async (request) => {
    requests.push(request)
    const url = new URL(request.url)
    return new Response(JSON.stringify(payloads[url.pathname]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  const result = await client.loadDashboard({
    analysisCursor: null,
    resumeCursor: null,
  })

  assert.equal(result.health.ok, true)
  assert.equal(requests.length, 4)
  for (const request of requests) {
    assert.equal(request.headers.has('X-Capture-Token'), false)
  }
})

test('dashboard adapter never retries a failed analysis POST automatically', async () => {
  let calls = 0
  const fetch = async () => {
    calls += 1
    return new Response(
      JSON.stringify({
        ok: false,
        error: {
          code: 'internal_error',
          message: 'Analysis failed.',
          requestId: 'request-1',
        },
        validationFailures: [],
        errors: ['Analysis failed.'],
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      },
    )
  }
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  await assert.rejects(
    () => client.runAnalysis(5, 'analysis-start-1'),
    (error) =>
      error.message === 'Analysis failed.' && error.code === 'internal_error',
  )
  assert.equal(calls, 1)
})

test('dashboard adapter sends target and one caller-owned idempotency key', async () => {
  const requests = []
  const fetch = async (request) => {
    requests.push(request)
    return new Response(
      JSON.stringify({
        ok: true,
        run: {
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
        },
        validationFailures: [],
        errors: [],
      }),
      { status: 202, headers: { 'Content-Type': 'application/json' } },
    )
  }
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  await client.runAnalysis(5, 'analysis-start-1')

  assert.equal(requests.length, 1)
  assert.equal(requests[0].headers.get('Idempotency-Key'), 'analysis-start-1')
  assert.deepEqual(await requests[0].json(), { target: 5 })
})

test('dashboard adapter exposes typed active-run conflicts without parsing messages', async () => {
  const fetch = async () =>
    new Response(
      JSON.stringify({
        ok: false,
        error: {
          code: 'analysis_run_active',
          message: 'Another Analysis Run is active.',
          requestId: 'request-1',
          activeRunId: 'run-active',
        },
        validationFailures: [],
        errors: ['Another Analysis Run is active.'],
      }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  await assert.rejects(
    () => client.runAnalysis(5, 'analysis-start-1'),
    (error) =>
      error.code === 'analysis_run_active' &&
      error.activeRunId === 'run-active',
  )
})

test('dashboard adapter supports active lookup, run polling, and cancellation', async () => {
  const requests = []
  const activeResponse = {
    ok: true,
    run: null,
    validationFailures: [],
    errors: [],
  }
  const runResponse = {
    ok: true,
    run: {
      runId: 'run-1',
      lifecycle: 'cancelling',
      outcome: null,
      reasonCode: null,
      target: 1,
      attemptBudget: 2,
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
      updatedAt: '2026-08-12T12:00:01Z',
      startedAt: null,
      finishedAt: null,
    },
    validationFailures: [],
    errors: [],
  }
  const fetch = async (request) => {
    requests.push([request.method, new URL(request.url).pathname])
    const path = new URL(request.url).pathname
    return new Response(
      JSON.stringify(
        path.endsWith('/runs/active') ? activeResponse : runResponse,
      ),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )
  }
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  await client.getActiveAnalysisRun()
  await client.getAnalysisRun('run-1')
  await client.cancelAnalysisRun('run-1')

  assert.deepEqual(requests, [
    ['GET', '/api/v1/applications/analysis/runs/active'],
    ['GET', '/api/v1/applications/analysis/runs/run-1'],
    ['POST', '/api/v1/applications/analysis/runs/run-1/cancel'],
  ])
})

test('dashboard load keeps healthy sections when one queue request fails', async () => {
  const fetch = async (request) => {
    const url = new URL(request.url)
    if (url.pathname === '/api/v1/resumes/queue') {
      return new Response(
        JSON.stringify({
          ok: false,
          error: {
            code: 'internal_error',
            message: 'Resume Queue is unavailable.',
            requestId: 'request-1',
          },
          validationFailures: [],
          errors: ['Resume Queue is unavailable.'],
        }),
        { status: 500, headers: { 'Content-Type': 'application/json' } },
      )
    }
    return new Response(JSON.stringify(payloads[url.pathname]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const client = createDashboardClient({
    baseUrl: 'http://merida.test',
    fetch,
  })

  const result = await client.loadDashboard({})

  assert.equal(result.health.ok, true)
  assert.equal(result.analysisQueue.ok, true)
  assert.equal(result.resumeQueue, null)
  assert.deepEqual(result.errors, ['Resume Queue is unavailable.'])
})
