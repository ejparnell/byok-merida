import assert from 'node:assert/strict'
import test from 'node:test'

import { createDashboardClient } from './dashboardClient.js'

const payloads = {
  '/api/v1/health': { ok: true, checks: { analysis: 'ready', resumes: 'ready' } },
  '/api/v1/operator/settings': { ok: true, mode: 'demo' },
  '/api/v1/applications/analysis/queue': { ok: true, queueCount: 0, items: [], pagination: { limit: 5, nextCursor: null, hasMore: false } },
  '/api/v1/resumes/queue': { ok: true, queueCount: 0, items: [], pagination: { limit: 5, nextCursor: null, hasMore: false } },
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
  const client = createDashboardClient({ baseUrl: 'http://merida.test', fetch })

  const result = await client.loadDashboard({ analysisCursor: null, resumeCursor: null })

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
    return new Response(JSON.stringify({
      ok: false,
      error: { code: 'internal_error', message: 'Analysis failed.', requestId: 'request-1' },
      validationFailures: [],
      errors: ['Analysis failed.'],
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const client = createDashboardClient({ baseUrl: 'http://merida.test', fetch })

  await assert.rejects(
    () => client.runAnalysis(5),
    (error) => error.message === 'Analysis failed.' && error.code === 'internal_error',
  )
  assert.equal(calls, 1)
})
