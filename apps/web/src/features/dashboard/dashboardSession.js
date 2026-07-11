const clampLimit = (value) => Math.max(1, Math.min(10, Number(value) || 5))

export function createDashboardSession(client, onChange = () => {}) {
  let state = {
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

  const publish = (patch) => {
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
      if (error.code === 'invalid_cursor' && (analysisCursor || resumeCursor)) {
        publish({ analysisCursor: null, resumeCursor: null, loading: false })
        return load({ reset: true })
      }
      publish({ loading: false, errors: [error.message || 'The local backend could not be reached.'] })
      return null
    }
  }

  return {
    getState: () => state,
    subscribe(next) {
      onChange = next
      next(state)
    },
    setCursors(analysisCursor, resumeCursor) {
      publish({ analysisCursor, resumeCursor })
    },
    async load(options) {
      return load(options)
    },
    async runAnalysis(limit) {
      if (state.analysisRunning) return null
      publish({ analysisRunning: true, analysisResult: null, errors: [] })
      try {
        const result = await client.runAnalysis(clampLimit(limit))
        publish({ analysisRunning: false, analysisResult: result })
        const queueChanged = result.ok
          && result.result === 'completed'
          && ((result.succeeded || 0) > 0 || (result.repaired || 0) > 0)
        if (queueChanged) {
          publish({ analysisCursor: null, resumeCursor: null })
          await load({ reset: true })
        } else {
          await load()
        }
        return result
      } catch (error) {
        publish({ analysisRunning: false, errors: [error.message || 'Analysis could not be completed.'] })
        return null
      }
    },
    async createResume(applicationId) {
      if (state.activeResumeId) return null
      publish({ activeResumeId: applicationId, errors: [] })
      try {
        const result = await client.createResume(applicationId)
        publish({
          activeResumeId: null,
          resumeResults: { ...state.resumeResults, [applicationId]: result },
          resumeCursor: result.ok && result.result === 'created' ? null : state.resumeCursor,
        })
        await load()
        return result
      } catch (error) {
        publish({ activeResumeId: null, errors: [error.message || 'Resume Creation could not be completed.'] })
        return null
      }
    },
    dismissAnalysisResult() {
      publish({ analysisResult: null })
    },
    dismissResumeResult(applicationId) {
      const resumeResults = { ...state.resumeResults }
      delete resumeResults[applicationId]
      publish({ resumeResults })
    },
  }
}
