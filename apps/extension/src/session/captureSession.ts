import type {
  ConfirmApplicationResponse,
  ConfirmedApplicationDraft,
  PrepareApplicationRequest,
  PrepareApplicationResponse,
  PreparedApplicationDraft,
} from '@merida/api-client'
import type { CaptureClient } from '../shared/captureClient.ts'

export type CaptureSource = { tabId: number; url: string }
export type CapturePhase =
  'idle' | 'reading' | 'parsing' | 'reviewing' | 'confirming' | 'complete'

export type CaptureState = {
  phase: CapturePhase
  evidence: PrepareApplicationRequest['evidence'] | null
  source: CaptureSource | null
  review: PreparedApplicationDraft | null
  dirty: boolean
  result: ConfirmApplicationResponse | null
  errors: string[]
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

export function createCaptureSession(
  client: CaptureClient,
  onChange: (state: CaptureState) => void = () => {},
): CaptureSession {
  let state: CaptureState = { ...EMPTY_STATE }

  const publish = (patch: Partial<CaptureState>) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const performPrepare = async (
    evidence: PrepareApplicationRequest['evidence'],
    source: CaptureSource,
  ) => {
    publish({ phase: 'reading', errors: [], result: null })
    try {
      publish({ phase: 'parsing' })
      const response = await client.prepare(evidence)
      publish({
        phase: 'reviewing',
        evidence,
        source,
        review: { ...response.draft },
        dirty: false,
        errors: response.errors || [],
      })
      return response.result
    } catch (error) {
      publish({
        phase: state.review ? 'reviewing' : 'idle',
        errors: [
          operatorError(error).message || 'Application could not be prepared.',
        ],
      })
      return 'failed'
    }
  }

  return {
    getState: () => state,
    subscribe(next: (state: CaptureState) => void) {
      onChange = next
      next(state)
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
    updateReview(field: keyof PreparedApplicationDraft, value: string) {
      if (!state.review) return
      publish({
        review: { ...state.review, [field]: value },
        dirty: true,
        errors: [],
      })
    },
    sourceChanged(source: CaptureSource) {
      if (!state.source) return false
      const changed =
        state.source.tabId !== source.tabId || state.source.url !== source.url
      if (changed) publish({ sourceChanged: true })
      return changed
    },
    async confirm() {
      if (!state.review || !state.evidence || state.phase === 'confirming')
        return null
      const review = state.review
      const required: Array<keyof PreparedApplicationDraft> = [
        'companyName',
        'role',
        'jobUrl',
      ]
      const missing: string[] = required.filter(
        (field) => !String(review[field] || '').trim(),
      )
      const jobContent = readableJobContent(state.evidence)
      if (jobContent.length < 20) missing.push('jobContent')
      if (missing.length) {
        publish({
          errors: [`Required fields are missing: ${missing.join(', ')}.`],
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
        const result = await client.confirm(draft)
        if (result.ok) {
          publish({ phase: 'complete', result, evidence: null, dirty: false })
        } else {
          publish({
            phase: 'reviewing',
            result,
            errors: result.errors || ['Application could not be created.'],
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
  subscribe(next: (state: CaptureState) => void): void
  prepare(
    evidence: PrepareApplicationRequest['evidence'],
    source: CaptureSource,
    options?: { discard?: boolean },
  ): Promise<
    | PrepareApplicationResponse['result']
    | 'failed'
    | 'discard_confirmation_required'
  >
  updateReview(field: keyof PreparedApplicationDraft, value: string): void
  sourceChanged(source: CaptureSource): boolean
  confirm(): Promise<
    | ConfirmApplicationResponse
    | { ok: false; result: 'needs_review'; missing: string[] }
    | null
  >
  clear(): void
}
