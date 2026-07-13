import type {
  ConfirmApplicationResponse,
  ConfirmedApplicationDraft,
  PrepareApplicationRequest,
  PrepareApplicationResponse,
  PreparedApplicationDraft,
} from '@merida/api-client'
import type { CaptureClient } from '../shared/captureClient.ts'
import type { ObservedSource, SourceReference } from '../shared/sourceAccess.ts'

export type CaptureSource = SourceReference
export type CapturePhase =
  'idle' | 'reading' | 'parsing' | 'reviewing' | 'confirming' | 'complete'

export type ReviewDraft = Omit<
  PreparedApplicationDraft,
  'jobContentPreview'
> & {
  jobContent: string
}

export type CaptureState = {
  phase: CapturePhase
  evidence: PrepareApplicationRequest['evidence'] | null
  source: CaptureSource | null
  review: ReviewDraft | null
  dirty: boolean
  result: ConfirmApplicationResponse | null
  errors: string[]
  reviewReasons: string[]
  missingFields: string[]
  sourceChanged: boolean
}

const EMPTY_STATE = {
  phase: 'idle',
  evidence: null,
  source: null,
  review: null,
  dirty: false,
  result: null,
  errors: [],
  reviewReasons: [],
  missingFields: [],
  sourceChanged: false,
} satisfies CaptureState

const operatorError = (error: unknown) => error as Error

const readableJobContent = (
  evidence: PrepareApplicationRequest['evidence'],
) => {
  const semanticText = String(evidence.semanticHtml || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return (
    evidence.selectedText?.trim() ||
    evidence.visibleText?.trim() ||
    semanticText
  )
}

const createReviewDraft = (
  draft: PreparedApplicationDraft,
  evidence: PrepareApplicationRequest['evidence'],
): ReviewDraft => ({
  jobUrl: draft.jobUrl,
  companyName: draft.companyName,
  role: draft.role,
  location: draft.location,
  jobContent: readableJobContent(evidence),
})

export function createCaptureSession(
  client: CaptureClient,
  onChange: (state: CaptureState) => void = () => {},
): CaptureSession {
  let state: CaptureState = { ...EMPTY_STATE }
  let activeClient = client

  const publish = (patch: Partial<CaptureState>) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const performPrepare = async (
    evidence: PrepareApplicationRequest['evidence'],
    source: CaptureSource,
  ) => {
    publish({ phase: 'parsing', errors: [], result: null })
    try {
      const response = await activeClient.prepare(evidence)
      const validationErrors = (response.validationFailures || []).map(
        (failure) => failure.message,
      )
      publish({
        phase: 'reviewing',
        evidence,
        source,
        review: createReviewDraft(response.draft, evidence),
        dirty: false,
        reviewReasons: response.reviewReasons || [],
        missingFields: response.missingFields || [],
        errors: [
          ...(response.reviewReasons || []),
          ...validationErrors,
          ...(response.errors || []),
        ],
      })
      return response.result
    } catch (error) {
      publish({
        phase: state.review ? 'reviewing' : 'idle',
        errors: [
          operatorError(error).message || 'Application could not be prepared.',
        ],
        reviewReasons: [],
        missingFields: [],
      })
      return 'failed'
    }
  }

  return {
    getState: () => state,
    setClient(nextClient: CaptureClient) {
      activeClient = nextClient
    },
    beginReading() {
      if (state.phase === 'reviewing' && state.dirty) return
      publish({ phase: 'reading', errors: [], result: null })
    },
    cancelReading() {
      if (state.phase !== 'reading') return
      publish({ phase: state.review ? 'reviewing' : 'idle' })
    },
    async prepare(
      evidence: PrepareApplicationRequest['evidence'],
      source: CaptureSource,
      { discard = false }: { discard?: boolean } = {},
    ) {
      if (state.phase === 'reviewing' && state.dirty && !discard) {
        return 'discard_confirmation_required'
      }
      return performPrepare(evidence, source)
    },
    updateReview(field: keyof ReviewDraft, value: string) {
      if (!state.review) return
      publish({
        review: { ...state.review, [field]: value },
        dirty: true,
        errors: [],
        reviewReasons: [],
        missingFields: [],
      })
    },
    sourceChanged(source: ObservedSource) {
      if (!state.source) return
      const changed =
        state.source.tabId !== source.tabId || state.source.url !== source.url
      if (changed !== state.sourceChanged) publish({ sourceChanged: changed })
    },
    async confirm() {
      if (!state.review || !state.evidence || state.phase === 'confirming')
        return null
      const review = state.review
      const required = ['companyName', 'role', 'jobUrl'] as const
      const missing: string[] = required.filter(
        (field) => !String(review[field] || '').trim(),
      )
      const jobContent = review.jobContent.trim()
      if (jobContent.length < 20) missing.push('jobContent')
      if (missing.length) {
        publish({
          errors: [`Required fields are missing: ${missing.join(', ')}.`],
          missingFields: missing,
        })
        return { ok: false, result: 'needs_review', missing }
      }
      publish({ phase: 'confirming', errors: [] })
      try {
        const draft: ConfirmedApplicationDraft = {
          companyName: review.companyName!.trim(),
          role: review.role!.trim(),
          location: review.location,
          jobUrl: review.jobUrl.trim(),
          jobContent,
        }
        const result = await activeClient.confirm(draft)
        if (result.ok) {
          publish({
            ...EMPTY_STATE,
            phase: 'complete',
            result,
          })
        } else {
          const validationErrors = (result.validationFailures || []).map(
            (failure) => failure.message,
          )
          publish({
            phase: 'reviewing',
            result,
            errors: [
              ...validationErrors,
              ...(result.errors || ['Application could not be created.']),
            ],
            missingFields: (result.validationFailures || [])
              .filter((failure) => failure.kind === 'request')
              .map((failure) => failure.field),
          })
        }
        return result
      } catch (error) {
        publish({
          phase: 'reviewing',
          errors: [
            operatorError(error).message || 'Application could not be created.',
          ],
        })
        return null
      }
    },
    clear() {
      publish({ ...EMPTY_STATE })
    },
  }
}

export interface CaptureSession {
  getState(): CaptureState
  setClient(client: CaptureClient): void
  beginReading(): void
  cancelReading(): void
  prepare(
    evidence: PrepareApplicationRequest['evidence'],
    source: CaptureSource,
    options?: { discard?: boolean },
  ): Promise<
    | PrepareApplicationResponse['result']
    | 'failed'
    | 'discard_confirmation_required'
  >
  updateReview(field: keyof ReviewDraft, value: string): void
  sourceChanged(source: ObservedSource): void
  confirm(): Promise<
    | ConfirmApplicationResponse
    | { ok: false; result: 'needs_review'; missing: string[] }
    | null
  >
  clear(): void
}
