import {
  createClient,
  createResume,
  getApplicationAnalysisQueue,
  getHealth,
  getOperatorSettings,
  getResumeCreationQueue,
  resetDemo,
  runApplicationAnalysis,
} from '@merida/api-client'

const operatorError = (error) => {
  if (error instanceof Error) return error
  return new Error(error?.error?.message || error?.errors?.[0] || 'The API request failed.')
}

const invoke = async (request) => {
  try {
    return await request
  } catch (error) {
    throw operatorError(error)
  }
}

const queueQuery = (cursor) => ({ limit: 5, ...(cursor ? { cursor } : {}) })

export function createDashboardClient(options = {}) {
  const generatedClient = createClient({
    baseUrl: options.baseUrl || globalThis.location?.origin || 'http://127.0.0.1:8000',
    fetch: options.fetch,
    responseStyle: 'data',
    throwOnError: true,
  })

  return {
    async loadDashboard({ analysisCursor, resumeCursor }) {
      const [health, settings, analysisQueue, resumeQueue] = await Promise.all([
        invoke(getHealth({ client: generatedClient })),
        invoke(getOperatorSettings({ client: generatedClient })),
        invoke(getApplicationAnalysisQueue({ client: generatedClient, query: queueQuery(analysisCursor) })),
        invoke(getResumeCreationQueue({ client: generatedClient, query: queueQuery(resumeCursor) })),
      ])
      return { health, settings, analysisQueue, resumeQueue }
    },
    runAnalysis(limit) {
      return invoke(runApplicationAnalysis({ client: generatedClient, body: { limit } }))
    },
    createResume(applicationId) {
      return invoke(createResume({ client: generatedClient, body: { applicationId } }))
    },
    resetDemo() {
      return invoke(resetDemo({ client: generatedClient }))
    },
  }
}
