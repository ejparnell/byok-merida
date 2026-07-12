import {
  createClient,
  createResume,
  getApplicationAnalysisQueue,
  getHealth,
  getOperatorSettings,
  getResumeCreationQueue,
  invokeData,
  resetDemo,
  runApplicationAnalysis,
} from '@merida/api-client'
import type {
  CreateResumeResponse,
  GetApplicationAnalysisQueueResponse,
  GetResumeCreationQueueResponse,
  HealthResponse,
  OperatorSettingsResponse,
  ResetDemoResponse,
  RunApplicationAnalysisResponse,
} from '@merida/api-client'

export type DashboardSnapshot = {
  health: HealthResponse
  settings: OperatorSettingsResponse
  analysisQueue: GetApplicationAnalysisQueueResponse
  resumeQueue: GetResumeCreationQueueResponse
}

export interface DashboardClient {
  loadDashboard(cursors: {
    analysisCursor?: string | null
    resumeCursor?: string | null
  }): Promise<DashboardSnapshot>
  runAnalysis(limit: number): Promise<RunApplicationAnalysisResponse>
  createResume(applicationId: string): Promise<CreateResumeResponse>
  resetDemo(): Promise<ResetDemoResponse>
}

const queueQuery = (cursor?: string | null) => ({
  limit: 5,
  ...(cursor ? { cursor } : {}),
})

export function createDashboardClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
): DashboardClient {
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
        invokeData<HealthResponse>(getHealth({ client: generatedClient })),
        invokeData<OperatorSettingsResponse>(
          getOperatorSettings({ client: generatedClient }),
        ),
        invokeData<GetApplicationAnalysisQueueResponse>(
          getApplicationAnalysisQueue({
            client: generatedClient,
            query: queueQuery(analysisCursor),
          }),
        ),
        invokeData<GetResumeCreationQueueResponse>(
          getResumeCreationQueue({
            client: generatedClient,
            query: queueQuery(resumeCursor),
          }),
        ),
      ])
      return { health, settings, analysisQueue, resumeQueue }
    },
    runAnalysis(limit: number) {
      return invokeData<RunApplicationAnalysisResponse>(
        runApplicationAnalysis({ client: generatedClient, body: { limit } }),
      )
    },
    createResume(applicationId: string) {
      return invokeData<CreateResumeResponse>(
        createResume({ client: generatedClient, body: { applicationId } }),
      )
    },
    resetDemo() {
      return invokeData<ResetDemoResponse>(
        resetDemo({ client: generatedClient }),
      )
    },
  }
}
