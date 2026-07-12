import assert from 'node:assert/strict'
import test from 'node:test'

import { readCaptureHealth } from './captureHealth.ts'

test('capture health remains blocked when backend Capture settings are blocked', async () => {
  const health = await readCaptureHealth(
    {
      health: async () => ({
        ok: false,
        status: 'blocked',
        service: 'merida-api',
        checks: {
          settings: 'blocked',
          notion: 'ready',
          analysis: 'ready',
          resumes: 'ready',
        },
        validationFailures: [],
        errors: ['CAPTURE_TOKEN is not configured.'],
      }),
      prepare: async () => {
        throw new Error('not used')
      },
      confirm: async () => {
        throw new Error('not used')
      },
    },
    'extension-token',
  )

  assert.equal(health.phase, 'blocked')
  assert.deepEqual(health.errors, ['CAPTURE_TOKEN is not configured.'])
})
