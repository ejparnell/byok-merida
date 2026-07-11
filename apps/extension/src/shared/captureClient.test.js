import assert from 'node:assert/strict'
import test from 'node:test'

import { createCaptureClient } from './captureClient.js'

test('extension adapter sends the capture token only to protected operations', async () => {
  const requests = []
  const fetch = async (request) => {
    requests.push(request)
    const path = new URL(request.url).pathname
    const body = path.endsWith('/prepare')
      ? { ok: true, result: 'prepared', draft: {} }
      : path.endsWith('/confirm')
        ? { ok: true, result: 'created', application: {} }
        : { ok: true, status: 'ready', checks: { notion: 'ready' } }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const client = createCaptureClient(
    { backendUrl: 'http://merida.test', captureToken: 'secret-token' },
    { fetch },
  )

  await client.health()
  await client.prepare({ url: 'https://example.test/job', visibleText: 'Readable job content for testing.' })
  await client.confirm({ jobUrl: 'https://example.test/job', companyName: 'Example', role: 'Engineer', location: null, jobContent: 'Readable job content for testing.' })

  assert.equal(requests.length, 3)
  assert.equal(requests[0].headers.has('X-Capture-Token'), false)
  assert.equal(requests[1].headers.get('X-Capture-Token'), 'secret-token')
  assert.equal(requests[2].headers.get('X-Capture-Token'), 'secret-token')
})
