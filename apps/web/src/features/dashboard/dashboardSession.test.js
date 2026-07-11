import assert from 'node:assert/strict'
import test from 'node:test'

import { createDashboardSession } from './dashboardSession.js'

test('analysis completion resets both queue cursors and keeps a safe final result', async () => {
  const calls = []
  const client = {
    loadDashboard: async ({ analysisCursor, resumeCursor }) => {
      calls.push(['load', analysisCursor, resumeCursor])
      return {
        health: { checks: { analysis: 'ready', resumes: 'ready' } },
        settings: { models: { analysis: 'demo', resumes: 'demo' } },
        analysisQueue: { queueCount: 1, items: [], pagination: { nextCursor: null } },
        resumeQueue: { queueCount: 0, items: [], pagination: { nextCursor: null } },
      }
    },
    runAnalysis: async (limit) => {
      calls.push(['run', limit])
      return { ok: true, result: 'completed', processed: 1, succeeded: 1, failed: 0, repaired: 0, items: [] }
    },
  }
  const session = createDashboardSession(client)
  session.setCursors('opaque-analysis', 'opaque-resume')

  await session.runAnalysis(99)

  assert.deepEqual(calls[0], ['run', 10])
  assert.deepEqual(calls[1], ['load', null, null])
  assert.equal(session.getState().analysisResult.result, 'completed')
  assert.equal(session.getState().analysisCursor, null)
  assert.equal(session.getState().resumeCursor, null)
})

test('resume completion keeps output links after the queue refresh', async () => {
  const client = {
    loadDashboard: async () => ({
      health: { checks: { analysis: 'ready', resumes: 'ready' } },
      settings: { models: { analysis: 'demo', resumes: 'demo' } },
      analysisQueue: { queueCount: 0, items: [], pagination: { nextCursor: null } },
      resumeQueue: { queueCount: 0, items: [], pagination: { nextCursor: null } },
    }),
    createResume: async () => ({
      ok: true,
      result: 'created',
      resume: { url: 'https://example.test/resume' },
      note: { url: 'https://example.test/note' },
      pdf: { downloadUrl: '/api/v1/resumes/resume-1/pdf' },
    }),
  }
  const session = createDashboardSession(client)

  await session.createResume('app-1')

  assert.equal(session.getState().activeResumeId, null)
  assert.equal(session.getState().resumeResults['app-1'].pdf.downloadUrl, '/api/v1/resumes/resume-1/pdf')
})
