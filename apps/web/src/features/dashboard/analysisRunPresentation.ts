import type { AnalysisRunSnapshot } from '@merida/api-client'

export const DEFAULT_ANALYSIS_TARGET = 5

type PresentationRow = {
  label: string
  value: string
}

const lifecycleLabels: Record<AnalysisRunSnapshot['lifecycle'], string> = {
  queued: 'Queued',
  running: 'Running',
  cancelling: 'Cancelling',
  finished: 'Finished',
}

const outcomeLabels: Record<
  NonNullable<AnalysisRunSnapshot['outcome']>,
  string
> = {
  target_met: 'Target met',
  spend_limited: 'Spend limited',
  attempt_budget_exhausted: 'Attempt Budget exhausted',
  queue_exhausted: 'Queue exhausted',
  cancelled: 'Cancelled',
  authorization_blocked: 'Authorization blocked',
  failed: 'Run failed',
}

const candidateLabels: Record<
  AnalysisRunSnapshot['candidates'][number]['state'],
  string
> = {
  pending: 'Pending',
  evaluating: 'Evaluating',
  analyzed: 'Analyzed',
  repaired: 'Repaired',
  skipped: 'Skipped',
  failed: 'Failed',
  indeterminate: 'Indeterminate',
}

export const formatUsdMicros = (micros: number): string =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(micros / 1_000_000)

const displayReason = (reasonCode: string | null): string | null =>
  reasonCode ? reasonCode.replaceAll('_', ' ') : null

export type AnalysisRunPresentation = {
  title: string
  lifecycleLabel: string
  reason: string | null
  tone: 'active' | 'success' | 'failure'
  isActive: boolean
  showCancel: boolean
  cancelLabel: string
  progressRows: PresentationRow[]
  countsSummary: string
  spendRows: PresentationRow[]
  candidates: Array<{
    applicationId: string
    ordinalLabel: string
    stateLabel: string
    reason: string | null
  }>
}

export function presentAnalysisRun(
  run: AnalysisRunSnapshot | null,
  { cancelPending = false }: { cancelPending?: boolean } = {},
): AnalysisRunPresentation | null {
  if (!run) return null

  const isActive = run.lifecycle !== 'finished'
  const lifecycleLabel = lifecycleLabels[run.lifecycle]
  const title = run.outcome ? outcomeLabels[run.outcome] : lifecycleLabel
  const tone =
    run.outcome === 'failed' || run.outcome === 'authorization_blocked'
      ? 'failure'
      : isActive
        ? 'active'
        : 'success'

  return {
    title,
    lifecycleLabel,
    reason: displayReason(run.reasonCode),
    tone,
    isActive,
    showCancel: isActive,
    cancelLabel: cancelPending
      ? 'Requesting cancellation'
      : run.lifecycle === 'cancelling'
        ? 'Cancellation requested'
        : 'Cancel run',
    progressRows: [
      {
        label: 'Completions',
        value: `${run.progress.completions} / ${run.target}`,
      },
      {
        label: 'Evaluated candidates',
        value: `${run.progress.evaluated} / ${run.attemptBudget}`,
      },
      {
        label: 'Committed Spend',
        value: `${formatUsdMicros(run.spend.committedMicros)} / ${formatUsdMicros(run.spend.ceilingMicros)}`,
      },
    ],
    countsSummary: `${run.progress.repaired} repaired · ${run.progress.skipped} skipped · ${run.progress.failed} failed · ${run.progress.indeterminate} indeterminate`,
    spendRows: [
      {
        label: 'Verified cost',
        value: formatUsdMicros(run.spend.verifiedCostMicros),
      },
      {
        label: 'Active reservations',
        value: formatUsdMicros(run.spend.activeReservationMicros),
      },
      {
        label: 'Indeterminate reservations',
        value: formatUsdMicros(run.spend.indeterminateReservationMicros),
      },
      {
        label: 'Remaining authorized budget',
        value: formatUsdMicros(run.spend.remainingAuthorizedMicros),
      },
    ],
    candidates: run.candidates.map((candidate) => ({
      applicationId: candidate.applicationId,
      ordinalLabel: `Candidate ${candidate.ordinal + 1}`,
      stateLabel: candidateLabels[candidate.state],
      reason: displayReason(candidate.reasonCode),
    })),
  }
}
