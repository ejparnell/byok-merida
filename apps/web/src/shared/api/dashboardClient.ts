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

const queueQuery = (cursor?: string | null) => ({
  limit: 5,
  ...(cursor ? { cursor } : {}),
})

export function createDashboardClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
) {
  const generatedClient = createClient({
    baseUrl:
      options.baseUrl || globalThis.location?.origin || 'http://127.0.0.1:8000',
    fetch: options.fetch,
    responseStyle: 'data',
    throwOnError: true,
  })

  return {
    async loadDashboard({
      analysisCursor,
      resumeCursor,
    }: {
      analysisCursor?: string | null
      resumeCursor?: string | null
    }) {
      const [health, settings, analysisQueue, resumeQueue] = await Promise.all([
        invokeApi(getHealth({ client: generatedClient })),
        invokeApi(getOperatorSettings({ client: generatedClient })),
        invokeApi(
          getApplicationAnalysisQueue({
            client: generatedClient,
            query: queueQuery(analysisCursor),
          }),
        ),
        invokeApi(
          getResumeCreationQueue({
            client: generatedClient,
            query: queueQuery(resumeCursor),
          }),
        ),
      ])
      return { health, settings, analysisQueue, resumeQueue } as any
    },
    runAnalysis(limit: number): Promise<any> {
      return invokeApi(
        runApplicationAnalysis({ client: generatedClient, body: { limit } }),
      ) as Promise<any>
    },
    createResume(applicationId: string): Promise<any> {
      return invokeApi(
        createResume({ client: generatedClient, body: { applicationId } }),
      ) as Promise<any>
    },
    resetDemo(): Promise<any> {
      return invokeApi(resetDemo({ client: generatedClient })) as Promise<any>
    },
  }
}
