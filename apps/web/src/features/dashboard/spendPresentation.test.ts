import assert from 'node:assert/strict'
import test from 'node:test'

import { formatUsdMicros } from './spendPresentation.ts'

test('USD-micro formatting retains sub-cent authorization values', () => {
  assert.equal(formatUsdMicros(2_405), '$0.002405')
  assert.equal(formatUsdMicros(714_240), '$0.71424')
  assert.equal(formatUsdMicros(1_000_000), '$1.00')
  assert.equal(formatUsdMicros(1), '$0.000001')
})
