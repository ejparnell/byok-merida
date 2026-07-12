const EMPTY_STATE = {
  phase: 'idle',
  evidence: null,
  source: null,
  review: null,
  dirty: false,
  result: null,
  errors: [],
}

const operatorError = (error: unknown) => error as Error

const readableJobContent = (evidence: any) => {
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
  client: any,
  onChange: (state: any) => void = () => {},
) {
  let state: any = { ...EMPTY_STATE }

  const publish = (patch: any) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const performPrepare = async (evidence: any, source: any) => {
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
    subscribe(next: (state: any) => void) {
      onChange = next
      next(state)
    },
    async prepare(
      evidence: any,
      source: any,
      { discard = false }: { discard?: boolean } = {},
    ) {
      if (state.phase === 'reviewing' && state.dirty && !discard) {
        return 'discard_confirmation_required'
      }
      return performPrepare(evidence, source)
    },
    updateReview(field: string, value: string) {
      if (!state.review) return
      publish({
        review: { ...state.review, [field]: value },
        dirty: true,
        errors: [],
      })
    },
    sourceChanged(source: { tabId: number; url: string }) {
      if (!state.source) return false
      const changed =
        state.source.tabId !== source.tabId || state.source.url !== source.url
      if (changed) publish({ sourceChanged: true })
      return changed
    },
    async confirm() {
      if (!state.review || !state.evidence || state.phase === 'confirming')
        return null
      const required = ['companyName', 'role', 'jobUrl']
      const missing = required.filter(
        (field) => !String(state.review[field] || '').trim(),
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
        const result = await client.confirm({ ...state.review, jobContent })
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
