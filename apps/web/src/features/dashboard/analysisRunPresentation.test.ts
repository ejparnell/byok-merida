import assert from 'node:assert/strict'
import test from 'node:test'

import type { AnalysisRunSnapshot } from '@merida/api-client'

import {
  DEFAULT_ANALYSIS_TARGET,
  formatUsdMicros,
  presentAnalysisRun,
} from './analysisRunPresentation.ts'

const runSnapshot = (
  overrides: Partial<AnalysisRunSnapshot> = {},
): AnalysisRunSnapshot => ({
  runId: 'run-1',
  lifecycle: 'running',
  outcome: null,
  reasonCode: null,
  target: 5,
  attemptBudget: 10,
  progress: {
    completions: 2,
    repaired: 1,
    evaluated: 4,
    skipped: 1,
    failed: 0,
    indeterminate: 0,
  },
  spend: {
    ceilingMicros: 500_000,
    committedMicros: 145_000,
    verifiedCostMicros: 120_000,
    activeReservationMicros: 5_000,
    indeterminateReservationMicros: 20_000,
    remainingAuthorizedMicros: 355_000,
  },
  candidates: [],
  createdAt: '2026-08-12T12:00:00Z',
  updatedAt: '2026-08-12T12:00:01Z',
  startedAt: '2026-08-12T12:00:01Z',
  finishedAt: null,
  ...overrides,
})

test('presents every Analysis Run lifecycle label', () => {
  const cases: Array<[AnalysisRunSnapshot['lifecycle'], string]> = [
    ['queued', 'Queued'],
    ['running', 'Running'],
    ['cancelling', 'Cancelling'],
    ['finished', 'Finished'],
  ]

  for (const [lifecycle, expected] of cases) {
    const presentation = presentAnalysisRun(runSnapshot({ lifecycle }))
    assert.equal(presentation?.lifecycleLabel, expected)
    assert.equal(presentation?.title, expected)
  }
})

test('presents every terminal outcome and keeps it visible', () => {
  const cases: Array<[NonNullable<AnalysisRunSnapshot['outcome']>, string]> = [
    ['target_met', 'Target met'],
    ['spend_limited', 'Spend limited'],
    ['attempt_budget_exhausted', 'Attempt Budget exhausted'],
    ['queue_exhausted', 'Queue exhausted'],
    ['cancelled', 'Cancelled'],
    ['authorization_blocked', 'Authorization blocked'],
    ['failed', 'Run failed'],
  ]

  for (const [outcome, expected] of cases) {
    const presentation = presentAnalysisRun(
      runSnapshot({
        lifecycle: 'finished',
        outcome,
        finishedAt: '2026-08-12T12:01:00Z',
      }),
    )
    assert.equal(presentation?.title, expected)
    assert.equal(presentation?.isActive, false)
    assert.equal(presentation?.showCancel, false)
  }
})

test('presents every safe candidate state and reason', () => {
  const candidates: AnalysisRunSnapshot['candidates'] = [
    'pending',
    'evaluating',
    'analyzed',
    'repaired',
    'skipped',
    'failed',
    'indeterminate',
  ].map((state, ordinal) => ({
    applicationId: `application-${ordinal + 1}`,
    ordinal,
    state: state as AnalysisRunSnapshot['candidates'][number]['state'],
    reasonCode: ordinal === 6 ? 'provider_outcome_indeterminate' : null,
    startedAt: null,
    completedAt: null,
  }))

  const presentation = presentAnalysisRun(runSnapshot({ candidates }))

  assert.deepEqual(
    presentation?.candidates.map((candidate) => candidate.stateLabel),
    [
      'Pending',
      'Evaluating',
      'Analyzed',
      'Repaired',
      'Skipped',
      'Failed',
      'Indeterminate',
    ],
  )
  assert.equal(
    presentation?.candidates[6]?.reason,
    'provider outcome indeterminate',
  )
})

test('presents primary progress and committed spend against the $0.50 ceiling', () => {
  const presentation = presentAnalysisRun(
    runSnapshot({
      spend: {
        ceilingMicros: 500_000,
        committedMicros: 480_000,
        verifiedCostMicros: 300_000,
        activeReservationMicros: 0,
        indeterminateReservationMicros: 180_000,
        remainingAuthorizedMicros: 20_000,
      },
    }),
  )

  assert.deepEqual(presentation?.progressRows, [
    { label: 'Completions', value: '2 / 5' },
    { label: 'Evaluated candidates', value: '4 / 10' },
    { label: 'Committed Spend', value: '$0.48 / $0.50' },
  ])
  assert.deepEqual(presentation?.spendRows, [
    { label: 'Verified cost', value: '$0.30' },
    { label: 'Active reservations', value: '$0.00' },
    { label: 'Indeterminate reservations', value: '$0.18' },
    { label: 'Remaining authorized budget', value: '$0.02' },
  ])
})

test('presents active and cancellation button states without hiding the run', () => {
  assert.deepEqual(
    {
      active: presentAnalysisRun(runSnapshot({ lifecycle: 'queued' }))
        ?.isActive,
      showCancel: presentAnalysisRun(runSnapshot({ lifecycle: 'queued' }))
        ?.showCancel,
      label: presentAnalysisRun(runSnapshot({ lifecycle: 'queued' }))
        ?.cancelLabel,
    },
    { active: true, showCancel: true, label: 'Cancel run' },
  )
  assert.equal(
    presentAnalysisRun(runSnapshot({ lifecycle: 'cancelling' }))?.cancelLabel,
    'Cancellation requested',
  )
  assert.equal(
    presentAnalysisRun(runSnapshot(), { cancelPending: true })?.cancelLabel,
    'Requesting cancellation',
  )
})

test('uses a five-application default target and hides only an absent run', () => {
  assert.equal(DEFAULT_ANALYSIS_TARGET, 5)
  assert.equal(presentAnalysisRun(null), null)
})

test('formats USD micros without hiding sub-cent reservations', () => {
  assert.equal(formatUsdMicros(500_000), '$0.50')
  assert.equal(formatUsdMicros(5_000), '$0.005')
})
