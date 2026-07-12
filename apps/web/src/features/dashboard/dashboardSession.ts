const clampLimit = (value: unknown) =>
  Math.max(1, Math.min(10, Number(value) || 5))
const operatorError = (error: unknown) => error as Error & { code?: string }

export function createDashboardSession(
  client: any,
  onChange: (state: any) => void = () => {},
) {
  let state: any = {
    loading: false,
    health: null,
    settings: null,
    analysisQueue: null,
    resumeQueue: null,
    analysisCursor: null,
    resumeCursor: null,
    analysisRunning: false,
    analysisResult: null,
    activeResumeId: null,
    resumeResults: {},
    errors: [],
  }

  const publish = (patch: any) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const load = async ({ reset = false } = {}) => {
    const analysisCursor = reset ? null : state.analysisCursor
    const resumeCursor = reset ? null : state.resumeCursor
    publish({ loading: true, errors: [] })
    try {
      const data = await client.loadDashboard({ analysisCursor, resumeCursor })
      publish({
        ...data,
        analysisCursor,
        resumeCursor,
        loading: false,
      })
      return data
    } catch (error) {
      const failure = operatorError(error)
      if (
        failure.code === 'invalid_cursor' &&
        (analysisCursor || resumeCursor)
      ) {
        publish({ analysisCursor: null, resumeCursor: null, loading: false })
        return load({ reset: true })
      }
      publish({
        loading: false,
        errors: [failure.message || 'The local backend could not be reached.'],
      })
      return null
    }
  }

  return {
    getState: () => state,
    subscribe(next: (state: any) => void) {
      onChange = next
      next(state)
    },
    setCursors(analysisCursor: string | null, resumeCursor: string | null) {
      publish({ analysisCursor, resumeCursor })
    },
    async load(options: { reset?: boolean } = {}) {
      return load(options)
    },
    async runAnalysis(limit: unknown) {
      if (state.analysisRunning) return null
      publish({ analysisRunning: true, analysisResult: null, errors: [] })
      try {
        const result = await client.runAnalysis(clampLimit(limit))
        publish({ analysisRunning: false, analysisResult: result })
        const queueChanged =
          result.ok &&
          result.result === 'completed' &&
          ((result.succeeded || 0) > 0 || (result.repaired || 0) > 0)
        if (queueChanged) {
          publish({ analysisCursor: null, resumeCursor: null })
          await load({ reset: true })
        } else {
          await load()
        }
        return result
      } catch (error) {
        publish({
          analysisRunning: false,
          errors: [
            operatorError(error).message || 'Analysis could not be completed.',
          ],
        })
        return null
      }
    },
    async createResume(applicationId: string) {
      if (state.activeResumeId) return null
      publish({ activeResumeId: applicationId, errors: [] })
      try {
        const result = await client.createResume(applicationId)
        publish({
          activeResumeId: null,
          resumeResults: { ...state.resumeResults, [applicationId]: result },
          resumeCursor:
            result.ok && result.result === 'created'
              ? null
              : state.resumeCursor,
        })
        await load()
        return result
      } catch (error) {
        publish({
          activeResumeId: null,
          errors: [
            operatorError(error).message ||
              'Resume Creation could not be completed.',
          ],
        })
        return null
      }
    },
    dismissAnalysisResult() {
      publish({ analysisResult: null })
    },
    dismissResumeResult(applicationId: string) {
      const resumeResults = { ...state.resumeResults }
      delete resumeResults[applicationId]
      publish({ resumeResults })
    },
  }
}
