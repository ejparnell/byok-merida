import {
  createClient,
  createResume,
  getApplicationAnalysisQueue,
  getHealth,
  getOperatorSettings,
  getResumeCreationQueue,
  invokeApi,
  resetDemo,
  runApplicationAnalysis,
} from '@merida/api-client'

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
        invokeApi(getHealth({ client: generatedClient })),
        invokeApi(getOperatorSettings({ client: generatedClient })),
        invokeApi(getApplicationAnalysisQueue({ client: generatedClient, query: queueQuery(analysisCursor) })),
        invokeApi(getResumeCreationQueue({ client: generatedClient, query: queueQuery(resumeCursor) })),
      ])
      return { health, settings, analysisQueue, resumeQueue }
    },
    runAnalysis(limit) {
      return invokeApi(runApplicationAnalysis({ client: generatedClient, body: { limit } }))
    },
    createResume(applicationId) {
      return invokeApi(createResume({ client: generatedClient, body: { applicationId } }))
    },
    resetDemo() {
      return invokeApi(resetDemo({ client: generatedClient }))
    },
  }
}
